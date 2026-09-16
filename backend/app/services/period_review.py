"""Month and year performance recaps — first-class period review, not a week debrief."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, time
from typing import Any

from sqlalchemy.orm import Session

from app.models import Activity, AthleteProfile, DailyHealthMetric
from app.services.coach_intent import MONTH_REVIEW, YEAR_REVIEW

MONTH_FORMAT_RULES = """OUTPUT FORMAT — hard fail if you violate any of these:
- Intent is MONTH_REVIEW. Recap the PERIOD REVIEW PACKET window. Nothing else.
- Completely skip ⚡ THE BOTTOM LINE, ride autopsies, NP/IF/TSS/laps, and week schedule tables.
- Layout in this exact order:
  🧭 MONTH GRADE
  📅 WHAT LANDED
  🫀 RECOVERY COST
  🧠 NEXT BLOCK'S CALL
  🔬 THE SCIENCE
- 📅 WHAT LANDED = one Markdown table, one row per week in the window:
  | Week | Sessions | Minutes | Quality | Note |
- BAN 🟢 TODAY'S CALL, 🗓️ REVISED WEEK, and Add-to-Schedule language.
- No analogies unless the athlete asked WHY/HOW."""

YEAR_FORMAT_RULES = """OUTPUT FORMAT — hard fail if you violate any of these:
- Intent is YEAR_REVIEW. Recap the PERIOD REVIEW PACKET window. Nothing else.
- Completely skip ride autopsies, NP/IF/TSS/laps, and week schedule tables.
- Layout in this exact order:
  🧭 YEAR GRADE
  📅 WHAT LANDED
  🫀 RECOVERY COST
  🧠 NEXT SEASON'S CALL
  🔬 THE SCIENCE
- 📅 WHAT LANDED = one Markdown table, one row per month in the window:
  | Month | Sessions | Minutes | Quality | Note |
- BAN 🟢 TODAY'S CALL, 🗓️ REVISED WEEK, and Add-to-Schedule language."""

PERIOD_REVIEW_SCHEMA = """{
  "reply": "string, period debrief: GRADE, WHAT LANDED table, RECOVERY COST, NEXT CALL, science. No ride autopsy, no week schedule table.",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "MONTH_REVIEW"
}"""


def period_review_system_prompt(horizon: str) -> str:
    rules = YEAR_FORMAT_RULES if horizon == "year" else MONTH_FORMAT_RULES
    lens = (
        "You are a Pro Olympic Coach doing a season/year debrief."
        if horizon == "year"
        else "You are a Pro Olympic Coach doing a monthly training debrief."
    )
    return (
        "You are the Advance Athlete Lab coach. Be plain, honest, and specific.\n\n"
        f"Role lens:\n{lens} Grade the window they actually lived — volume, "
        "consistency, quality days, recovery cost. Do not rewrite next week's calendar.\n\n"
        + rules
    )


def period_review_task(horizon: str) -> str:
    noun = "year" if horizon == "year" else "month"
    return (
        f"Debrief the athlete's {noun} from PERIOD REVIEW PACKET. Follow OUTPUT FORMAT exactly. "
        "Use only packet totals and bucket rows. Do not invent sessions. "
        "Do not paste a 7-day schedule or ask them to add a week to Schedule."
    )


def review_period_window(clock: dict, message: str, *, horizon: str) -> tuple[date, date, str]:
    today = clock["today"]
    text = (message or "").lower()
    if horizon == "year":
        if re.search(r"\blast year\b|\bprevious year\b|\blast season\b", text):
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return start, end, "last calendar year"
        if re.search(r"\blast 12 months\b|\bpast 12 months\b|\blast twelve months\b", text):
            start = today - timedelta(days=365)
            return start, today, "last 12 months"
        start = date(today.year, 1, 1)
        return start, today, "this year (Jan–today)"

    if re.search(r"\blast 30 days\b|\bpast 30 days\b|\blast thirty days\b", text):
        start = today - timedelta(days=29)
        return start, today, "last 30 days"
    if re.search(r"\blast 4 weeks\b|\bpast 4 weeks\b|\blast four weeks\b", text):
        start = today - timedelta(days=27)
        return start, today, "last 4 weeks"
    if re.search(r"\blast month\b|\bprevious month\b|\bpast month\b", text):
        first_this = date(today.year, today.month, 1)
        end = first_this - timedelta(days=1)
        start = date(end.year, end.month, 1)
        return start, end, "last calendar month"
    start = date(today.year, today.month, 1)
    return start, today, "this month (1st–today)"


def _activity_day(activity: Activity) -> date | None:
    value = activity.activity_date
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _quality_blob(*parts: object) -> bool:
    text = " ".join(str(part or "") for part in parts).lower()
    tokens = (
        "threshold",
        "interval",
        "vo2",
        "over-under",
        "over under",
        "tempo",
        "race",
        "quality",
        "speed",
        "hills",
    )
    return any(token in text for token in tokens)


def build_period_review_packet(
    db: Session,
    profile: AthleteProfile,
    context: dict,
    clock: dict,
    message: str,
    *,
    horizon: str,
) -> dict:
    start, end, label = review_period_window(clock, message, horizon=horizon)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == profile.id,
            Activity.canonical_activity_id.is_(None),
            Activity.activity_date >= start_dt,
            Activity.activity_date < end_dt,
        )
        .order_by(Activity.activity_date.asc())
        .all()
    )

    buckets: dict[str, dict[str, Any]] = {}

    def _bucket_key(day: date) -> str:
        if horizon == "year":
            return f"{day.year:04d}-{day.month:02d}"
        monday = day - timedelta(days=day.weekday())
        return monday.isoformat()

    def _bucket_label(key: str, day: date) -> str:
        if horizon == "year":
            return calendar.month_abbr[day.month]
        monday = date.fromisoformat(key)
        sunday = monday + timedelta(days=6)
        return f"{monday.isoformat()} → {min(sunday, end).isoformat()}"

    total_minutes = 0
    total_km = 0.0
    session_count = 0
    quality_days = 0
    quality_day_set: set[date] = set()

    for activity in activities:
        day = _activity_day(activity)
        if day is None or day < start or day > end:
            continue
        minutes = round((activity.moving_time_s or 0) / 60.0)
        km = round((activity.distance_m or 0) / 1000.0, 2)
        key = _bucket_key(day)
        bucket = buckets.setdefault(
            key,
            {
                "key": key,
                "label": _bucket_label(key, day),
                "sessions": 0,
                "minutes": 0,
                "km": 0.0,
                "quality": 0,
            },
        )
        bucket["sessions"] += 1
        bucket["minutes"] += minutes
        bucket["km"] += km
        session_count += 1
        total_minutes += minutes
        total_km += km
        if _quality_blob(activity.name, activity.sport_type):
            bucket["quality"] += 1
            if day not in quality_day_set:
                quality_day_set.add(day)
                quality_days += 1

    nights = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == profile.id,
            DailyHealthMetric.metric_date >= start,
            DailyHealthMetric.metric_date <= end,
        )
        .all()
    )

    def _mean(values: list) -> float | None:
        numbers = [float(value) for value in values if isinstance(value, (int, float))]
        if not numbers:
            return None
        return round(sum(numbers) / len(numbers), 1)

    rows = sorted(buckets.values(), key=lambda row: row["key"])
    load = (context.get("safety") or {}).get("load") or {}
    return {
        "horizon": horizon,
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": label,
        },
        "buckets": rows,
        "totals": {
            "sessions": session_count,
            "minutes": round(total_minutes),
            "km": round(total_km, 1),
            "quality_days": quality_days,
            "synced_files": len(activities),
        },
        "recovery": {
            "nights": len(nights),
            "avg_sleep_score": _mean([row.sleep_score for row in nights]),
            "avg_sleep_min": _mean(
                [getattr(row, "sleep_duration_min", None) for row in nights]
            ),
            "avg_hrv": _mean([row.hrv for row in nights]),
            "avg_stress": _mean([row.stress for row in nights]),
            "avg_rhr": _mean([row.resting_heart_rate for row in nights]),
        },
        "load": {
            "acute_minutes": load.get("acute_minutes"),
            "chronic_minutes": load.get("chronic_minutes"),
            "minutes_acwr": load.get("minutes_acwr"),
        },
        "coverage_note": (
            "Totals are from synced files in this window — not every session ever done."
        ),
    }


def template_period_review(
    message: str,
    safety: dict,
    science_hits: list[dict],
    *,
    packet: dict | None = None,
    horizon: str = "month",
) -> dict[str, Any]:
    packet = packet or {}
    window = packet.get("window") or {}
    totals = packet.get("totals") or {}
    recovery = packet.get("recovery") or {}
    buckets = packet.get("buckets") or []
    load = safety.get("load") or packet.get("load") or {}
    acwr = load.get("minutes_acwr")
    sessions = totals.get("sessions") or 0
    minutes = totals.get("minutes") or 0
    quality = totals.get("quality_days") or 0
    label = window.get("label") or ("this year" if horizon == "year" else "this month")
    grade_header = "🧭 YEAR GRADE" if horizon == "year" else "🧭 MONTH GRADE"
    next_header = "🧠 NEXT SEASON'S CALL" if horizon == "year" else "🧠 NEXT BLOCK'S CALL"
    intent = YEAR_REVIEW if horizon == "year" else MONTH_REVIEW

    if sessions == 0:
        grade = f"**Incomplete** — no synced files in {label}."
    elif quality == 0:
        grade = f"**Aerobic block** — {sessions} sessions, volume without a quality day."
    else:
        grade = (
            f"**Solid {horizon}** — {sessions} sessions, {quality} quality day(s) in {label}."
        )

    if horizon == "year":
        table = [
            "| Month | Sessions | Minutes | Quality | Note |",
            "|---|---|---|---|---|",
        ]
    else:
        table = [
            "| Week | Sessions | Minutes | Quality | Note |",
            "|---|---|---|---|---|",
        ]
    if buckets:
        for row in buckets:
            note = "Quality mixed in." if row.get("quality") else "Aerobic / easy bias."
            table.append(
                f"| {row.get('label') or '—'} | {row.get('sessions') or 0} | "
                f"{row.get('minutes') or 0} | {row.get('quality') or 0} | {note} |"
            )
    else:
        table.append("| — | 0 | 0 | 0 | No files in this window. |")

    sleep = recovery.get("avg_sleep_score")
    hrv = recovery.get("avg_hrv")
    next_calls = [
        "1. Keep frequency; cut the longest day ~20–30% if this block ran long.",
        "2. Put quality on recovered days only — HRV in range before threshold.",
        "3. First session after this recap stays easy or technique, not revenge intervals.",
    ]
    science = [
        f"• 🔬 THE SCIENCE: {sessions} files / {minutes} min in {label} is the work that landed, not a single peak day.",
        "• 🗣️ LOCKER ROOM LINGO: Consistency is the grade. One hero session does not save a quiet month.",
        "• 💡 REAL-WORLD EXAMPLE: Spread the next block — more easy hits, one controlled quality day.",
    ]
    lines = [
        grade_header,
        grade,
        f"**Sessions:** {sessions}",
        f"**Minutes:** {minutes}",
        f"**Quality days:** {quality}",
        f"**ACWR (current):** {acwr if acwr is not None else 'Missing'}",
        f"**Window:** {window.get('start') or '—'} → {window.get('end') or '—'}",
        "",
        "📅 WHAT LANDED",
        *table,
        "",
        "🫀 RECOVERY COST",
        f"• **Sleep score (avg):** {sleep if sleep is not None else 'Missing'}",
        f"• **HRV (avg):** {hrv if hrv is not None else 'Missing'}",
        f"• **Stress (avg):** {recovery.get('avg_stress') if recovery.get('avg_stress') is not None else 'Missing'}",
        f"• **RHR (avg):** {recovery.get('avg_rhr') if recovery.get('avg_rhr') is not None else 'Missing'}",
        f"• {packet.get('coverage_note') or 'Synced files only.'}",
        "",
        next_header,
        *next_calls,
        "",
        "🔬 THE SCIENCE",
        *science,
    ]
    return {
        "reply": "\n".join(lines),
        "citations": [
            hit["citation"]["slug"]
            for hit in science_hits[:2]
            if hit.get("citation", {}).get("slug")
        ],
        "escalate": False,
        "escalation_reason": None,
        "intent": intent,
    }
