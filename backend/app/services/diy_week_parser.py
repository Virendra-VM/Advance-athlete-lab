"""Parse athlete DIY week prose into Pass-1 workouts.

Turns messages like "today mobility + strength, tomorrow 8 km + 1 hr ride,
Friday full-body, Saturday 15 km, Sunday 3–4 hr mountain" into workout rows
the schedule planner can honor instead of wiping with a library week.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.services.coach_advisory import DIY_PROPOSAL_RE, WEEKDAY_RE

DAY_ALIASES = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

DAY_ANCHOR_RE = re.compile(
    r"(?:"
    r"\b(?:on\s+)?(?P<weekday>monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b|"
    r"\b(?P<relative>yesterday|today|tomorrow)\b"
    r")",
    re.I,
)

KM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*km\b", re.I)
HOUR_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:hr|hrs|hour|hours)\b"
    r"|(\d+(?:\.\d+)?)\s*(?:hr|hrs|hour|hours)\b",
    re.I,
)
MIN_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:min|mins|minute|minutes)\b",
    re.I,
)

# Split multi-session clauses: "mobility and Strength" / "run ... and ... ride"
SESSION_SPLIT_RE = re.compile(
    r"\s+(?:and|,|/|\+)\s+(?=(?:"
    r"mobility|yoga|strength|core|full[\s-]?body|run|running|ride|bike|cycling|"
    r"endurance|long|swim|walk|rest"
    r")\b)",
    re.I,
)


def has_diy_week_proposal(message: str) -> bool:
    """True when the athlete named days + proposed sessions (not just 'plan this week')."""
    text = (message or "").strip()
    if not text:
        return False
    weekdays = WEEKDAY_RE.findall(text)
    relative = len(re.findall(r"\b(yesterday|today|tomorrow)\b", text, re.I))
    day_hits = len(weekdays) + relative
    if day_hits < 2:
        return False
    has_session = bool(
        re.search(
            r"\b("
            r"ride|run|running|bike|cycling|strength|mobility|yoga|core|"
            r"long|endurance|km|hr|hour|workout|session|train"
            r")\b",
            text,
            re.I,
        )
    )
    if not has_session:
        return False
    return bool(DIY_PROPOSAL_RE.search(text)) or day_hits >= 3


def parse_diy_week_from_message(message: str, clock: dict) -> list[dict[str, Any]]:
    """Extract proposed workouts from natural-language day plans."""
    text = (message or "").strip()
    if not text or not clock.get("today") or not clock.get("week_start"):
        return []
    if not has_diy_week_proposal(text):
        return []

    clauses = _split_day_clauses(text, clock)
    workouts: list[dict[str, Any]] = []
    for day, clause in clauses:
        if day < clock["week_start"] or day > clock["week_start"] + timedelta(days=6):
            continue
        # Past days with "I did X" still stamp the calendar; future/today are plans.
        for workout in _sessions_from_clause(day, clause):
            workouts.append(workout)
    return _dedupe_workouts(workouts)


def executed_by_day_from_context(
    context: dict | None,
    *,
    week_start: date,
    week_end: date | None = None,
) -> dict[date, list[dict[str, Any]]]:
    """Group recent_activities into Mon–Sun buckets for schedule stamping."""
    end = week_end or (week_start + timedelta(days=6))
    by_day: dict[date, list[dict[str, Any]]] = {}
    for activity in (context or {}).get("recent_activities") or []:
        raw = activity.get("activity_date") or activity.get("date")
        try:
            day = date.fromisoformat(str(raw)[:10])
        except (TypeError, ValueError):
            continue
        if day < week_start or day > end:
            continue
        minutes = activity.get("minutes")
        if minutes is None:
            minutes = round((activity.get("moving_time_s") or 0) / 60.0) or None
        km = activity.get("km")
        if km is None and activity.get("distance_m"):
            km = round(float(activity["distance_m"]) / 1000.0, 2)
        by_day.setdefault(day, []).append(
            {
                "name": activity.get("name") or activity.get("sport") or "Session",
                "sport": activity.get("sport") or activity.get("sport_type") or "Training",
                "minutes": minutes,
                "km": km,
                "avg_hr": activity.get("avg_hr") or activity.get("average_heartrate"),
            }
        )
    return by_day


def workouts_from_executed(
    executed_by_day: dict[date, list[dict[str, Any]]],
    *,
    today: date,
) -> list[dict[str, Any]]:
    """Synthetic planned rows for past days that already have files (Done stamps)."""
    rows: list[dict[str, Any]] = []
    for day, items in sorted(executed_by_day.items()):
        if day >= today:
            continue
        for item in items:
            minutes = item.get("minutes")
            if not isinstance(minutes, (int, float)) or minutes <= 0:
                minutes = 45
            sport = str(item.get("sport") or "Training")
            title = str(item.get("name") or sport)
            rows.append(
                {
                    "date": day.isoformat(),
                    "sport": sport[:64],
                    "title": title[:200],
                    "session_type": _infer_session_type(title, sport, ""),
                    "duration_min": int(round(minutes)),
                    "intensity": "Completed",
                    "description": "Logged session — already completed.",
                    "structure": [],
                    "completed": True,
                    "source": "executed",
                }
            )
    return rows


def merge_week_workouts(
    *,
    base: list[dict[str, Any]],
    overlay: list[dict[str, Any]],
    today: date,
) -> list[dict[str, Any]]:
    """Overlay athlete DIY / executed rows onto a base week.

    Past days: prefer executed/DIY stamps. Today and future: DIY replaces base
    for those dates; unspecified open days keep base library rows.
    """
    by_date: dict[str, list[dict[str, Any]]] = {}
    for workout in base:
        key = str(workout.get("date") or "")[:10]
        if not key:
            continue
        by_date.setdefault(key, []).append(dict(workout))

    overlay_dates = {
        str(item.get("date") or "")[:10]
        for item in overlay
        if str(item.get("date") or "")[:10]
    }
    for iso in overlay_dates:
        try:
            day = date.fromisoformat(iso)
        except ValueError:
            continue
        day_rows = [dict(item) for item in overlay if str(item.get("date") or "")[:10] == iso]
        if day < today:
            # Keep executed stamps; drop empty library ghosts for that day.
            by_date[iso] = day_rows
        else:
            by_date[iso] = day_rows

    merged: list[dict[str, Any]] = []
    for iso in sorted(by_date):
        merged.extend(by_date[iso])
    return merged


def soft_cap_today_only(
    workouts: list[dict[str, Any]],
    safety: dict | None,
    *,
    today: date,
) -> list[dict[str, Any]]:
    """Apply REST/EASY Today's Call to today's rows only — leave Sat/Sun alone."""
    from app.services.session_blueprints import downgrade_today_workout

    action = ((safety or {}).get("readiness") or {}).get("action") or "proceed"
    auto = (safety or {}).get("autoregulation") or (safety or {}).get("todays_call") or {}
    call_level = str(auto.get("call_level") or "").lower()
    if action == "proceed" and call_level not in {"rest", "easy", "caution", "moderate"}:
        return workouts
    if call_level in {"hard", "primed"} and action == "proceed":
        return workouts

    today_iso = today.isoformat()
    rest_today = action == "rest_or_mobility" or call_level == "rest"
    out: list[dict[str, Any]] = []
    today_capped: list[dict[str, Any]] = []
    for workout in workouts:
        if str(workout.get("date") or "")[:10] != today_iso:
            out.append(workout)
            continue
        # Don't downgrade already-completed stamps.
        if workout.get("completed") or workout.get("source") == "executed":
            out.append(workout)
            continue
        today_capped.append(downgrade_today_workout(workout, safety))

    if rest_today and today_capped:
        # One restore block for the day — don't stack duplicate mobility rows.
        best = max(today_capped, key=lambda item: int(item.get("duration_min") or 0))
        best = dict(best)
        best["title"] = "Restore / mobility"
        best["session_type"] = "mobility"
        best["sport"] = "Yoga / Mobility"
        best["intensity"] = "Recovery"
        out.append(best)
    else:
        out.extend(today_capped)
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _split_day_clauses(text: str, clock: dict) -> list[tuple[date, str]]:
    today: date = clock["today"]
    week_start: date = clock["week_start"]
    matches = list(DAY_ANCHOR_RE.finditer(text))
    if not matches:
        return []

    clauses: list[tuple[date, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[start:end].strip(" .;,\n\t")
        day = _resolve_day(match, today=today, week_start=week_start)
        if day is None:
            continue
        # Drop the leading anchor word from the session body when possible.
        body = DAY_ANCHOR_RE.sub("", chunk, count=1).strip(" .;,:-\n\t")
        body = re.sub(
            r"^(?:i('ll| will|'m going to| did| have done)|i'll be doing|doing|do|did)\s+",
            "",
            body,
            flags=re.I,
        ).strip()
        if body:
            clauses.append((day, body))
    return clauses


def _resolve_day(match: re.Match, *, today: date, week_start: date) -> date | None:
    relative = (match.group("relative") or "").lower()
    if relative == "yesterday":
        return today - timedelta(days=1)
    if relative == "today":
        return today
    if relative == "tomorrow":
        return today + timedelta(days=1)
    weekday = (match.group("weekday") or "").lower()
    key = re.sub(r"[^a-z]", "", weekday)
    if key not in DAY_ALIASES:
        return None
    return week_start + timedelta(days=DAY_ALIASES[key])


def _sessions_from_clause(day: date, clause: str) -> list[dict[str, Any]]:
    parts = [part.strip() for part in SESSION_SPLIT_RE.split(clause) if part.strip()]
    if not parts:
        parts = [clause]
    # Also catch "in the morning X and in afternoon Y" without sport keywords between.
    if len(parts) == 1 and re.search(r"\b(morning|afternoon|evening)\b", clause, re.I):
        morning = re.search(
            r"(?:in\s+the\s+)?morning\s+(?:i'?ll\s+do\s+|of\s+)?(.+?)(?=\s+and\s+(?:in\s+)?(?:the\s+)?afternoon|\Z)",
            clause,
            re.I | re.S,
        )
        afternoon = re.search(
            r"(?:in\s+the\s+)?afternoon\s+(?:i'?ll\s+do\s+)?(.+)$",
            clause,
            re.I | re.S,
        )
        rebuilt: list[str] = []
        if morning:
            rebuilt.append(morning.group(1).strip())
        if afternoon:
            rebuilt.append(afternoon.group(1).strip())
        if rebuilt:
            parts = rebuilt

    workouts: list[dict[str, Any]] = []
    for part in parts:
        built = _workout_from_fragment(day, part)
        if built:
            workouts.append(built)
    return workouts


def _workout_from_fragment(day: date, fragment: str) -> dict[str, Any] | None:
    text = (fragment or "").strip()
    if not text or len(text) < 3:
        return None
    # Skip pure narrative without a session cue.
    if not re.search(
        r"\b(ride|run|running|bike|cycling|strength|mobility|yoga|core|"
        r"long|endurance|swim|walk|rest|off|km|hr|hour|workout|train|session)\b",
        text,
        re.I,
    ):
        return None

    sport, title, session_type, intensity = _classify_fragment(text)
    duration = _duration_from_fragment(text, sport=sport, session_type=session_type)
    return {
        "date": day.isoformat(),
        "sport": sport,
        "title": title,
        "session_type": session_type,
        "duration_min": duration,
        "intensity": intensity,
        "description": text[:280],
        "structure": [],
        "source": "athlete_diy",
    }


def _classify_fragment(text: str) -> tuple[str, str, str, str]:
    lower = text.lower()
    if re.search(r"\b(rest|off day|day off)\b", lower) and not re.search(
        r"\b(run|ride|strength)\b", lower
    ):
        return "Rest", "Rest day", "rest", "None"
    has_mobility = bool(re.search(r"\b(mobility|yoga)\b", lower))
    has_strength = bool(re.search(r"\b(strength|full[\s-]?body|core|gym|lift)\b", lower))
    # Combined fragment without a successful split — prefer strength; mobility is support.
    if has_mobility and not has_strength:
        title = "Recovery day mobility" if "recovery" in lower else "Mobility"
        return "Yoga / Mobility", title, "mobility", "Very easy"
    if has_strength:
        if "full" in lower:
            title = "Full-body strength"
        elif "core" in lower:
            title = "Strength Training with Core"
        else:
            title = "Strength + core"
        return "Strength training", title, "strength", "RPE 6–7"
    if re.search(r"\b(bike|cycling|ride)\b", lower) or (
        "endurance" in lower and "run" not in lower
    ):
        mountain = bool(re.search(r"\b(mountain|hilly|hills|climb)\b", lower))
        hour = HOUR_RE.search(text)
        hours = 0.0
        if hour:
            if hour.group(1) is not None and hour.group(2) is not None:
                hours = (float(hour.group(1)) + float(hour.group(2))) / 2.0
            elif hour.group(3) is not None:
                hours = float(hour.group(3))
        longish = mountain or "long" in lower or hours >= 2.0
        title = (
            "Long mountain ride"
            if mountain
            else ("Long endurance ride" if longish else "Endurance ride (Z2)")
        )
        session = "long" if longish else "endurance"
        return "Cycling", title, session, "Easy / endurance"
    if re.search(r"\b(run|running|jog)\b", lower) or KM_RE.search(text):
        longish = "long" in lower or bool(
            KM_RE.search(text) and float(KM_RE.search(text).group(1)) >= 12
        )
        km_match = KM_RE.search(text)
        if km_match and longish:
            title = f"Long run ({km_match.group(1)} km)"
        elif km_match:
            title = f"Easy run ({km_match.group(1)} km)"
        else:
            title = "Long aerobic run" if longish else "Easy aerobic (Z2)"
        return "Running", title, "long" if longish else "easy", "Easy / conversational"
    if "swim" in lower:
        return "Swimming", "Easy swim", "easy", "Easy / conversational"
    if "walk" in lower or "hike" in lower:
        return "Walking", "Easy walk", "easy", "Easy / conversational"
    if "mobility" in lower or "yoga" in lower:
        return "Yoga / Mobility", "Mobility", "mobility", "Very easy"
    return "Training", text[:80].title(), "easy", "Easy / conversational"


def _duration_from_fragment(text: str, *, sport: str, session_type: str) -> int:
    hour = HOUR_RE.search(text)
    if hour:
        if hour.group(1) is not None and hour.group(2) is not None:
            low = float(hour.group(1))
            high = float(hour.group(2))
            return int(round(((low + high) / 2.0) * 60))
        single = hour.group(3)
        if single is not None:
            return int(round(float(single) * 60))
    minutes = MIN_RE.search(text)
    if minutes:
        low = float(minutes.group(1))
        high = float(minutes.group(2)) if minutes.group(2) else low
        return int(round((low + high) / 2.0))
    km = KM_RE.search(text)
    if km:
        distance = float(km.group(1))
        # ~5:30–6:00 /km conversational.
        return max(20, int(round(distance * 5.75)))
    if session_type == "long":
        return 180 if "cycl" in sport.lower() or "ride" in text.lower() else 90
    if session_type == "strength":
        return 45
    if session_type == "mobility":
        return 30
    if session_type == "rest":
        return 0
    return 60


def _infer_session_type(title: str, sport: str, intensity: str) -> str:
    from app.services.week_from_chat import _infer_session_type as infer

    return infer(title, sport, intensity)


def _dedupe_workouts(workouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for workout in workouts:
        key = (
            str(workout.get("date") or "")[:10],
            str(workout.get("title") or "").lower(),
            str(workout.get("session_type") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(workout)
    return out
