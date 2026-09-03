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
            "Recovery markers are down.\n"
            "1. Rest or mobility — 20-30 min\n"
            "- Focus: walk, breathe, restore\n"
            "- Avoid: quality work, heavy loading"
        )
        adjustment = "Replace today's session with rest or mobility."
    elif readiness["action"] == "downgrade_to_easy":
        headline = "Keep today conversational"
        recommendation = (
            "Keep today conversational and skip intervals.\n"
            "1. Easy aerobic — planned duration\n"
            "- Intensity: talk test, no surges\n"
            "- Reassess: add quality only after tomorrow's check-in"
        )
        adjustment = "Convert any quality work to easy aerobic work at the same duration."
    else:
        headline = "Cleared to train as planned"
        recommendation = (
            "Recovery markers look normal — train as scheduled.\n"
            "1. Planned session — as written\n"
            "- Warm-up: 10 minutes\n"
            "- Stop: if anything sharp shows up"
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


def build_template_week_brief(context: dict, safety: dict, distance: dict) -> dict:
    readiness = safety["readiness"]
    acwr = distance.get("acwr")
    acute = distance.get("acute_load_km")
    chronic = distance.get("chronic_load_km")
    load_line = (
        f"Last 7 days {acute} km vs usual week {chronic} km"
        + (f" (ACWR {acwr})." if acwr is not None else ".")
    )

    if readiness["action"] == "rest_or_mobility":
        headline = "Protect the rest of this week"
        recommendation = (
            "Recovery is down — remaining days stay easy or off.\n"
            "1. Easy movement only — 20-40 min\n"
            "- Focus: walk, spin, mobility\n"
            "- Avoid: intervals, long days, chasing weekly km"
        )
        adjustment = "Do not add volume to make the week look complete."
    elif acwr is None:
        headline = "Build a usual week first"
        recommendation = (
            "The load ratio needs a 28-day average before it can warn you about spikes.\n"
            "1. Keep days consistent — planned duration\n"
            "- Focus: repeatable easy-moderate work\n"
            "- Avoid: one catch-up weekend that dumps a month of km"
        )
        adjustment = "Hold weekly distance steady until a usual week exists."
    elif acwr >= 1.5:
        headline = "This week jumped too far"
        recommendation = (
            f"{load_line}\n"
            "1. Cut intensity — remaining sessions easy\n"
            "- Volume: trim the longest day 10-20%\n"
            "- Avoid: new workout types, stacking quality"
        )
        adjustment = "Back off hard work and let the 28-day average catch up."
    elif acwr >= 1.3:
        headline = "Hold the line this week"
        recommendation = (
            f"{load_line}\n"
            "1. Keep planned easy days — as written\n"
            "- Intensity: no new quality\n"
            "- Long session: same or slightly shorter"
        )
        adjustment = "Repeat a similar week rather than adding more kilometres."
    elif acwr < 0.8:
        headline = "A lighter week than your usual"
        recommendation = (
            f"{load_line}\n"
            "1. Easy aerobic — rebuild gradually\n"
            "- Focus: add a little to easy days over 2-3 weeks\n"
            "- Avoid: making up missed km in one weekend"
        )
        adjustment = "Rebuild volume slowly so next week's ratio stays near 1.0."
    else:
        headline = "Building at a useful pace"
        recommendation = (
            f"{load_line}\n"
            "1. Train as planned — quality stays\n"
            "- Progress: distance or intensity, not both\n"
            "- Guardrail: skip stacking a new interval set with a longer long run"
        )
        adjustment = "Keep this week's shape; nudge only one variable next week."

    if readiness["action"] == "downgrade_to_easy" and acwr is not None and acwr < 1.3:
        headline = "Easy week — recovery is the limiter"
        recommendation = (
            "Recovery markers say keep remaining sessions conversational.\n"
            "1. Easy aerobic — planned duration\n"
            "- Intensity: talk test only\n"
            "- Volume: hold kilometres, do not add"
        )
        adjustment = "Convert remaining quality to easy work at the same duration."

    rationale = [readiness["reason"], load_line]
    injuries = (safety.get("injuries") or {}).get("active") or []
    if injuries:
        rationale.append(f"Active injuries on file: {', '.join(injuries)}.")
    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": " ".join(rationale),
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def build_template_load_brief(context: dict, safety: dict, effort: dict) -> dict:
    readiness = safety["readiness"]
    ratio = effort.get("load_ratio")
    short = effort.get("short_load")
    long = effort.get("long_load")
    load_line = (
        f"Short-term load {short} vs long-term {long}"
        + (f" (ratio {ratio})." if ratio is not None else ".")
    )

    if readiness["action"] == "rest_or_mobility":
        headline = "Protect the rest of this week"
        recommendation = (
            "Recovery is down — remaining days stay easy or off, even if the load ratio looks productive.\n"
            "1. Easy movement only — 20-40 min\n"
            "- Focus: walk, spin, mobility\n"
            "- Avoid: intervals, stacking load points"
        )
        adjustment = "Do not add hard sessions to make the week’s effort look complete."
    elif ratio is None:
        headline = "Sync COROS to read effort load"
        recommendation = (
            "Short-term and long-term load come from a COROS sync. Until then this brief cannot say whether recent effort is ramping or spiking.\n"
            "1. Connect and sync COROS — latest week of comments\n"
            "- Focus: heart-rate effort, not kilometres\n"
            "- Avoid: guessing from distance alone"
        )
        adjustment = "Open Training Load after the next COROS sync."
    elif ratio >= 1.5:
        headline = "Recent effort jumped too far"
        recommendation = (
            f"{load_line}\n"
            "1. Cut intensity — remaining sessions easy\n"
            "- Duration: shorten the hardest session\n"
            "- Avoid: new workout types, stacking quality"
        )
        adjustment = "Back off hard work and let long-term load absorb the spike."
    elif ratio >= 1.3:
        headline = "Hold effort here this week"
        recommendation = (
            f"{load_line}\n"
            "1. Keep planned easy days — as written\n"
            "- Intensity: no new quality\n"
            "- Longest session: same or slightly shorter"
        )
        adjustment = "Repeat a similar effort week rather than adding more load."
    elif ratio < 0.8:
        headline = "Quieter than your fitness base"
        recommendation = (
            f"{load_line}\n"
            "1. Easy aerobic — rebuild gradually\n"
            "- Focus: add a little duration to easy days over 2-3 weeks\n"
            "- Avoid: one monster interval day to ‘catch up’"
        )
        adjustment = "Rebuild effort slowly so next week’s ratio stays near 1.0."
    else:
        headline = "Effort is in a useful range"
        recommendation = (
            f"{load_line}\n"
            "1. Train as planned — quality stays\n"
            "- Progress: duration or intensity, not both\n"
            "- Guardrail: skip stacking a new hard session with extra duration"
        )
        adjustment = "Keep this week’s effort shape; nudge only one variable next week."

    if readiness["action"] == "downgrade_to_easy" and ratio is not None and ratio < 1.3:
        headline = "Easy week — recovery is the limiter"
        recommendation = (
            "Recovery markers say keep remaining sessions conversational, even with a calm load ratio.\n"
            "1. Easy aerobic — planned duration\n"
            "- Intensity: talk test only\n"
            "- Load: hold effort, do not add"
        )
        adjustment = "Convert remaining quality to easy work at the same duration."

    rationale = [readiness["reason"], load_line]
    injuries = (safety.get("injuries") or {}).get("active") or []
    if injuries:
        rationale.append(f"Active injuries on file: {', '.join(injuries)}.")
    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": " ".join(rationale),
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


from app.services.ai_coach import template_autopsy


def template_chat_reply(
    question: str,
    safety: dict,
    science_hits: list[dict],
    session_packet: dict | None = None,
    context: dict | None = None,
) -> dict:
    return template_autopsy(
        question,
        safety,
        science_hits,
        session_packet=session_packet,
        context=context,
    )
