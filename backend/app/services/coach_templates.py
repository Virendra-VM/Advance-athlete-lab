"""Deterministic plan/advice templates.

These run when no AI provider is configured, when a provider fails, or when a
generated plan is rejected as unsafe. They are built from the same safety profile
the LLM is constrained by, so the app is always able to answer.
"""

from __future__ import annotations

from datetime import date, timedelta

ENDURANCE_SPORTS = {"running", "trail running", "cycling", "swimming", "rowing", "walking / hiking", "triathlon"}

QUALITY_BY_SPORT = {
    "running": ("threshold", "2 x 10 min at controlled hard effort, 3 min easy between"),
    "trail running": ("hills", "8 x 60 s strong uphill, walk or jog down"),
    "cycling": ("threshold", "3 x 10 min at sustained hard effort, 5 min easy between"),
    "swimming": ("intervals", "8 x 100 m at strong effort with 30 s rest"),
    "rowing": ("intervals", "6 x 4 min strong with 2 min easy"),
    "strength training": ("strength", "3 x 6-8 reps at RPE 7 on main lifts"),
    "yoga / mobility": ("mobility", "Full-body mobility flow"),
    "team sport": ("cross-training", "Skills and game play"),
    "walking / hiking": ("long", "Steady hike on rolling terrain"),
    "triathlon": ("threshold", "Bike 3 x 8 min strong, then 10 min easy run"),
}


def _primary_sports(context: dict) -> list[str]:
    sports = [
        entry["sport"]
        for entry in (context.get("profile", {}).get("sports") or [])
        if entry.get("priority") != "secondary"
    ]
    if sports:
        return sports
    volume = context.get("profile", {}).get("current_weekly_volume")
    if isinstance(volume, dict) and volume:
        return list(volume.keys())
    return ["Running"]


def _spread_days(day_count: int) -> list[int]:
    """Spread N training days across a 7-day week, keeping rest between them."""
    layouts = {
        1: [2],
        2: [1, 4],
        3: [1, 3, 5],
        4: [0, 2, 4, 6],
        5: [0, 1, 3, 4, 6],
        6: [0, 1, 2, 3, 4, 6],
        7: [0, 1, 2, 3, 4, 5, 6],
    }
    return layouts.get(max(1, min(7, day_count)), [1, 3, 5])


def build_template_week(
    context: dict, safety: dict, week_start: date, today: date | None = None
) -> dict:
    sports = _primary_sports(context)
    days = safety["max_days_per_week"]
    offsets = _spread_days(days)
    today = today or date.today()
    remaining = [offset for offset in offsets if week_start + timedelta(days=offset) >= today]
    if not remaining:
        remaining = [max(0, (today - week_start).days)]
    session_minutes = min(
        safety["max_session_minutes"],
        max(20, round(safety["max_weekly_minutes"] / max(1, days))),
    )
    long_minutes = min(safety["max_session_minutes"], round(session_minutes * 1.4))
    readiness = safety["readiness"]
    hard_budget = safety["max_hard_sessions"]
    quality_slot = remaining[len(remaining) // 2] if len(remaining) > 1 else None

    workouts = []
    for index, offset in enumerate(remaining):
        sport = sports[index % len(sports)]
        sport_key = sport.lower()
        is_last = index == len(remaining) - 1
        session_date = week_start + timedelta(days=offset)

        if index == 0 and readiness["action"] != "proceed":
            workouts.append(
                {
                    "date": session_date.isoformat(),
                    "sport": sport,
                    "title": "Recovery session",
                    "session_type": "easy" if readiness["action"] == "downgrade_to_easy" else "mobility",
                    "duration_min": max(20, round(session_minutes * 0.6)),
                    "intensity": "Recovery",
                    "description": f"{readiness['reason']} Keep this genuinely easy and reassess tomorrow.",
                    "structure": [],
                }
            )
            continue

        if hard_budget > 0 and offset == quality_slot:
            session_type, detail = QUALITY_BY_SPORT.get(
                sport_key, ("tempo", "Sustained moderate-hard effort with easy recovery")
            )
            hard_budget -= 1
            workouts.append(
                {
                    "date": session_date.isoformat(),
                    "sport": sport,
                    "title": f"{sport} quality session",
                    "session_type": session_type,
                    "duration_min": session_minutes,
                    "intensity": "Hard / controlled",
                    "description": f"10 min easy warm-up, {detail}, 10 min easy cool-down.",
                    "structure": [
                        {"segment": "Warm-up", "duration_min": 10, "intensity": "Easy"},
                        {
                            "segment": "Main set",
                            "duration_min": max(10, session_minutes - 20),
                            "intensity": "Hard",
                        },
                        {"segment": "Cool-down", "duration_min": 10, "intensity": "Easy"},
                    ],
                }
            )
            continue

        if is_last and sport_key in ENDURANCE_SPORTS and days > 2:
            workouts.append(
                {
                    "date": session_date.isoformat(),
                    "sport": sport,
                    "title": f"Long {sport.lower()} session",
                    "session_type": "long",
                    "duration_min": long_minutes,
                    "intensity": "Easy / conversational",
                    "description": "Steady aerobic effort you could hold a conversation through. "
                    "Fuel and hydrate if it runs past 75 minutes.",
                    "structure": [],
                }
            )
            continue

        if sport_key == "strength training":
            workouts.append(
                {
                    "date": session_date.isoformat(),
                    "sport": sport,
                    "title": "Full-body strength",
                    "session_type": "strength",
                    "duration_min": session_minutes,
                    "intensity": "RPE 6-7",
                    "description": "Squat pattern, hinge pattern, push, pull, carry — 3 sets of 8-12 "
                    "reps at RPE 6-7 with 90 s rest.",
                    "structure": [],
                }
            )
            continue

        workouts.append(
            {
                "date": session_date.isoformat(),
                "sport": sport,
                "title": f"Easy {sport.lower()}",
                "session_type": "easy",
                "duration_min": session_minutes,
                "intensity": "Easy / conversational",
                "description": "Conversational effort throughout. Finish feeling like you could "
                "repeat it tomorrow.",
                "structure": [],
            }
        )

    goal = context.get("profile", {}).get("primary_goal") or "general fitness"
    return {
        "title": f"Week of {week_start.strftime('%b %d')}",
        "summary": (
            f"{len(workouts)} sessions across {', '.join(sports)} aimed at {goal}, sized to "
            f"{safety['max_weekly_minutes']} minutes and your recent training load."
        ),
        "focus": "Consistency and aerobic base"
        if safety["max_hard_sessions"] == 0
        else "Aerobic base with one quality session",
        "week_start": week_start.isoformat(),
        "workouts": workouts,
        "coach_notes": (
            "Built from your profile and safety rules without an AI provider configured. "
            "Set AI_PROVIDER and an API key for personalised generation."
        ),
        "citations": [],
    }


def build_template_advice(context: dict, safety: dict) -> dict:
    readiness = safety["readiness"]
    load = safety["load"]
    if readiness["action"] == "rest_or_mobility":
        headline = "Take today easy or off"
        recommendation = (
            "Rest, walk, or do 20-30 minutes of mobility. Two or more recovery markers are "
            "down, so training hard today buys fatigue rather than fitness."
        )
        adjustment = "Replace today's session with rest or mobility."
    elif readiness["action"] == "downgrade_to_easy":
        headline = "Keep today conversational"
        recommendation = (
            "Do the planned duration at an easy, conversational effort and skip any intervals. "
            "Reassess tomorrow before adding intensity."
        )
        adjustment = "Convert any quality work to easy aerobic work at the same duration."
    else:
        headline = "Cleared to train as planned"
        recommendation = (
            "Recovery markers look normal, so train as scheduled. Warm up for 10 minutes and "
            "stop the session if anything sharp shows up."
        )
        adjustment = None

    rationale_parts = [readiness["reason"]]
    if load["minutes_acwr"]:
        rationale_parts.append(
            f"Last 7 days: {load['acute_minutes']} min vs {load['chronic_minutes']} min/week "
            f"28-day average (ratio {load['minutes_acwr']})."
        )
    if safety["injuries"]["active"]:
        rationale_parts.append(
            f"Active injuries on file: {', '.join(safety['injuries']['active'])}."
        )

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": " ".join(rationale_parts),
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def template_chat_reply(question: str, safety: dict, science_hits: list[dict]) -> dict:
    readiness = safety["readiness"]
    lines = [
        "No AI provider is configured, so here is what your data and the coaching rules say.",
        f"Readiness: {readiness['reason']}",
        f"This week's limits: up to {safety['max_days_per_week']} training days, "
        f"{safety['max_weekly_minutes']} total minutes, "
        f"{safety['max_hard_sessions']} hard session(s).",
    ]
    if safety["injuries"]["active"]:
        lines.append(
            f"Active injuries ({', '.join(safety['injuries']['active'])}) mean avoiding "
            f"{', '.join(safety['injuries']['avoid_keywords']) or 'high-impact loading'}."
        )
    if science_hits:
        top = science_hits[0]
        lines.append(f"Relevant guidance — {top['heading']}: {top['body']}")
    return {
        "reply": "\n\n".join(lines),
        "citations": [hit["citation"]["slug"] for hit in science_hits[:2] if hit["citation"]["slug"]],
        "escalate": False,
        "escalation_reason": None,
    }
