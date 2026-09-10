"""Conversational plan advice — answer 'should I do X?' without rebuilding the week.

Athletes proposing a DIY Fri–Sun stack or asking to validate a idea need a coach
conversation, not a REVISED WEEK table dump.
"""

from __future__ import annotations

import re
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
    r"would this work|good idea to|ok to do|okay to do"
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
    travel = "train" in text_lower or "travel" in text_lower or "kolhapur" in text_lower
    travel_dest = _travel_destination(message)
    stacking = "strength" in text_lower and ("bike" in text_lower or "ride" in text_lower)

    friday_summary = "Strength AM + Easy Spin PM." if stacking else "One focused session — strength or easy bike, not both hard."
    friday_rule = (
        f"Keep the afternoon ride strictly in Zone 2 (**{easy_band}**). "
        "Resist the urge to turn it into a makeup threshold ride!"
        if stacking
        else f"If you ride, stay in Zone 2 around **{easy_band}** — conversational, not heroic."
    )

    saturday_rule = (
        "Keep it conversational. Enjoy the ride, but cap the duration so you aren't completely drained while packing."
        if travel
        else "Keep it conversational — easy enough to talk the whole way. Don't chase hero distance."
    )

    sunday_label = "Sunday (Travel Day)" if travel else "Sunday"
    sunday_summary = "Rest & Recover on the Train." if travel else "Easy movement or full rest."
    sunday_rule = (
        "Skip the long run today. Stacking a long run right before sitting still on a train for hours "
        "will make your legs stiff and trap metabolic waste. Let Sunday be your full recovery day."
        if travel
        else "Keep it light — mobility or 30–40 minutes easy. Not another long endurance hit."
    )

    acwr_val = f"**{acwr:.2f}**" if isinstance(acwr, (int, float)) else "healthy"
    hrv_val = f"**{hrv}**" if hrv is not None else "solid"
    dest_phrase = f" at **{travel_dest}**" if travel_dest else " at your destination"

    bottom_line = (
        f"**The Bottom Line:** Your ACWR sits at a healthy {acwr_val} and your HRV is strong at {hrv_val}, "
        f"so your recovery foundation is solid. By resting on Sunday's train ride, you'll absorb Friday and "
        f"Saturday's training and arrive{dest_phrase} completely fresh!"
    )

    body_parts = [
        _empathy_opening(message),
        "",
        _collaborative_transition(message, travel_dest=travel_dest),
        "",
        _day_block("Friday (Tomorrow)", friday_summary, friday_rule),
        "",
        _day_block("Saturday", "Long Easy Ride.", saturday_rule),
        "",
        _day_block(sunday_label, sunday_summary, sunday_rule),
        "",
        bottom_line,
    ]

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
                "costs more than it pays back, especially before travel.",
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


ADVISORY_CHAT_RULES = """ADVISORY MODE — enforce ELITE COACH PERSONA layout (hard fail if violated):
1. Empathy paragraph first (validate bike fit / missed sessions / travel).
2. Collaborative transition ("right instincts — let's tweak…").
3. Friday / Saturday / Sunday — each with **Coach's Rule:** and zone numbers.
4. **The Bottom Line:** — exactly 2 encouraging sentences (ACWR + HRV + travel).
BAN: PRIMED/ACCUMULATE, TODAY'S CALL, REVISED WEEK, tables, "Mostly yes — with three edits"."""


def advisory_prompt_block() -> str:
    return ADVISORY_CHAT_RULES


GO_DEEPER_RULES = """GO DEEPER MODE (hard):
- Warm, brief follow-up — 1 paragraph or 3 bullets. One watch number.
- End with one encouraging sentence. No week table. No PRIMED/ACCUMULATE."""


def go_deeper_prompt_block() -> str:
    return GO_DEEPER_RULES
