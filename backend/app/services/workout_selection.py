"""Phase-aware workout selection engine — Phase 2 SWL.

Picks library templates from season phase, sport, safety budget, and slot role
(easy / long / quality / strength / mobility). Used for deterministic weeks and
to attach template IDs to LLM-generated plans before enrichment.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.coach_templates import ENDURANCE_SPORTS, _primary_sports, _spread_days
from app.services.workout_library import (
    LIBRARY_VERSION,
    get_template_by_id,
    pick_template,
)

HARD_SESSION_TYPES = {
    "tempo",
    "threshold",
    "intervals",
    "hills",
    "speed",
    "race",
}

# Deterministic template presets: (sport_key, phase_type, quality_index) → template id
PHASE_TEMPLATE_PRESETS: dict[tuple[str, str, int], str] = {
    ("running", "base", 0): "run_threshold_2x10_lthr1",
    ("running", "build", 0): "run_threshold_2x10_lthr1",
    ("running", "build", 1): "run_vo2_5x3",
    ("running", "peak", 0): "run_marathon_pace_2x20",
    ("running", "peak", 1): "run_vo2_4x4",
    ("running", "taper", 0): "run_taper_shakeout",
    ("running", "recovery_week", 0): "run_easy_z2",
    ("running", "restore", 0): "run_recovery_jog",
    ("trail_running", "base", 0): "trail_hills_8x60",
    ("trail_running", "build", 0): "trail_hills_8x60",
    ("trail_running", "build", 1): "trail_fartlek_vert",
    ("trail_running", "peak", 0): "trail_race_pace",
    ("cycling", "base", 0): "bike_threshold_3x10",
    ("cycling", "build", 0): "bike_sweet_spot_2x20",
    ("cycling", "build", 1): "bike_vo2_5x3",
    ("cycling", "peak", 0): "bike_race_pace_2x15",
    ("cycling", "peak", 1): "bike_over_under_3x12",
    ("cycling", "taper", 0): "bike_taper_opener",
    ("swimming", "base", 0): "swim_css_threshold_8x100",
    ("swimming", "build", 0): "swim_css_threshold_8x100",
    ("swimming", "build", 1): "swim_vo2_8x100",
    ("swimming", "peak", 0): "swim_vo2_16x50",
    ("triathlon", "build", 0): "tri_bike_threshold_run_easy",
    ("triathlon", "peak", 0): "tri_brick_bike_run",
    ("strength", "base", 0): "strength_full_body",
    ("strength", "build", 0): "strength_hypertrophy",
    ("strength", "peak", 0): "strength_power",
}

PHASE_EASY_TEMPLATE: dict[str, str] = {
    "running": "run_easy_z2",
    "trail_running": "trail_easy_terrain",
    "cycling": "bike_easy_z2",
    "swimming": "swim_easy_aerobic",
    "triathlon": "tri_easy_multi",
    "strength": "strength_deload",
    "mobility": "mobility_recovery_day",
    "rowing": "row_easy_aerobic",
    "walking": "walk_easy_recovery",
    "cross_training": "xt_elliptical_easy",
}

PHASE_LONG_TEMPLATE: dict[str, str] = {
    "running": "run_long_z2",
    "trail_running": "trail_vert_long",
    "cycling": "bike_long_z2",
    "swimming": "swim_long_continuous",
    "triathlon": "tri_easy_multi",
    "rowing": "row_long_steady",
    "walking": "walk_hike_long",
}

# (session_type, preferred_intent) when no preset matches
PHASE_QUALITY_INTENTS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("running", "base"): [("threshold", "threshold")],
    ("running", "build"): [("threshold", "threshold"), ("intervals", "vo2")],
    ("running", "peak"): [("tempo", "race_pace"), ("intervals", "vo2")],
    ("running", "taper"): [("easy", "easy")],
    ("running", "recovery_week"): [("easy", "easy")],
    ("running", "restore"): [("mobility", "mobility_general")],
    ("trail_running", "base"): [("hills", "hills")],
    ("trail_running", "build"): [("hills", "hills"), ("intervals", "fartlek")],
    ("trail_running", "peak"): [("race", "race_pace")],
    ("cycling", "base"): [("threshold", "threshold")],
    ("cycling", "build"): [("threshold", "sweet_spot"), ("intervals", "vo2")],
    ("cycling", "peak"): [("tempo", "race_pace"), ("intervals", "vo2")],
    ("cycling", "taper"): [("easy", "easy")],
    ("swimming", "base"): [("threshold", "threshold")],
    ("swimming", "build"): [("threshold", "threshold"), ("intervals", "vo2")],
    ("swimming", "peak"): [("intervals", "vo2")],
    ("triathlon", "build"): [("threshold", "threshold")],
    ("triathlon", "peak"): [("cross-training", "cross_training")],
    ("strength", "base"): [("strength", "strength_general")],
    ("strength", "build"): [("strength", "strength_hypertrophy")],
    ("strength", "peak"): [("strength", "strength_power")],
}


def phase_type_from_context(context: dict[str, Any] | None) -> str:
    season = (context or {}).get("season") or {}
    if not season.get("has_plan"):
        return "base"
    current = season.get("current_phase") or {}
    week_intent = season.get("week_intent") or {}
    return str(
        current.get("phase_type") or week_intent.get("phase_type") or "base"
    ).lower()


def week_intent_from_context(context: dict[str, Any] | None) -> dict[str, Any]:
    season = (context or {}).get("season") or {}
    return dict(season.get("week_intent") or {})


def _sport_key(sport: str | None) -> str:
    blob = (sport or "").strip().lower()
    if "trail" in blob:
        return "trail_running"
    if any(token in blob for token in ("triathlon", "tri ")):
        return "triathlon"
    if any(token in blob for token in ("cycl", "bike", "ride")):
        return "cycling"
    if "swim" in blob:
        return "swimming"
    if any(token in blob for token in ("strength", "gym", "lift", "weights")):
        return "strength"
    if any(token in blob for token in ("yoga", "mobility", "stretch", "pilates")):
        return "mobility"
    if "row" in blob:
        return "rowing"
    if "walk" in blob or "hike" in blob:
        return "walking"
    if "run" in blob or "jog" in blob:
        return "running"
    return "running"


def _scaled_minutes(base: int, volume_bias: float, *, kind: str = "weekday") -> int:
    bias = float(volume_bias or 1.0)
    if kind == "long":
        scaled = round(base * max(0.85, min(1.15, bias)))
    elif kind == "recovery":
        scaled = round(base * 0.6 * max(0.7, min(1.0, bias)))
    else:
        scaled = round(base * max(0.75, min(1.1, bias)))
    return max(20, scaled)


def _quality_intent_pair(
    sport_key: str,
    phase_type: str,
    quality_index: int,
) -> tuple[str, str]:
    options = PHASE_QUALITY_INTENTS.get((sport_key, phase_type))
    if not options:
        options = PHASE_QUALITY_INTENTS.get((sport_key, "base"), [("threshold", "threshold")])
    session_type, intent = options[quality_index % len(options)]
    return session_type, intent


def select_template_for_slot(
    *,
    sport: str,
    slot: str,
    phase_type: str,
    safety: dict[str, Any] | None = None,
    quality_index: int = 0,
    workout_stub: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Pick a library template for a week slot (easy, long, quality, strength, mobility)."""
    sport_key = _sport_key(sport)
    stub = dict(workout_stub or {})
    stub.setdefault("sport", sport)

    if slot == "easy":
        preset_id = PHASE_EASY_TEMPLATE.get(sport_key, "run_easy_z2")
        template = get_template_by_id(preset_id)
        if template:
            return template
        stub.update({"session_type": "easy", "title": f"Easy {sport}"})
        return pick_template(stub, safety=safety, preferred_intent="easy", phase_type=phase_type)

    if slot == "long":
        preset_id = PHASE_LONG_TEMPLATE.get(sport_key)
        if preset_id:
            template = get_template_by_id(preset_id)
            if template:
                return template
        stub.update({"session_type": "long", "title": f"Long {sport}"})
        return pick_template(stub, safety=safety, preferred_intent="long", phase_type=phase_type)

    if slot == "mobility":
        stub.update({"session_type": "mobility", "title": "Recovery mobility"})
        return get_template_by_id("mobility_recovery_day") or pick_template(
            stub, safety=safety, preferred_intent="mobility_general", phase_type=phase_type
        )

    if slot == "strength":
        if (safety or {}).get("spine_lock"):
            template = get_template_by_id("strength_spine_lock")
            if template:
                return template
        preset_id = PHASE_TEMPLATE_PRESETS.get((sport_key, phase_type, 0))
        if sport_key == "strength" and preset_id:
            template = get_template_by_id(preset_id)
            if template:
                return template
        stub.update({"session_type": "strength", "title": "Strength session"})
        return pick_template(stub, safety=safety, preferred_intent="strength_general", phase_type=phase_type)

    if slot == "quality":
        preset_id = PHASE_TEMPLATE_PRESETS.get((sport_key, phase_type, quality_index))
        if preset_id:
            template = get_template_by_id(preset_id)
            if template:
                return template
        session_type, intent = _quality_intent_pair(sport_key, phase_type, quality_index)
        stub.update({"session_type": session_type, "title": f"{intent.replace('_', ' ').title()} {sport}"})
        return pick_template(stub, safety=safety, preferred_intent=intent, phase_type=phase_type)

    return None


def _workout_from_template(
    template: dict[str, Any],
    *,
    session_date: date,
    sport: str,
    duration_min: int,
    phase_type: str,
) -> dict[str, Any]:
    session_types = template.get("session_types") or ["easy"]
    return {
        "date": session_date.isoformat(),
        "sport": sport,
        "title": template.get("title") or f"{sport} session",
        "session_type": session_types[0],
        "duration_min": duration_min,
        "intensity": (template.get("main") or {}).get("intensity"),
        "description": template.get("summary") or "",
        "structure": [],
        "library_template_id": template.get("id"),
        "library_version": LIBRARY_VERSION,
        "selection_phase": phase_type,
    }


def build_library_week(
    context: dict,
    safety: dict,
    week_start: date,
    today: date | None = None,
) -> dict:
    """Build a full week using phase-aware library selection."""
    sports = _primary_sports(context)
    phase_type = phase_type_from_context(context)
    week_intent = week_intent_from_context(context)
    volume_bias = float(week_intent.get("volume_bias") or 1.0)
    long_cap = int(week_intent.get("long_session_allowed_min") or safety.get("max_session_minutes") or 180)

    days = safety["max_days_per_week"]
    offsets = _spread_days(days)
    today = today or date.today()
    remaining = [offset for offset in offsets if week_start + timedelta(days=offset) >= today]
    if not remaining:
        remaining = [max(0, (today - week_start).days)]

    typical = int(safety.get("typical_session_minutes") or 45)
    max_session = int(safety["max_session_minutes"])
    session_minutes = _scaled_minutes(typical, volume_bias, kind="weekday")
    long_minutes = min(
        max_session,
        long_cap,
        _scaled_minutes(max(round(typical * 2), typical + 60, 90), volume_bias, kind="long"),
    )

    readiness = safety["readiness"]
    hard_budget = int(safety["max_hard_sessions"])
    quality_slot = remaining[len(remaining) // 2] if len(remaining) > 1 else None
    quality_index = 0

    workouts: list[dict[str, Any]] = []
    for index, offset in enumerate(remaining):
        sport = sports[index % len(sports)]
        sport_key = sport.lower()
        is_last = index == len(remaining) - 1
        session_date = week_start + timedelta(days=offset)

        if index == 0 and readiness["action"] != "proceed":
            slot = "mobility" if readiness["action"] == "rest_or_mobility" else "easy"
            duration = _scaled_minutes(session_minutes, volume_bias, kind="recovery")
            template = select_template_for_slot(
                sport=sport,
                slot=slot,
                phase_type=phase_type,
                safety=safety,
            )
            if template:
                row = _workout_from_template(
                    template,
                    session_date=session_date,
                    sport=sport,
                    duration_min=duration,
                    phase_type=phase_type,
                )
                row["description"] = (
                    f"{readiness['reason']} Keep this genuinely easy and reassess tomorrow."
                )
                workouts.append(row)
            else:
                workouts.append(
                    {
                        "date": session_date.isoformat(),
                        "sport": sport,
                        "title": "Recovery session",
                        "session_type": "mobility" if slot == "mobility" else "easy",
                        "duration_min": duration,
                        "intensity": "Recovery",
                        "description": f"{readiness['reason']} Keep this genuinely easy and reassess tomorrow.",
                        "structure": [],
                    }
                )
            continue

        if hard_budget > 0 and offset == quality_slot:
            template = select_template_for_slot(
                sport=sport,
                slot="quality",
                phase_type=phase_type,
                safety=safety,
                quality_index=quality_index,
            )
            hard_budget -= 1
            quality_index += 1
            if template:
                workouts.append(
                    _workout_from_template(
                        template,
                        session_date=session_date,
                        sport=sport,
                        duration_min=session_minutes,
                        phase_type=phase_type,
                    )
                )
                continue

        if is_last and sport_key in ENDURANCE_SPORTS and days > 2 and phase_type not in {"taper", "restore"}:
            template = select_template_for_slot(
                sport=sport,
                slot="long",
                phase_type=phase_type,
                safety=safety,
            )
            if template:
                workouts.append(
                    _workout_from_template(
                        template,
                        session_date=session_date,
                        sport=sport,
                        duration_min=long_minutes,
                        phase_type=phase_type,
                    )
                )
                continue

        if sport_key == "strength training" or _sport_key(sport) == "strength":
            template = select_template_for_slot(
                sport="Strength training",
                slot="strength",
                phase_type=phase_type,
                safety=safety,
            )
            if template:
                workouts.append(
                    _workout_from_template(
                        template,
                        session_date=session_date,
                        sport=sport,
                        duration_min=session_minutes,
                        phase_type=phase_type,
                    )
                )
                continue

        template = select_template_for_slot(
            sport=sport,
            slot="easy",
            phase_type=phase_type,
            safety=safety,
        )
        if template:
            workouts.append(
                _workout_from_template(
                    template,
                    session_date=session_date,
                    sport=sport,
                    duration_min=session_minutes,
                    phase_type=phase_type,
                )
            )
        else:
            workouts.append(
                {
                    "date": session_date.isoformat(),
                    "sport": sport,
                    "title": f"Easy {sport.lower()}",
                    "session_type": "easy",
                    "duration_min": session_minutes,
                    "intensity": "Easy / conversational",
                    "description": "Conversational effort throughout.",
                    "structure": [],
                }
            )

    goal = context.get("profile", {}).get("primary_goal") or "general fitness"
    focus_by_phase = {
        "base": "Aerobic base and durability",
        "build": "Threshold and VO₂ development",
        "peak": "Race-specific sharpening",
        "taper": "Freshness with openers",
        "restore": "Recovery and mobility",
        "recovery_week": "Absorb load — easy volume",
    }
    return {
        "title": f"Week of {week_start.strftime('%b %d')}",
        "summary": (
            f"{len(workouts)} library-selected sessions for {phase_type} phase across "
            f"{', '.join(sports)}, aimed at {goal}."
        ),
        "focus": focus_by_phase.get(phase_type, "Consistency and aerobic base"),
        "week_start": week_start.isoformat(),
        "workouts": workouts,
        "coach_notes": (
            f"Sessions selected from the science workout library for {phase_type} phase "
            f"(volume bias {volume_bias:.2f}). Structures are zone-resolved at enrichment."
        ),
        "citations": [],
        "selection_engine": "swl-v2",
    }


def _is_generic_title(title: str | None) -> bool:
    blob = (title or "").lower()
    markers = (
        "quality session",
        "easy ",
        "long ",
        "recovery session",
        "threshold",
        "interval",
    )
    return any(marker in blob for marker in markers) or len(blob) < 12


def apply_library_selection_to_plan(
    plan_data: dict[str, Any],
    context: dict[str, Any],
    safety: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach library template IDs to each workout row (LLM or partial plans)."""
    plan = dict(plan_data or {})
    phase_type = phase_type_from_context(context)
    quality_index = 0
    workouts: list[dict[str, Any]] = []

    for workout in plan.get("workouts") or []:
        item = dict(workout)
        session_type = str(item.get("session_type") or "easy").lower()

        existing_id = item.get("library_template_id")
        if existing_id and get_template_by_id(str(existing_id)):
            workouts.append(item)
            if session_type in HARD_SESSION_TYPES:
                quality_index += 1
            continue

        if session_type == "rest":
            workouts.append(item)
            continue

        sport = item.get("sport") or "Running"
        sport_key = _sport_key(sport)

        if session_type in HARD_SESSION_TYPES:
            slot = "quality"
        elif session_type == "long":
            slot = "long"
        elif session_type in {"strength"}:
            slot = "strength"
        elif session_type in {"mobility"}:
            slot = "mobility"
        else:
            slot = "easy"

        template = select_template_for_slot(
            sport=sport,
            slot=slot,
            phase_type=phase_type,
            safety=safety,
            quality_index=quality_index if slot == "quality" else 0,
            workout_stub=item,
        )
        if template:
            if slot == "quality":
                quality_index += 1
            session_types = template.get("session_types") or [session_type]
            item["library_template_id"] = template.get("id")
            item["library_version"] = LIBRARY_VERSION
            item["selection_phase"] = phase_type
            item["session_type"] = session_types[0]
            if _is_generic_title(item.get("title")) and template.get("title"):
                item["title"] = template["title"]
            if not (item.get("description") or "").strip() and template.get("summary"):
                item["description"] = template["summary"]
            item["structure"] = []

        workouts.append(item)

    plan["workouts"] = workouts
    plan["selection_engine"] = plan.get("selection_engine") or "swl-v2"
    return plan
