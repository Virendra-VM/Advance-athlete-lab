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


def build_template_hrv_brief(context: dict, safety: dict, hrv: dict) -> dict:
    last = hrv.get("hrv")
    usual = hrv.get("avg_7d")
    ratio = hrv.get("ratio_vs_usual")
    assessment = hrv.get("hrv_assessment") or "unlabelled"
    metric_line = (
        f"Last night {last} ms vs 7-day usual {usual} ms"
        + (f" ({ratio}× usual, {assessment})." if ratio is not None else f" ({assessment}).")
    )

    if last is None:
        headline = "Need an overnight HRV recording"
        recommendation = (
            "HRV on this page is last night’s milliseconds versus your own 7-day usual. Until a night records, there is no number to read.\n"
            "1. Wear the watch overnight — next recording\n"
            "- Metric: overnight HRV in ms\n"
            "- Compare: your usual, not someone else’s ms"
        )
        adjustment = "This brief stays on HRV until a night lands."
    elif assessment and "unbalanced" in str(assessment).lower():
        headline = "HRV reads unbalanced versus usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read last night as suppressed HRV — ms only\n"
            f"- Last night: {last} ms\n"
            "- COROS: unbalanced"
        )
        adjustment = "Stay on this HRV reading until nights return toward 1.0× usual."
    elif ratio is not None and ratio < 0.9:
        headline = "Last night’s HRV sat below usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Treat this as a low HRV night — milliseconds only\n"
            f"- Last night: {last} ms\n"
            f"- Usual: {usual} ms"
        )
        adjustment = "A suppressed HRV night is the story on this page. Nothing else."
    elif ratio is not None and ratio < 0.95:
        headline = "HRV a little below recent nights"
        recommendation = (
            f"{metric_line}\n"
            "1. Note a small dip in overnight HRV\n"
            f"- Ratio: {ratio}× usual\n"
            "- Watch: the next HRV night, not other metrics"
        )
        adjustment = "One dip is often noise in HRV. Two or three low nights is a streak on this chart."
    elif ratio is not None and ratio > 1.08:
        headline = "HRV above your usual night"
        recommendation = (
            f"{metric_line}\n"
            "1. Read this as a higher HRV night than usual\n"
            f"- Last night: {last} ms\n"
            f"- Usual: {usual} ms"
        )
        adjustment = "Above-usual HRV is the only call on this page."
    else:
        headline = "HRV is around your usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Last night matched your recent HRV\n"
            f"- Last night: {last} ms\n"
            f"- Usual: {usual} ms"
        )
        adjustment = "Typical HRV is the useful zone on this page — not a call about anything else."

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": metric_line,
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def build_template_stress_brief(context: dict, safety: dict, stress: dict) -> dict:
    last = stress.get("stress")
    usual = stress.get("avg_7d")
    ratio = stress.get("ratio_vs_usual")
    high_absolute = bool(stress.get("high_absolute"))
    metric_line = (
        f"Today’s stress {last} vs 7-day usual {usual}"
        + (f" ({ratio}× usual)." if ratio is not None else ".")
    )

    if last is None:
        headline = "Need a daily stress recording"
        recommendation = (
            "Stress on this page is the all-day average versus your own 7-day usual. Until a day records, there is no number to read.\n"
            "1. Wear the watch through the day — next recording\n"
            "- Metric: daily average stress\n"
            "- Compare: your usual, not someone else’s 0–100"
        )
        adjustment = "This brief stays on stress until a day lands."
    elif high_absolute or (ratio is not None and ratio >= 1.25):
        headline = "Stress is high versus your usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read today as a high stress day on this chart\n"
            f"- Today: {last}\n"
            f"- Usual: {usual}"
        )
        adjustment = "A 70+ day or 1.25× usual is the stress story. Nothing else."
    elif ratio is not None and ratio >= 1.1:
        headline = "Stress sits above your recent days"
        recommendation = (
            f"{metric_line}\n"
            "1. Note an elevated stress day versus usual\n"
            f"- Ratio: {ratio}× usual\n"
            "- Watch: the next stress day on this page"
        )
        adjustment = "Elevated versus usual is the only call here."
    elif ratio is not None and ratio < 0.9:
        headline = "A quieter stress day than usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read today as below your usual stress\n"
            f"- Today: {last}\n"
            f"- Usual: {usual}"
        )
        adjustment = "Quiet stress is the story on this page — not a call about anything else."
    else:
        headline = "Stress is around your usual day"
        recommendation = (
            f"{metric_line}\n"
            "1. Today matched your recent stress average\n"
            f"- Today: {last}\n"
            f"- Usual: {usual}"
        )
        adjustment = "Typical stress is the useful zone on this page."

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": metric_line,
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def build_template_rhr_brief(context: dict, safety: dict, rhr: dict) -> dict:
    last = rhr.get("resting_heart_rate")
    usual = rhr.get("avg_7d")
    ratio = rhr.get("ratio_vs_usual")
    delta = rhr.get("delta_bpm")
    elevated_rise = bool(rhr.get("elevated_rise"))
    rise_soft = bool(rhr.get("rise_soft"))
    delta_bit = (
        f", {delta:+.0f} bpm"
        if isinstance(delta, (int, float)) and abs(delta) >= 0.5
        else ""
    )
    metric_line = (
        f"Last night {last} bpm vs 7-day usual {usual} bpm"
        + (f" ({ratio}× usual{delta_bit})." if ratio is not None else ".")
    )

    if last is None:
        headline = "Need an overnight resting HR recording"
        recommendation = (
            "Resting HR on this page is overnight bpm versus your own 7-day usual. Until a night records, there is no number to read.\n"
            "1. Wear the watch overnight — next recording\n"
            "- Metric: resting HR in bpm\n"
            "- Compare: your usual, not someone else’s bpm"
        )
        adjustment = "This brief stays on resting HR until a night lands."
    elif elevated_rise or (ratio is not None and ratio >= 1.08):
        headline = "Resting HR is up versus usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read last night as elevated resting HR\n"
            f"- Last night: {last} bpm\n"
            f"- Usual: {usual} bpm"
        )
        adjustment = "A rise of about 7 bpm or 1.08× usual is the resting-HR story. Nothing else."
    elif rise_soft or (ratio is not None and ratio >= 1.05):
        headline = "Resting HR a few beats above usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Note a small rise in overnight resting HR\n"
            f"- Ratio: {ratio}× usual\n"
            "- Watch: the next resting-HR night on this page"
        )
        adjustment = "A little high versus usual is the only call here."
    elif ratio is not None and ratio < 0.97:
        headline = "Resting HR quieter than usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read last night as below your usual bpm\n"
            f"- Last night: {last} bpm\n"
            f"- Usual: {usual} bpm"
        )
        adjustment = "Below-usual resting HR is the story on this page."
    else:
        headline = "Resting HR is around your usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Last night matched your recent resting HR\n"
            f"- Last night: {last} bpm\n"
            f"- Usual: {usual} bpm"
        )
        adjustment = "Typical resting HR is the useful zone on this page."

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": metric_line,
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def build_template_daily_brief(context: dict, safety: dict, daily: dict) -> dict:
    last = daily.get("steps")
    usual = daily.get("avg_7d_steps")
    ratio = daily.get("ratio_vs_usual")
    sedentary = bool(daily.get("sedentary"))
    calories = daily.get("calories")
    avg_hr = daily.get("avg_heart_rate")
    cal_bit = f" Calories {int(calories)}." if isinstance(calories, (int, float)) else ""
    hr_bit = f" Day-average HR {int(avg_hr)} bpm." if isinstance(avg_hr, (int, float)) else ""
    metric_line = (
        f"Today {int(last) if last is not None else last} steps vs 7-day usual {int(usual) if usual is not None else usual}"
        + (f" ({ratio}× usual)." if ratio is not None else ".")
        + cal_bit
        + hr_bit
    )

    if last is None:
        headline = "Need a daily steps recording"
        recommendation = (
            "Daily health on this page is steps versus your own 7-day usual, with calories and day-average HR as companions. Until a day records, there is no number to read.\n"
            "1. Wear the watch through the day — next recording\n"
            "- Metric: daily steps\n"
            "- Compare: your usual, not someone else’s 10,000"
        )
        adjustment = "This brief stays on daily health until a day lands."
    elif sedentary or (ratio is not None and ratio < 0.75):
        headline = "Steps sit below your usual day"
        recommendation = (
            f"{metric_line}\n"
            "1. Read today as a quiet step day on this chart\n"
            f"- Today: {int(last) if last is not None else last} steps\n"
            f"- Usual: {int(usual) if usual is not None else usual} steps"
        )
        adjustment = "Quiet versus usual, or under 5,000 steps, is the daily-health story. Nothing else."
    elif ratio is not None and ratio >= 1.5:
        headline = "Steps spiked versus your usual"
        recommendation = (
            f"{metric_line}\n"
            "1. Read today as a very high step day versus usual\n"
            f"- Today: {int(last)} steps\n"
            f"- Usual: {int(usual) if usual is not None else usual} steps"
        )
        adjustment = "A 1.50× step day is the story on this page."
    elif ratio is not None and ratio >= 1.2:
        headline = "More steps than your usual day"
        recommendation = (
            f"{metric_line}\n"
            "1. Note a busy step day versus usual\n"
            f"- Ratio: {ratio}× usual\n"
            "- Companions: calories and day-average HR on this page only"
        )
        adjustment = "Busy versus usual is the daily-health call. Nothing else."
    else:
        headline = "Steps are around your usual day"
        recommendation = (
            f"{metric_line}\n"
            "1. Today matched your recent step average\n"
            f"- Today: {int(last)} steps\n"
            f"- Usual: {int(usual) if usual is not None else usual} steps"
        )
        adjustment = "Typical steps are the useful zone on this page."

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": metric_line,
        "citations": [],
        "escalate": False,
        "escalation_reason": None,
    }


def build_template_sleep_brief(context: dict, safety: dict, sleep: dict) -> dict:
    last = sleep.get("sleep_duration_min")
    usual = sleep.get("avg_7d_min")
    ratio = sleep.get("ratio_vs_usual")
    score = sleep.get("sleep_score")
    deep = sleep.get("deep_sleep_pct")
    rem = sleep.get("rem_sleep_pct")
    nap = sleep.get("nap_duration_min")
    metric_line = (
        f"Last night {last} min vs 7-day usual {usual} min"
        + (f" ({ratio}× usual)." if ratio is not None else ".")
        + (f" Score {int(score)}." if isinstance(score, (int, float)) else "")
    )
    extras = []
    if isinstance(deep, (int, float)):
        extras.append(f"Deep {deep:.0f}%")
    if isinstance(rem, (int, float)):
        extras.append(f"REM {rem:.0f}%")
    if isinstance(nap, (int, float)) and nap > 0:
        extras.append(f"Nap {int(nap)} min")
    extra_line = f" {' · '.join(extras)}." if extras else ""

    if last is None:
        headline = "Need an overnight sleep recording"
        recommendation = (
            "Sleep on this page is last night’s duration, stages, and naps versus your own 7-day usual. Until a night records, there is no number to read.\n"
            "1. Wear the watch overnight — next recording\n"
            "- Metric: time asleep in minutes\n"
            "- Compare: your usual night, not someone else’s hours"
        )
        adjustment = "This brief stays on sleep until a night lands."
    elif (ratio is not None and ratio < 0.85) or (isinstance(last, (int, float)) and last < 360):
        headline = "Last night was shorter than usual"
        recommendation = (
            f"{metric_line}{extra_line}\n"
            "1. Read last night as a short sleep versus your usual\n"
            f"- Last night: {last} min\n"
            f"- Usual: {usual} min"
        )
        adjustment = "Short versus usual is the sleep story on this page. Nothing else."
    elif ratio is not None and ratio > 1.1:
        headline = "Longer sleep than your usual night"
        recommendation = (
            f"{metric_line}{extra_line}\n"
            "1. Read last night as above your usual duration\n"
            f"- Last night: {last} min\n"
            f"- Usual: {usual} min"
        )
        adjustment = "Above-usual sleep duration is the only call here."
    else:
        headline = "Sleep is around your usual night"
        recommendation = (
            f"{metric_line}{extra_line}\n"
            "1. Last night matched your recent sleep duration\n"
            f"- Last night: {last} min\n"
            f"- Usual: {usual} min"
        )
        adjustment = "Typical sleep duration is the useful zone on this page."

    return {
        "headline": headline,
        "recommendation": recommendation,
        "session_adjustment": adjustment,
        "rationale": metric_line,
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
