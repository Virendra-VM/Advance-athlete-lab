"""Pillar 1 voice: three-step coaching, rolling facts, and fail-closed BFR."""

from __future__ import annotations

import re

CRUTCH_PHRASES = (
    "take a deep breath",
    "you've got the right instincts",
    "you have the right instincts",
    "let's dive in",
    "you've got this",
)

BANNED_BADGE_MARKERS = (
    "🟢",
    "TODAY'S CALL",
    "PRIMED / ACCUMULATE",
    "LOCKER ROOM DIRECTIVE",
    "ACWR:",
)

_EMOTION_RE = re.compile(
    r"\b(anxious|anxiety|panic(?:ked|king)?|worried|worry|guilty|guilt|scared|"
    r"terrified|frustrated|freaking out|so stressed|nervous)\b",
    re.IGNORECASE,
)
_RESOLVED_RE = re.compile(
    r"\b(feeling better|feel better|all good now|it(?:'s| is) resolved|not worried|"
    r"panic(?:'s| is) over|anxiety is gone)\b",
    re.IGNORECASE,
)
_STIFFNESS_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*/\s*10).{0,40}\b(hamstring|calf|quad|knee|back|achilles|glute)\b"
    r"|\b(hamstring|calf|quad|knee|back|achilles|glute)\b.{0,40}(\d+(?:\.\d+)?\s*/\s*10)",
    re.IGNORECASE,
)
_MISSED_RE = re.compile(
    r"\bmissed\b.{0,60}\b(threshold|vo2|interval|session|workout|long run)\b"
    r"|\b(threshold|vo2|interval|long run)\b.{0,40}\bmissed\b",
    re.IGNORECASE,
)
_TAPER_TANTRUM_RE = re.compile(
    r"\b(taper|race)\b",
    re.IGNORECASE,
)
_TAPER_BODY_RE = re.compile(
    r"\b(sluggish|heavy|phantom|flat|anxious|panic)\b",
    re.IGNORECASE,
)
_BFR_RE = re.compile(
    r"\b(bfr|blood flow restriction|occlusion cuff)\b",
    re.IGNORECASE,
)
_PRESSURE_ASK_RE = re.compile(
    r"\b(pressure|mmhg|millimetre|millimeter|how tight|what should i set|cuff)\b",
    re.IGNORECASE,
)

TAPER_TANTRUM_REPLY = (
    "Feeling heavy and sluggish right now is exactly what we want to see. "
    "Your body is busy repairing muscle tissue from the last build block, and that repair process demands energy. "
    "We aren't losing fitness; we're just coiling the spring. "
    "Keep tomorrow's spin strictly in Zone 1 to flush the legs, and trust the taper. "
    "You'll have that snap back by race morning."
)

BFR_REFUSAL = (
    "BFR requires personalized calibration based on your Arterial Occlusion Pressure (AOP), "
    "typically restricted to 40-80% of your maximum. Because we do not have your Doppler "
    "ultrasound baseline in your profile, I cannot safely prescribe a static mmHg pressure. "
    "I recommend avoiding BFR until you can calibrate it with a physical therapist. Instead, "
    "we can utilize standard high-rep hypertrophy work today to achieve a similar metabolic stimulus."
)

CONVERSATION_CONTRACT = """CONVERSATION CONTRACT — hard fail if violated:
You are an elite endurance coach. Tone is high-agency, warm, and confident. You never apologize.
When the athlete is anxious, missed a session, or is in a taper tantrum, follow Empathy, then Direction, then a Practical Analogy.
Empathy acknowledges the reality in one or two sentences and does not dwell.
Direction is a concrete schedule change (what changes tomorrow, what is wiped, what stays easy).
Practical Analogy is a physical image such as coiling the spring, absorbing the load, or banking the fitness.
Never output status badges, emoji headers, JSON, or raw keys. Banned leaks include 🟢 TODAY'S CALL, LOCKER ROOM DIRECTIVE, PRIMED / ACCUMULATE, and lines like ACWR: 1.2. Translate the numbers into prose.
Never open with a crutch phrase: "Take a deep breath", "You've got the right instincts", "Let's dive in", or "You've got this".
Use only the ROLLING STATE facts for history. Do not mention past anxiety once the issue is resolved.
Do NOT autopsy a past ride. Do NOT add 🔬 WEEKLY TRANSLATIONS.
When a why is earned, one short **Why this works** or **Why recovery** note is enough.
Aim for 80-180 words besides any session detail."""


def is_taper_tantrum(message: str) -> bool:
    text = message or ""
    return bool(_TAPER_TANTRUM_RE.search(text) and _TAPER_BODY_RE.search(text))


def taper_tantrum_reply(message: str) -> str | None:
    if not is_taper_tantrum(message):
        return None
    return TAPER_TANTRUM_REPLY


def bfr_pressure_reply(message: str, aop_mmhg: float | None) -> str | None:
    """Refuse a cuff pressure when arterial occlusion pressure is missing.

    A stored AOP may be turned into the 40–80% band. A missing AOP never becomes a guessed mmHg.
    """
    text = message or ""
    if not _BFR_RE.search(text) or not _PRESSURE_ASK_RE.search(text):
        return None
    if aop_mmhg is None:
        return BFR_REFUSAL
    pressure = float(aop_mmhg)
    low = round(pressure * 0.4)
    high = round(pressure * 0.8)
    return (
        f"Your stored arterial occlusion pressure is {pressure:.0f} mmHg. "
        f"Keep the cuff between {low} and {high} mmHg, which is 40-80% of that baseline. "
        "Stop for numbness, color change, or pain. If a clinician has not set this with you, skip the cuffs "
        "and use high-rep hypertrophy instead."
    )


def physiological_fact(message: str) -> str:
    """One immutable fact. Emotional wording is dropped."""
    text = (message or "").strip()
    if not text:
        return ""
    stiffness = _STIFFNESS_RE.search(text)
    if stiffness:
        score = stiffness.group(1) or stiffness.group(4)
        tissue = stiffness.group(2) or stiffness.group(3)
        return f"User reported {score.replace(' ', '')} {tissue.lower()} stiffness"
    if _MISSED_RE.search(text):
        return "User missed a key session"
    if re.search(r"\bbike fit\b|\bsaddle\b", text, re.IGNORECASE):
        return "User changed bike fit or saddle position"
    cleaned = _EMOTION_RE.sub("", text)
    cleaned = re.sub(
        r"\b(i feel|i'm feeling|i am feeling|i'm so|i am so)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
    if not cleaned:
        return ""
    return cleaned[:180]


def rolling_state_summary(history: list[dict] | None) -> str:
    """Prior turns as physiological facts. Resolved anxiety is not carried forward."""
    facts: list[str] = []
    seen: set[str] = set()
    for entry in history or []:
        if (entry.get("role") or "").lower() != "user":
            continue
        content = str(entry.get("content") or "")
        if _RESOLVED_RE.search(content):
            facts = [fact for fact in facts if "stiffness" in fact or "missed" in fact or "bike fit" in fact]
            continue
        fact = physiological_fact(content)
        if not fact or fact in seen:
            continue
        if _EMOTION_RE.search(fact):
            continue
        seen.add(fact)
        facts.append(f"[{fact}]")
    return "\n".join(facts)
