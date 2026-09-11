"""Conversational plan advice — answer 'should I do X?' without rebuilding the week.

Athletes proposing a DIY Fri–Sun stack or asking to validate a idea need a coach
conversation, not a REVISED WEEK table dump.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

WEEKDAY_RE = re.compile(
    r"\b("
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|"
    r"mon|tue|tues|wed|thu|thur|fri|sat|sun"
    r")\b",
    re.I,
)

PLAN_ADVICE_RE = re.compile(
    r"\b("
    r"should i use|should i do this|should i go with|should i stick with|"
    r"what do you think|does this (?:plan|schedule) (?:work|make sense|sound)|"
    r"is this (?:plan|schedule) ok|can i do this|tell me should i|"
    r"would this work|good idea to|ok to do|okay to do|"
    r"problem in my plan|any problem in|pros and cons|how can i plan|"
    r"finish the base week|tell me my plan"
    r")\b",
    re.I,
)

DIY_PROPOSAL_RE = re.compile(
    r"\b("
    r"i('ll| will|'m going to)|thinking (?:of|about)|was thinking|"
    r"i plan to|my plan is|stack|then .{0,40} (?:and|then)"
    r")\b",
    re.I,
)

MISSED_OR_ROUGH_RE = re.compile(
    r"\b("
    r"missed|skipped|couldn't make|could not make|busy|not so good|rough day|"
    r"bad day|didn't train|did not train|life got in the way|bike fit"
    r")\b",
    re.I,
)

GO_DEEPER_FOLLOWUP_RE = re.compile(
    r"("
    r"explain why.*(?:plain language|no lecture|watch number|max \d+ bullet)|"
    r"quick follow-up only.*(?:no week table|watch number|max \d+ bullet)"
    r")",
    re.I,
)

SCHEDULE_SECTION_RE = re.compile(
    r"(🟢 TODAY'S CALL|🗣️ LOCKER ROOM DIRECTIVE|🗓️ REVISED WEEK|🛡️ SPINE LOCK|"
    r"🔬 WEEKLY TRANSLATIONS)",
    re.I,
)

TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)

STATUS_LEAD_RE = re.compile(
    r"^(🟢|🟡|🔴)?\s*(PRIMED|CAUTION|REST)\s*/\s*(ACCUMULATE|ABSORB|RESTORE)\s*[—\-].*?(?=\n\n|\Z)",
    re.I | re.S,
)

EMOJI_SECTION_RE = re.compile(
    r"^(🧠 THE CALL|💬 REFRAME|📌 ANSWER|🟢 TODAY'S CALL|🗣️ DIRECTIVE)\s*\n?",
    re.I | re.M,
)

FORMULAIC_LINE_RE = re.compile(
    r"^(Short answer:|Why:|What I'd do instead:|Readiness rule:|You asked:|Watch number:|"
    r"Mostly yes — with three edits|Failed target:?)\s*",
    re.I | re.M,
)

TRANSACTIONAL_VERDICT_RE = re.compile(
    r"^(Honestly\?\s*)?Mostly yes — with (?:three )?edits\b",
    re.I,
)


def is_plan_advice_message(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if not PLAN_ADVICE_RE.search(text):
        return False
    if re.search(r"\b(weekend|this week|next week|fri.?sun|sat.?sun)\b", text, re.I):
        return True
    weekdays = WEEKDAY_RE.findall(text)
    return (
        bool(DIY_PROPOSAL_RE.search(text))
        or bool(MISSED_OR_ROUGH_RE.search(text))
        or len(weekdays) >= 2
        or (
            len(weekdays) >= 1
            and re.search(r"\b(plan|schedule|stack|idea)\b", text, re.I)
        )
    )


def is_go_deeper_followup(message: str) -> bool:
    return bool(GO_DEEPER_FOLLOWUP_RE.search(message or ""))


def strip_schedule_sections(text: str) -> str:
    """Remove schedule-template blocks that leaked into a chat reply."""
    if not text or not SCHEDULE_SECTION_RE.search(text):
        return text
    lines: list[str] = []
    skip = False
    for line in text.splitlines():
        if SCHEDULE_SECTION_RE.search(line):
            skip = True
            continue
        if skip:
            if TABLE_LINE_RE.match(line):
                continue
            if line.strip() == "":
                continue
            if re.match(r"^(DAY|Add week to Schedule|Hide week plan)", line.strip(), re.I):
                continue
            if not line.strip():
                skip = False
                continue
            if not line.strip().startswith("|"):
                skip = False
            else:
                continue
        if TABLE_LINE_RE.match(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def polish_advisory_reply(text: str) -> str:
    """Strip robotic prefaces and template labels from advisory replies."""
    if not text:
        return text
    cleaned = strip_schedule_sections(text)
    cleaned = STATUS_LEAD_RE.sub("", cleaned).strip()
    cleaned = EMOJI_SECTION_RE.sub("", cleaned)
    cleaned = FORMULAIC_LINE_RE.sub("", cleaned)
    cleaned = TRANSACTIONAL_VERDICT_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def finalize_advisory_reply(reply: dict) -> dict:
    reply["reply"] = polish_advisory_reply(reply.get("reply") or "")
    return reply


def _wants_pros_cons(message: str) -> bool:
    return bool(re.search(r"\bpros?(?:\s*(?:and|&|/)\s*cons?)?\b", message or "", re.I))


PROS_SECTION_RE = re.compile(
    r"\n\*\*Pros\*\*[\s\S]*?(?=\n\*\*(?:Cons|The Bottom Line)|\nThe Bottom Line:|\Z)",
    re.I,
)
CONS_SECTION_RE = re.compile(
    r"\n\*\*Cons\*\*[\s\S]*?(?=\n\*\*The Bottom Line|\nThe Bottom Line:|\Z)",
    re.I,
)
MEMORY_BLEED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bike fit", re.compile(r"\bbike fit\b", re.I)),
    ("kolhapur", re.compile(r"\bkolhapur\b", re.I)),
    (
        "train",
        re.compile(r"\b(by train|on the train|train ride|train-travel|train day|traveling by train)\b", re.I),
    ),
    ("travel", re.compile(r"\b(travel(?:ing)? to|destination)\b", re.I)),
)


def strip_pros_cons_unless_requested(text: str, message: str) -> str:
    """Hard gate — no Pros/Cons block unless the athlete asked for it."""
    if _wants_pros_cons(message):
        return text
    cleaned = PROS_SECTION_RE.sub("", text or "")
    cleaned = CONS_SECTION_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def scrub_memory_bleed(
    text: str,
    message: str,
    *,
    thread_text: str = "",
) -> str:
    """Drop lines that mention stale topics not present in the current turn or advisory thread."""
    allowed = f"{message or ''}\n{thread_text or ''}".lower()
    if "long easy run" in allowed:
        threshold_ok = "threshold" in allowed
    else:
        threshold_ok = True

    kept: list[str] = []
    for line in (text or "").splitlines():
        lower_line = line.lower()
        drop = False
        if not threshold_ok and re.search(r"\bthreshold\b", lower_line):
            drop = True
        for label, pattern in MEMORY_BLEED_PATTERNS:
            if label in allowed:
                continue
            if pattern.search(lower_line):
                drop = True
                break
        if not drop:
            kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def pros_cons_guardrail_block(message: str) -> str:
    if _wants_pros_cons(message):
        return "Include explicit **Pros** and **Cons** sections — the athlete asked for trade-offs."
    return (
        "HARD BAN: Do NOT include Pros, Cons, or trade-off sections — "
        "the athlete did NOT ask for pros/cons in this message."
    )


def finalize_plan_advice_reply(reply: dict, message: str) -> dict:
    """Polish + enforce pros/cons gate + scrub memory bleed for plan-advice replies."""
    text = polish_advisory_reply(reply.get("reply") or "")
    text = strip_pros_cons_unless_requested(text, message)
    text = scrub_memory_bleed(text, message)
    reply["reply"] = text
    return reply


def _hard_session_summary(plan: dict | None, clock: dict | None) -> str | None:
    if not plan:
        return None
    hard_types = {"tempo", "threshold", "intervals", "hills", "speed", "race"}
    for workout in (plan.get("plan") or plan).get("workouts") or plan.get("workouts") or []:
        session_type = str(workout.get("session_type") or "").lower()
        intensity = str(workout.get("intensity") or "")
        if session_type not in hard_types and "threshold" not in intensity.lower():
            continue
        title = str(workout.get("title") or "Quality session")
        if intensity and intensity.lower() not in {"none", "—", "-", "easy / conversational"}:
            return f"{title} ({intensity})"
        return title
    return None


def _easy_watts(context: dict | None) -> str:
    physiology = (context or {}).get("physiology") or {}
    ftp = physiology.get("ftp_watts") or physiology.get("ftp_estimated_watts")
    if ftp:
        low = round(float(ftp) * 0.56)
        high = round(float(ftp) * 0.75)
        return f"{low}–{high}W"
    lthr = physiology.get("lthr_bpm")
    if lthr:
        return f"under {round(float(lthr) * 0.83)} bpm"
    return "easy enough to hold a conversation"


def _travel_destination(message: str) -> str | None:
    text = message or ""
    match = re.search(r"\b(?:train|travel(?:ing)?)\s+(?:to|for)\s+([A-Za-z][A-Za-z\s]{2,30})", text, re.I)
    if match:
        return match.group(1).strip().title()
    if "kolhapur" in text.lower():
        return "Kolhapur"
    return None


def _empathy_opening(message: str) -> str:
    text = (message or "").lower()
    if "bike fit" in text:
        return (
            "Hey! First off, take a deep breath — missing today for a proper **bike fit** is a total win, "
            "not a missed target. Getting your posture and pedal stroke dialed in is one of the best "
            "investments you can make to protect your knees and lower back. "
            "Never feel guilty about taking care of your equipment."
        )
    if MISSED_OR_ROUGH_RE.search(message or ""):
        return (
            "Hey — first off, rough days happen. Missing a session when life gets busy isn't failure; "
            "it means the calendar moved, not your fitness. Take a breath before you chase makeup work."
        )
    if "travel" in text or "train" in text:
        return (
            "Travel weeks are tricky — you're juggling logistics and training at the same time. "
            "That's normal, and we can absolutely shape a plan that respects both."
        )
    return (
        "I've looked at what you're proposing against the rest of your week — "
        "and I appreciate you thinking it through before stacking sessions."
    )


def _collaborative_transition(message: str, *, travel_dest: str | None) -> str:
    text = (message or "").lower()
    if travel_dest:
        tail = f"don't step onto that train to **{travel_dest}** with heavy, fatigued legs"
    elif "train" in text or "travel" in text:
        tail = "don't board that train with heavy, fatigued legs"
    else:
        tail = "you stay fresh for what's ahead"
    return (
        "Looking at your proposed plan for the next few days, you've got the **right instincts** — "
        f"but let's make a few quick tweaks so {tail}:"
    )


def _day_block(day_label: str, summary: str, rule: str) -> str:
    return f"**{day_label}:** {summary}\n**Coach's Rule:** {rule}"


def _rest_week_soon(message: str) -> bool:
    return bool(re.search(r"\b(rest week|recovery week|deload)\b", message or "", re.I))


def template_plan_advice(
    message: str,
    safety: dict,
    *,
    current_plan: dict | None = None,
    context: dict | None = None,
    clock: dict | None = None,
) -> dict[str, Any]:
    """Deterministic conversational advice — human coach voice, not a form."""
    load = (safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    hrv = health.get("hrv")

    easy_band = _easy_watts(context)
    text_lower = (message or "").lower()
    travel = bool(
        re.search(r"\b(travel(?:ing)?|by train|on the train|train ride)\b", text_lower)
        or "kolhapur" in text_lower
    )
    travel_dest = _travel_destination(message) if travel else None
    upper_core = bool(re.search(r"\b(upper body|upper/core|core)\b", text_lower))
    endurance_ride = bool(re.search(r"\b(endurance ride|1 hr ride|hour ride)\b", text_lower))
    stacking = (
        ("strength" in text_lower or upper_core)
        and ("bike" in text_lower or "ride" in text_lower or endurance_ride)
    )
    sunday_long_run = bool(re.search(r"\blong easy run\b", text_lower))
    rest_week = _rest_week_soon(message)
    wants_pros_cons = _wants_pros_cons(message)

    if stacking and endurance_ride:
        friday_summary = "Endurance ride (~1 hr) + upper/core after 30–60 min recovery."
        friday_rule = (
            f"Keep the ride strictly aerobic — Zone 2 around **{easy_band}**. "
            "Then upper/core only if you can breathe and talk normally; skip heavy lifting if the legs feel cooked."
        )
    elif stacking:
        friday_summary = "Strength AM + Easy Spin PM."
        friday_rule = (
            f"Keep the afternoon ride strictly in Zone 2 (**{easy_band}**). "
            "Resist the urge to turn it into a makeup threshold ride!"
        )
    else:
        friday_summary = "One focused session — strength or easy bike, not both hard."
        friday_rule = (
            f"If you ride, stay in Zone 2 around **{easy_band}** — conversational, not heroic."
        )

    saturday_mobility = "mobility" in text_lower
    saturday_summary = "Long easy ride" + (" + mobility in the evening." if saturday_mobility else ".")
    saturday_rule = (
        "Keep it conversational. Enjoy the ride, but cap the duration so you aren't completely drained while packing."
        if travel
        else (
            "Keep the ride truly easy — long duration is fine, intensity is not. "
            "Evening mobility only; no extra strength or intervals tacked on."
            if saturday_mobility
            else "Keep it conversational — easy enough to talk the whole way. Don't chase hero distance."
        )
    )

    if travel and not sunday_long_run:
        sunday_label = "Sunday (Travel Day)"
        sunday_summary = "Rest & Recover on the Train."
        sunday_rule = (
            "Skip the long run today. Stacking a long run right before sitting still on a train for hours "
            "will make your legs stiff and trap metabolic waste. Let Sunday be your full recovery day."
        )
    elif sunday_long_run:
        sunday_label = "Sunday"
        sunday_summary = "Long easy run."
        sunday_rule = (
            "Keep it easy — conversational pace, no hero miles. "
            + (
                "Because your rest week starts Monday, cap duration so you enter deload fresh, not flat."
                if rest_week
                else "Don't turn it into a third hard day after Friday's stack and Saturday's long ride."
            )
        )
    else:
        sunday_label = "Sunday"
        sunday_summary = "Easy movement or full rest."
        sunday_rule = "Keep it light — mobility or 30–40 minutes easy. Not another long endurance hit."

    acwr_val = f"**{acwr:.2f}**" if isinstance(acwr, (int, float)) else "healthy"
    hrv_val = f"**{hrv}**" if hrv is not None else "solid"

    if travel and not sunday_long_run:
        dest_phrase = f" at **{travel_dest}**" if travel_dest else " at your destination"
        bottom_line = (
            f"**The Bottom Line:** Your ACWR sits at a healthy {acwr_val} and your HRV is strong at {hrv_val}, "
            f"so your recovery foundation is solid. By resting on Sunday's train ride, you'll absorb Friday and "
            f"Saturday's training and arrive{dest_phrase} completely fresh!"
        )
    elif rest_week:
        bottom_line = (
            f"**The Bottom Line:** ACWR at {acwr_val} and HRV at {hrv_val} — you're close to a clean base-week finish. "
            "Keep Friday's ride easy, Saturday long but conversational, and Sunday's run truly easy so Monday's rest week starts with absorption, not debt."
        )
    else:
        bottom_line = (
            f"**The Bottom Line:** ACWR at {acwr_val} and HRV at {hrv_val} — solid foundation. "
            "Protect easy days so the hard ones land clean."
        )

    body_parts = [
        _empathy_opening(message),
        "",
        _collaborative_transition(message, travel_dest=travel_dest),
        "",
        _day_block("Friday (Tomorrow)", friday_summary, friday_rule),
        "",
        _day_block("Saturday", saturday_summary, saturday_rule),
        "",
        _day_block(sunday_label, sunday_summary, sunday_rule),
    ]

    if wants_pros_cons:
        body_parts.extend(
            [
                "",
                "**Pros:** You finish the base week with sport-specific volume, keep strength in the mix, "
                "and enter rest week with a clear stimulus on each day.",
                "",
                "**Cons:** Friday's ride + upper/core and Saturday long ride stack fatigue — Sunday's long run "
                "only works if Friday's ride stays easy and Saturday doesn't creep into tempo.",
            ]
        )

    body_parts.extend(["", bottom_line])

    reply = polish_advisory_reply("\n\n".join(body_parts))
    return {
        "reply": reply,
        "citations": ["aal-safety-and-load"],
        "escalate": False,
        "escalation_reason": None,
        "intent": "GENERAL_CHAT",
    }


def template_go_deeper_brief(
    safety: dict,
    *,
    current_plan: dict | None = None,
    clock: dict | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """Short why-this-week answer — conversational, no lecture."""
    hard = _hard_session_summary(current_plan, clock)
    load = (safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    easy_band = _easy_watts(context)
    hard_bit = hard or "one quality session"
    acwr_bit = f"**{acwr:.2f}**" if isinstance(acwr, (int, float)) else "steady"

    reply = polish_advisory_reply(
        "\n\n".join(
            [
                f"The shape is simple: **{hard_bit}** is enough hard work for the week — "
                f"everything else stays easy, around **{easy_band}**.",
                f"With load at {acwr_bit}, a second quality day or back-to-back long sessions "
                "costs more than it pays back before a recovery week.",
                "If you can't talk through it, it's too hard. Protect the easy days and the hard one lands clean.",
            ]
        )
    )
    return {
        "reply": reply,
        "citations": ["aal-safety-and-load"],
        "escalate": False,
        "escalation_reason": None,
        "intent": "GENERAL_CHAT",
    }


APPLY_ADVISORY_FOLLOWUP_RE = re.compile(
    r"(?:"
    r"change my plan as per|update my plan as per|update my remaining week|"
    r"update (?:my )?(?:remaining )?week as per|apply (?:those|the|this) (?:changes|updates|plan)|"
    r"as per (?:what we|this|the new|new plan)|as we just discussed|just discussed|discussed right now|"
    r"make those updates|go ahead (?:and|with)|"
    r"update (?:it|the plan|my remaining week) as (?:we|you) (?:said|discussed)|"
    r"put that (?:plan|in)|use that plan|do that plan|yes update|"
    r"change my plan as per this|new plan that we just"
    r")",
    re.I,
)


def _looks_like_apply_request(message: str) -> bool:
    """Broad apply intent — catches phrasing the strict regex may miss."""
    if APPLY_ADVISORY_FOLLOWUP_RE.search(message or ""):
        return True
    text = (message or "").lower()
    wants_update = bool(re.search(r"\b(update|change|apply|put)\b", text))
    refers_back = bool(
        re.search(
            r"\b(remaining week|as per|as we discussed|just discussed|new plan|what we|discuussed)\b",
            text,
        )
    )
    return wants_update and refers_back

ADVISORY_REPLY_MARKERS = ("Coach's Rule:", "The Bottom Line:")


def recent_advisory_thread(history: list[dict] | None) -> dict[str, str] | None:
    """Find the last plan-advice exchange before the current apply message."""
    if not history or len(history) < 2:
        return None
    prior = list(history[:-1])
    for index in range(len(prior) - 1, -1, -1):
        entry = prior[index]
        if entry.get("role") != "assistant":
            continue
        content = entry.get("content") or ""
        if not any(marker in content for marker in ADVISORY_REPLY_MARKERS):
            continue
        plan_message = ""
        for back in range(index - 1, -1, -1):
            if prior[back].get("role") == "user":
                plan_message = prior[back].get("content") or ""
                break
        return {
            "advice_reply": content,
            "plan_message": plan_message,
        }
    return None


def is_apply_advisory_followup(
    message: str,
    history: list[dict] | None = None,
) -> bool:
    """Athlete accepted prior plan advice — patch discussed days, not full rebuild."""
    if not _looks_like_apply_request(message):
        return False
    return recent_advisory_thread(history) is not None


def _weekday_dates(clock: dict) -> dict[str, date]:
    week_start = clock["week_start"]
    return {
        (week_start + timedelta(days=offset)).strftime("%A").lower(): week_start + timedelta(days=offset)
        for offset in range(7)
    }


def _advisory_target_dates(clock: dict, combined_text: str) -> dict[str, date]:
    """Map friday/saturday/sunday labels to calendar dates from the thread."""
    today = clock["today"]
    lower = (combined_text or "").lower()
    weekday_map = _weekday_dates(clock)
    dates: dict[str, date] = {}

    if re.search(r"\bfriday\b|\btoday\b|4pm|endurance ride|1 hr ride", lower):
        if re.search(r"\btoday\b|that'?s it 3 pm|4pm", lower):
            dates["friday"] = today
        else:
            dates["friday"] = weekday_map.get("friday", today)
    if re.search(r"\bsaturday\b|\btomorrow\b", lower):
        dates["saturday"] = (
            today + timedelta(days=1)
            if "tomorrow" in lower
            else weekday_map.get("saturday", today + timedelta(days=1))
        )
    if "sunday" in lower:
        dates["sunday"] = weekday_map.get("sunday", today + timedelta(days=2))
    return dates


def build_advisory_workouts_from_thread(
    thread: dict[str, str],
    clock: dict,
    *,
    context: dict | None = None,
    safety: dict | None = None,
) -> list[dict]:
    """Build concrete workouts for the days discussed in the advisory thread."""
    _ = safety
    combined = f"{thread.get('plan_message') or ''}\n{thread.get('advice_reply') or ''}"
    lower = combined.lower()
    easy_band = _easy_watts(context)
    dates = _advisory_target_dates(clock, combined)
    workouts: list[dict] = []

    friday = dates.get("friday")
    if friday and re.search(r"\b(endurance ride|1 hr ride|hour ride|upper body|upper/core|core)\b", lower):
        if re.search(r"\b(endurance ride|1 hr ride|hour ride|ride)\b", lower):
            workouts.append(
                {
                    "date": friday.isoformat(),
                    "sport": "Cycling",
                    "title": "Endurance ride (Z2)",
                    "session_type": "endurance",
                    "duration_min": 60,
                    "intensity": "Easy / conversational",
                    "description": f"60 min easy aerobic around {easy_band}.",
                    "structure": [],
                }
            )
        if re.search(r"\b(upper body|upper/core|core)\b", lower):
            workouts.append(
                {
                    "date": friday.isoformat(),
                    "sport": "Strength",
                    "title": "Upper body + core",
                    "session_type": "strength",
                    "duration_min": 45,
                    "intensity": "Moderate (RPE 6–7)",
                    "description": "Support work after the ride — not a second hard hit.",
                    "structure": [],
                }
            )

    saturday = dates.get("saturday")
    if saturday and re.search(r"\b(long ride|long easy ride)\b", lower):
        workouts.append(
            {
                "date": saturday.isoformat(),
                "sport": "Cycling",
                "title": "Long easy ride",
                "session_type": "endurance",
                "duration_min": 90,
                "intensity": "Easy / conversational",
                "description": "Conversational pace — cap duration so Sunday stays honest.",
                "structure": [],
            }
        )
        if "mobility" in lower:
            workouts.append(
                {
                    "date": saturday.isoformat(),
                    "sport": "Mobility",
                    "title": "Evening mobility",
                    "session_type": "mobility",
                    "duration_min": 25,
                    "intensity": "Recovery",
                    "description": "Light mobility only — no extra strength or intervals.",
                    "structure": [],
                }
            )

    sunday = dates.get("sunday")
    if sunday and re.search(r"\blong easy run\b", lower):
        workouts.append(
            {
                "date": sunday.isoformat(),
                "sport": "Running",
                "title": "Long easy run",
                "session_type": "easy",
                "duration_min": 60,
                "intensity": "Easy / conversational",
                "description": "Talk-pace only — absorb day before rest week.",
                "structure": [],
            }
        )
    return workouts


def template_apply_advisory_plan(
    message: str,
    safety: dict,
    *,
    thread: dict[str, str],
    clock: dict,
    context: dict | None = None,
    patched_workouts: list[dict] | None = None,
) -> dict[str, Any]:
    """Confirm a targeted calendar patch — no PRIMED/REVISED WEEK dump."""
    _ = message
    load = (safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    workouts = patched_workouts or build_advisory_workouts_from_thread(
        thread,
        clock,
        context=context,
        safety=safety,
    )
    acwr_bit = f"**{acwr:.2f}**" if isinstance(acwr, (int, float)) else "steady"

    change_lines: list[str] = []
    for workout in workouts:
        iso = str(workout.get("date") or "")[:10]
        try:
            label = date.fromisoformat(iso).strftime("%a %d %b")
        except ValueError:
            label = iso
        change_lines.append(
            f"- **{label}:** {workout.get('title')} — {workout.get('duration_min')} min · {workout.get('intensity')}"
        )

    body = "\n\n".join(
        [
            "Done — I updated **only the days we just discussed**. No full-week rebuild, no random library swap.",
            "",
            "**WHAT CHANGED**",
            "\n".join(change_lines) if change_lines else "- (No open days needed a change.)",
            "",
            "**Coach's Rule:** Keep Friday's ride easy, Saturday long but honest, and Sunday's run truly conversational.",
            "",
            f"**The Bottom Line:** Your calendar now matches what we agreed. ACWR at {acwr_bit} — "
            "land Monday's rest week fresh, not cooked.",
        ]
    )
    return {
        "reply": polish_advisory_reply(body),
        "citations": ["aal-safety-and-load"],
        "escalate": False,
        "escalation_reason": None,
        "intent": "GENERAL_CHAT",
    }


def apply_advisory_prompt_block(thread: dict[str, str]) -> str:
    advice = (thread.get("advice_reply") or "")[:1400]
    return f"""ADVISORY APPLY MODE (hard fail if violated):
- The athlete accepted your prior plan advice. Update ONLY the days you already discussed.
- Do NOT output PRIMED/ACCUMULATE, TODAY'S CALL, LOCKER ROOM DIRECTIVE, or a full REVISED WEEK table.
- Reply with: short confirmation → **WHAT CHANGED** bullets per updated day → **Coach's Rule:** → **The Bottom Line:**
- Do NOT invent bike fit, travel, trains, or destinations unless they appear in PRIOR ADVICE below.
- Do NOT swap in threshold intervals or library templates that contradict the prior advice.

PRIOR ADVICE (source of truth):
{advice}"""


ADVISORY_CHAT_RULES = """ADVISORY MODE — enforce ELITE COACH PERSONA layout (hard fail if violated):
1. Brief empathy ONLY if the athlete mentioned stress, missed sessions, bike fit, or travel in THIS message.
   Otherwise open with a direct, warm read on the plan they just described — no invented backstory.
2. Collaborative transition ("right instincts — let's tweak…").
3. Cover each day they proposed — each with **Coach's Rule:** and zone numbers where useful.
4. **Pros** and **Cons** ONLY when CURRENT-TURN PROS/CONS says to include them — otherwise skip entirely.
5. **The Bottom Line:** — 1–2 sentences tied to their plan and load (ACWR/HRV only if in ATHLETE STATE).
GROUNDING: Do NOT mention bike fit, trains, travel, destinations, or guilt about missed work unless
the athlete said those words in the CURRENT message.
BAN: PRIMED/ACCUMULATE, TODAY'S CALL, REVISED WEEK, tables, "Mostly yes — with three edits"."""


def grounding_guardrail_block(message: str) -> str:
    """Inject per-turn grounding so advisory replies stay on the athlete's actual question."""
    text = (message or "").strip()
    mentions_travel = bool(
        re.search(r"\b(travel|train ride|by train|on the train|airport|kolhapur)\b", text, re.I)
    )
    mentions_bike_fit = "bike fit" in text.lower()
    mentions_missed = bool(MISSED_OR_ROUGH_RE.search(text))
    bans: list[str] = []
    if not mentions_bike_fit:
        bans.append("bike fit")
    if not mentions_travel:
        bans.extend(["travel", "train", "Kolhapur", "destination"])
    if not mentions_missed:
        bans.extend(["missed session", "guilt", "you failed", "rough day you didn't mention"])
    ban_line = ", ".join(bans) if bans else "none (they raised the sensitive topics themselves)"
    return f"""CURRENT-TURN GROUNDING (hard fail if violated):
- Answer ONLY the plan and question in ATHLETE MESSAGE — not old chat context.
- Do NOT mention: {ban_line}.
- If they asked for pros/cons, give explicit Pros and Cons on the sessions they listed.
- Respect recovery/deload timing if they mention a rest week starting soon."""


def advisory_prompt_block(message: str | None = None) -> str:
    block = ADVISORY_CHAT_RULES
    if message:
        block = (
            f"{block}\n\n{pros_cons_guardrail_block(message)}\n\n"
            f"{grounding_guardrail_block(message)}"
        )
    return block


GO_DEEPER_RULES = """GO DEEPER MODE (hard):
- Warm, brief follow-up — 1 paragraph or 3 bullets. One watch number.
- End with one encouraging sentence. No week table. No PRIMED/ACCUMULATE."""


def go_deeper_prompt_block() -> str:
    return GO_DEEPER_RULES
