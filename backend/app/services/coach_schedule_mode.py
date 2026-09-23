"""Schedule response modes — action summary vs full coach report.

Phase 0/1: detect replan-with-zones requests, build library weeks deterministically,
diff against the current plan, and narrate with a concise WHAT CHANGED block.

Phase 3: two-pass for every SCHEDULE_UPDATE — pass 1 planner packet (library + zones),
pass 2 LLM narrator only (temp 0.7); week_plan always comes from pass 1.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, timedelta
from typing import Any

FULL_REPORT = "full_report"
ACTION_SUMMARY = "action_summary"

_ACTION_PATTERNS = (
    r"\bplan(?:\s+\w+){0,4}\s+(?:this|my)\s+week\s+again\b",
    r"\breplan\b",
    r"\bplan again\b",
    r"\bworkout library\b",
    r"\bnew(?:ly)?\s+(?:add(?:ed)?\s+)?(?:ftp|lthr|max\s*hr|resting\s*hr|zones?)\b",
    r"\bupdated?\s+(?:ftp|lthr|zones?|anchors?|workout library)\b",
    r"\bkeep(?:\s+the)?\s+schedule\s+same\b",
    r"\bsame\s+schedule\b",
    r"\bnew zones\b",
    r"\bzone anchors\b",
    r"\brebuild(?:\s+this)?\s+week\b",
)

_SAME_SCHEDULE_PATTERN = re.compile(
    r"\b(keep(?:\s+the)?\s+schedule\s+same|same\s+schedule|schedule\s+unchanged|same\s+days)\b",
    re.IGNORECASE,
)


def detect_schedule_response_mode(message: str) -> str:
    """Return ACTION_SUMMARY for replan / zone-refresh requests; else FULL_REPORT."""
    text = (message or "").lower()
    if any(re.search(pattern, text) for pattern in _ACTION_PATTERNS):
        return ACTION_SUMMARY
    return FULL_REPORT


def wants_same_schedule(message: str) -> bool:
    return bool(_SAME_SCHEDULE_PATTERN.search(message or ""))


def format_physiology_anchor_lines(context: dict | None) -> list[str]:
    physiology = (context or {}).get("physiology") or {}
    lines: list[str] = []
    ftp = physiology.get("ftp_watts") or physiology.get("ftp_estimated_watts")
    if ftp:
        src = physiology.get("ftp_source") or "profile"
        lines.append(f"**FTP:** {ftp} W ({src})")
    lthr = physiology.get("lthr_bpm")
    if lthr:
        lines.append(f"**LTHR:** {lthr} bpm")
    max_hr = physiology.get("max_hr_bpm")
    if max_hr:
        lines.append(f"**Max HR:** {max_hr} bpm")
    rest_hr = physiology.get("resting_hr_bpm")
    if rest_hr:
        lines.append(f"**Resting HR:** {rest_hr} bpm")
    tp = physiology.get("threshold_pace_sec_per_km")
    if tp:
        lines.append(f"**Threshold pace:** {_pace_label(tp)}")
    css = physiology.get("css_sec_per_100m")
    if css:
        lines.append(f"**CSS:** {_pace_label(css, per_100m=True)}")
    vo2 = physiology.get("vo2max")
    if vo2:
        lines.append(f"**VO₂max:** {vo2}")
    return lines


def _pace_label(seconds: float | int, *, per_100m: bool = False) -> str:
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return str(seconds)
    minutes, secs = divmod(total, 60)
    unit = "/100m" if per_100m else "/km"
    return f"{minutes}:{secs:02d}{unit}"


def _workout_key(workout: dict) -> str:
    return str(workout.get("date") or "")[:10]


def _intensity_blob(workout: dict) -> str:
    parts = [
        str(workout.get("intensity") or ""),
        str(workout.get("description") or ""),
    ]
    for segment in workout.get("structure") or []:
        if isinstance(segment, dict):
            parts.append(str(segment.get("detail") or ""))
            parts.append(str(segment.get("intensity") or ""))
    return " ".join(parts).lower()


def diff_week_plans(
    old_workouts: list[dict] | None,
    new_workouts: list[dict] | None,
) -> dict[str, Any]:
    """Compare workouts by date — session/intensity/zone detail changes."""
    old_by_date = {_workout_key(item): item for item in (old_workouts or []) if _workout_key(item)}
    new_by_date = {_workout_key(item): item for item in (new_workouts or []) if _workout_key(item)}
    all_dates = sorted(set(old_by_date) | set(new_by_date))

    changes: list[dict[str, str]] = []
    unchanged_days = 0
    for iso in all_dates:
        old = old_by_date.get(iso)
        new = new_by_date.get(iso)
        day_name = _weekday_name(iso)
        if old and not new:
            changes.append(
                {
                    "day": day_name,
                    "kind": "removed",
                    "summary": f"{day_name}: removed **{old.get('title') or 'session'}**",
                }
            )
            continue
        if new and not old:
            changes.append(
                {
                    "day": day_name,
                    "kind": "added",
                    "summary": f"{day_name}: added **{new.get('title') or 'session'}**",
                }
            )
            continue
        if not old or not new:
            continue

        old_title = (old.get("title") or "").strip()
        new_title = (new.get("title") or "").strip()
        old_intensity = (old.get("intensity") or "").strip()
        new_intensity = (new.get("intensity") or "").strip()
        old_blob = _intensity_blob(old)
        new_blob = _intensity_blob(new)

        if (
            old_title == new_title
            and old_intensity == new_intensity
            and old_blob == new_blob
        ):
            unchanged_days += 1
            continue

        if old_title != new_title:
            changes.append(
                {
                    "day": day_name,
                    "kind": "session",
                    "summary": f"{day_name}: **{old_title or 'Session'}** → **{new_title or 'Session'}**",
                }
            )
        elif old_intensity != new_intensity:
            changes.append(
                {
                    "day": day_name,
                    "kind": "intensity",
                    "summary": f"{day_name}: intensity **{old_intensity or '—'}** → **{new_intensity or '—'}**",
                }
            )
        else:
            changes.append(
                {
                    "day": day_name,
                    "kind": "zones",
                    "summary": f"{day_name}: **{new_title or 'Session'}** — zone targets updated",
                }
            )

    return {
        "changes": changes,
        "unchanged_days": unchanged_days,
        "total_days": len(all_dates),
        "same_shape": len(changes) == 0 and unchanged_days > 0,
    }


def _weekday_name(iso: str) -> str:
    try:
        parsed = date.fromisoformat(iso[:10])
    except ValueError:
        return iso[:10]
    return parsed.strftime("%A")


def format_what_changed_section(
    diff: dict[str, Any],
    physiology_lines: list[str],
    *,
    same_schedule: bool = False,
) -> list[str]:
    lines = ["📊 **WHAT CHANGED**"]
    if physiology_lines:
        lines.append("**Your anchors now drive the sessions:**")
        lines.extend(f"• {line}" for line in physiology_lines)
    changes = diff.get("changes") or []
    if same_schedule and not changes and physiology_lines:
        lines.append(
            "• **Schedule shape:** same days and sessions — intensities rebuilt from your updated anchors."
        )
    elif diff.get("same_shape") and physiology_lines:
        lines.append(
            "• **Sessions:** same layout — zone targets and library structures refreshed."
        )
    elif changes:
        lines.append("**Session updates:**")
        for item in changes[:8]:
            lines.append(f"• {item['summary']}")
        extra = len(changes) - 8
        if extra > 0:
            lines.append(f"• +{extra} more day(s) adjusted")
    elif physiology_lines:
        lines.append("• **Week rebuilt** using the workout library and your profile anchors.")
    else:
        lines.append("• **Week rebuilt** from the science workout library.")
    return lines


def strip_weekly_translations(reply: str) -> str:
    """Remove mandatory-style science triplets from action-summary replies."""
    if not reply:
        return reply
    text = reply
    for marker in ("🔬 WEEKLY TRANSLATIONS", "WEEKLY TRANSLATIONS"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx].rstrip()
    # Drop stray triplet blocks if the model added them anyway.
    lines = text.splitlines()
    cleaned: list[str] = []
    skip_triplet = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("• 🔬 THE SCIENCE:"):
            skip_triplet = True
            continue
        if skip_triplet:
            if stripped.startswith("• 🗣️ LOCKER ROOM LINGO:") or stripped.startswith(
                "• 💡 REAL-WORLD EXAMPLE:"
            ):
                continue
            skip_triplet = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def ensure_what_changed_block(reply: str, what_changed_lines: list[str]) -> str:
    if "WHAT CHANGED" in reply:
        return reply
    block = "\n".join(what_changed_lines)
    if "🟢 TODAY'S CALL" in reply:
        parts = reply.split("🟢 TODAY'S CALL", 1)
        return f"{parts[0].rstrip()}\n\n{block}\n\n🟢 TODAY'S CALL{parts[1]}"
    return f"{block}\n\n{reply}"


def build_proposed_schedule_week(
    *,
    context: dict,
    safety: dict,
    clock: dict,
    current_plan: dict | None,
    message: str,
) -> dict[str, Any]:
    """Pass 1 — deterministic week from athlete DIY, executed days, or library."""
    from app.services.coach_safety import validate_plan
    from app.services.diy_week_parser import (
        executed_by_day_from_context,
        has_diy_week_proposal,
        merge_week_workouts,
        parse_diy_week_from_message,
        soft_cap_today_only,
        workouts_from_executed,
    )
    from app.services.session_blueprints import enrich_plan
    from app.services.workout_library import physiology_from_context
    from app.services.workout_selection import (
        apply_library_selection_to_plan,
        build_library_week,
    )

    week_start = clock["week_start"]
    today = clock.get("today") or date.today()
    physiology = physiology_from_context(context)
    diy_workouts = parse_diy_week_from_message(message, clock) if message else []
    diy_mode = bool(diy_workouts) or has_diy_week_proposal(message or "")

    executed = executed_by_day_from_context(
        context,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
    )
    executed_rows = workouts_from_executed(executed, today=today)

    if wants_same_schedule(message) and current_plan and (current_plan.get("plan") or {}).get(
        "workouts"
    ):
        base = copy.deepcopy((current_plan.get("plan") or {}))
        proposed = {
            "title": base.get("title") or f"Week of {week_start.strftime('%b %d')}",
            "summary": "Same schedule — sessions recalibrated to your updated zone anchors.",
            "focus": base.get("focus") or "Zone-calibrated week",
            "week_start": week_start.isoformat(),
            "workouts": [copy.deepcopy(item) for item in base.get("workouts") or []],
            "selection_engine": "swl-v2-rezone",
        }
        proposed = apply_library_selection_to_plan(proposed, context, safety)
    elif diy_mode and diy_workouts:
        # Honor the athlete's day-by-day proposal; fill unspecified open days from library.
        library = build_library_week(context, safety, week_start, today=today)
        library = apply_library_selection_to_plan(library, context, safety)
        current_rows = list(((current_plan or {}).get("plan") or {}).get("workouts") or [])
        claimed = {
            str(item.get("date") or "")[:10]
            for item in (executed_rows + diy_workouts)
            if str(item.get("date") or "")[:10]
        }
        executed_dates = {
            str(item.get("date") or "")[:10]
            for item in executed_rows
            if str(item.get("date") or "")[:10]
        }
        # Prefer COROS/Strava files for past days — drop DIY "I did X" duplicates.
        diy_kept = [
            item
            for item in diy_workouts
            if str(item.get("date") or "")[:10] not in executed_dates
        ]
        library_kept = [
            item
            for item in (library.get("workouts") or [])
            if str(item.get("date") or "")[:10] not in claimed
        ]
        # Keep past planned days that have no file yet (honest Missed), not library ghosts.
        past_planned = []
        for item in current_rows:
            iso = str(item.get("date") or "")[:10]
            if not iso or iso in claimed:
                continue
            try:
                day = date.fromisoformat(iso)
            except ValueError:
                continue
            if day < today:
                past_planned.append(copy.deepcopy(item))
        seed = past_planned + library_kept + executed_rows + diy_kept
        seed = soft_cap_today_only(seed, safety, today=today)
        proposed = {
            "title": f"Athlete week of {week_start.strftime('%b %d')}",
            "summary": "Week built from your proposed sessions — today soft-capped if readiness is red.",
            "focus": "athlete-proposed calendar",
            "week_start": week_start.isoformat(),
            "workouts": seed,
            "selection_engine": "diy-v1",
            "diy_honored": True,
        }
    else:
        proposed = build_library_week(context, safety, week_start, today=today)
        proposed = apply_library_selection_to_plan(proposed, context, safety)
        # Stamp past executed files so the table is Done, not Missed/Unplanned.
        if executed_rows:
            proposed["workouts"] = merge_week_workouts(
                base=list(proposed.get("workouts") or []),
                overlay=executed_rows,
                today=today,
            )
        proposed["workouts"] = soft_cap_today_only(
            list(proposed.get("workouts") or []),
            safety,
            today=today,
        )

    proposed["week_start"] = week_start.isoformat()
    validation = validate_plan(proposed, safety)
    proposed = enrich_plan(validation["plan"], safety, physiology=physiology)
    if diy_mode:
        proposed["diy_honored"] = True
        proposed["focus"] = proposed.get("focus") or "athlete-proposed calendar"
    return proposed


def build_week_table_rows(
    plan_data: dict,
    *,
    clock: dict | None = None,
    context: dict | None = None,
) -> list[str]:
    """Markdown table rows for REVISED WEEK section."""
    from app.services.ai_coach import _secret_rule
    from app.services.diy_week_parser import executed_by_day_from_context

    weekdays = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    week_start = (clock or {}).get("week_start")
    today = (clock or {}).get("today")
    by_date: dict[str, list[dict]] = {}
    for workout in plan_data.get("workouts") or []:
        key = _workout_key(workout)
        if not key:
            continue
        by_date.setdefault(key, []).append(workout)

    executed = {}
    if context is not None and week_start is not None:
        executed = executed_by_day_from_context(
            context,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
        )

    rows = [
        "| Day | Session | Primary Focus | Intensity | Coach's Secret Rule |",
        "|---|---|---|---|---|",
    ]
    for index, name in enumerate(weekdays):
        day = week_start + timedelta(days=index) if week_start is not None else None
        iso = day.isoformat() if day is not None else ""
        planned_rows = by_date.get(iso) or []
        workout = planned_rows[0] if planned_rows else {}
        past = bool(today and day and day < today)
        day_executed = executed.get(day) if day is not None else None

        if day_executed:
            names = " + ".join(str(item.get("name") or "Session") for item in day_executed)
            sports = " / ".join(
                sorted(
                    {
                        str(item.get("sport") or "").strip()
                        for item in day_executed
                        if item.get("sport")
                    }
                )
            ) or (workout.get("sport") or "—")
            minutes = sum(item.get("minutes") or 0 for item in day_executed)
            session = names
            focus = sports
            intensity = f"{minutes:.0f} min logged" if minutes else "Completed"
            secret = "Done" if planned_rows else "Unplanned"
        elif past and not workout:
            session = "Unplanned"
            focus = "—"
            intensity = "—"
            secret = "Missed"
        elif len(planned_rows) > 1:
            session = " + ".join(
                str(item.get("title") or item.get("session_type") or "Session")
                for item in planned_rows
            )
            focus = " / ".join(
                sorted(
                    {
                        str(item.get("sport") or item.get("session_type") or "").strip()
                        for item in planned_rows
                        if item.get("sport") or item.get("session_type")
                    }
                )
            ) or "—"
            intensity = workout.get("intensity") or workout.get("session_type") or "—"
            secret = _secret_rule(workout, session, intensity, past=past)
        else:
            session = workout.get("title") or workout.get("session_type") or "Unplanned"
            focus = workout.get("sport") or workout.get("session_type") or "—"
            intensity = workout.get("intensity") or workout.get("session_type") or "—"
            secret = _secret_rule(workout, session, intensity, past=past)

        rows.append(f"| {name} | {session} | {focus} | {intensity} | {secret} |")
    return rows


def extract_risk_flags(
    safety: dict,
    context: dict | None,
    *,
    proposed_plan: dict | None = None,
) -> list[str]:
    """Pass-1 risk flags for the narrator — load, readiness, injury, spine."""
    from app.services.coach_safety import has_spine_lock
    from app.services.coach_voice import readiness_is_red

    flags: list[str] = []
    load = safety.get("load") or {}
    acwr = load.get("minutes_acwr")
    if isinstance(acwr, (int, float)):
        if acwr >= 1.5:
            flags.append(f"ACWR critical ({acwr:.2f}) — quality work vetoed")
        elif acwr >= 1.3:
            flags.append(f"ACWR elevated ({acwr:.2f}) — cap hard sessions")
    if readiness_is_red(safety, context):
        flags.append("Readiness below 65 — REST / RESTORE band")
    injuries = safety.get("injuries") or {}
    if injuries.get("has_severe_active"):
        flags.append("Severe active injury — no intensity without clearance")
    if has_spine_lock(injuries):
        flags.append("Spine lock active — no loaded spinal flexion")
    directive = (safety.get("readiness") or {}).get("action")
    if directive and directive != "proceed":
        flags.append(f"Readiness directive: {directive}")
    if proposed_plan:
        hard_count = sum(
            1
            for workout in proposed_plan.get("workouts") or []
            if str(workout.get("session_type") or "").lower()
            in {"tempo", "threshold", "intervals", "hills", "speed", "race"}
        )
        max_hard = int(safety.get("max_hard_sessions") or 2)
        if hard_count > max_hard:
            flags.append(f"Plan has {hard_count} hard sessions; cap is {max_hard}")
    return flags


def build_planner_packet(
    *,
    proposed_plan: dict,
    schedule_diff: dict,
    physiology_lines: list[str],
    safety: dict,
    context: dict | None,
    schedule_mode: str,
    message: str,
) -> dict[str, Any]:
    """Pass 1 — structured planner output for pass-2 narrator (no LLM)."""
    changed_fields = [item.get("summary") or "" for item in (schedule_diff.get("changes") or [])]
    return {
        "intent": "SCHEDULE_UPDATE",
        "response_mode": schedule_mode,
        "week_plan": proposed_plan,
        "changed_fields": [field for field in changed_fields if field],
        "risk_flags": extract_risk_flags(safety, context, proposed_plan=proposed_plan),
        "diff": schedule_diff,
        "physiology_anchors": physiology_lines,
        "same_schedule_requested": wants_same_schedule(message),
        "selection_engine": proposed_plan.get("selection_engine"),
        "workout_count": len(proposed_plan.get("workouts") or []),
    }


def build_schedule_narrator_block(
    *,
    schedule_mode: str,
    planner_packet: dict,
    proposed_plan: dict,
    schedule_diff: dict,
    physiology_lines: list[str],
    table_rows: list[str],
    today_call_block: str,
    athlete_state_block: str,
    voice_teaching_block: str = "",
) -> str:
    """Pass 2 prompt block — narrator narrates pass-1 ground truth only."""
    mode_label = (
        "action summary (WHAT CHANGED first)"
        if schedule_mode == ACTION_SUMMARY
        else "full Pro Olympic Coach call"
    )
    from app.services.coach_plain_language import plain_language_prompt_block

    lead_rule = (
        "Lead with 📊 WHAT CHANGED using the diff below."
        if schedule_mode == ACTION_SUMMARY
        else "Follow OUTPUT FORMAT: 🟢 TODAY'S CALL, 🗣️ LOCKER ROOM DIRECTIVE, 🗓️ REVISED WEEK, 🛡️ SPINE LOCK."
    )
    diy_honored = bool(proposed_plan.get("diy_honored"))
    diy_rule = ""
    if diy_honored:
        diy_rule = """
ATHLETE DIY WEEK (hard)
- Pass 1 already honored the athlete's proposed days (selection_engine diy-v1).
- Copy those sessions into 🗓️ REVISED WEEK — do NOT replace Sat long / Sun mountain with mobility.
- If readiness is REST/EASY: soft-cap TODAY only. Negotiate future load in prose
  (e.g. "trim Sunday to 2–2.5 h if sleep stays low") — never silently delete proposed days.
- Past days with logged files are Done — never label them Missed.
"""
    block = f"""
{today_call_block}

{athlete_state_block}

ROUTING (hard) — Phase 3 two-pass
Intent is SCHEDULE_UPDATE — pass 2 narrator only ({mode_label}).
Pass 1 already built PLANNER PACKET from the workout library and zone engine.
Do NOT invent sessions, dates, intensities, or zone targets. Narrate pass-1 ground truth only.
Do NOT autopsy a past ride. Skip ⚡ THE BOTTOM LINE, 🔬 MECHANICAL PRECISION, and 🫀 CARDIOVASCULAR COST.
Do NOT add 🔬 WEEKLY TRANSLATIONS or science/lingo/analogy triplets unless CONDITIONAL TEACHING applies.
{lead_rule}
Open with a plain-language lead: decision + one watch number + one why sentence (Phase 4).
Copy week_plan from PLANNER PACKET exactly. Copy PROPOSED WEEK TABLE verbatim into 🗓️ REVISED WEEK.
{diy_rule}
PLANNER PACKET (pass 1 — ground truth)
{json.dumps(planner_packet, indent=2, default=str)}

PROPOSED WEEK PLAN
{json.dumps(proposed_plan, indent=2, default=str)}

PROPOSED WEEK DIFF
{json.dumps(schedule_diff, indent=2, default=str)}

PROPOSED WEEK TABLE (copy verbatim)
{chr(10).join(table_rows)}

PHYSIOLOGY ANCHORS
{chr(10).join(f"- {line}" for line in physiology_lines) or "- (none on file)"}
{voice_teaching_block}
"""
    return block + "\n" + plain_language_prompt_block()


def finalize_schedule_narrator_reply(
    reply: dict,
    *,
    proposed_plan: dict,
    schedule_mode: str,
    schedule_diff: dict,
    physiology_lines: list[str],
    message: str,
    voice=None,
    safety: dict | None = None,
    context: dict | None = None,
    clock: dict | None = None,
) -> dict:
    """Merge pass-1 plan into pass-2 narrator; strip filler; force week_plan."""
    if schedule_mode == ACTION_SUMMARY:
        what_changed = format_what_changed_section(
            schedule_diff,
            physiology_lines,
            same_schedule=wants_same_schedule(message),
        )
        text = strip_weekly_translations(reply.get("reply") or "")
        reply["reply"] = ensure_what_changed_block(text, what_changed)
    else:
        from app.services.coach_voice import finalize_schedule_full_reply

        if voice is not None and safety is not None:
            reply = finalize_schedule_full_reply(reply, voice, safety, context)
        else:
            reply["reply"] = strip_weekly_translations(reply.get("reply") or "")
    from app.services.coach_plain_language import apply_plain_language_reply

    reply = apply_plain_language_reply(
        reply,
        context=context,
        safety=safety,
        proposed_plan=proposed_plan,
        clock=clock,
    )
    reply["week_plan"] = proposed_plan
    reply["intent"] = "SCHEDULE_UPDATE"
    return reply
