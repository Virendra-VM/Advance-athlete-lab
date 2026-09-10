"""Phase 4 — plain-language layer for coach replies.

One voice: decision first, one watch number, one sentence why.
No journal abstract. Minimal headers on short replies.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

PLAIN_LANGUAGE_PHASE4_RULES = """PLAIN-LANGUAGE LAYER (Phase 4 — hard fail if violated):
- Write like a smart training partner, not a journal abstract.
- Open with the decision in the first 1-2 sentences ("Do X today" / "Keep Thursday as your only hard hit").
- Include ONE number they can use on their watch (watts, bpm, pace, or ACWR).
- Add ONE sentence why in everyday words — no metaphors, no triplet labels.
- BAN these labels in short replies: THE SCIENCE, LOCKER ROOM LINGO, REAL-WORLD EXAMPLE, METRIC/BIOLOGY/EXAMPLE.
- BAN journal filler: "glycolytic flux", "oxidative fibers", "parasympathetic tone" unless SCIENCE_LOOKUP.
- If the reply is under 250 words (excluding the week table), skip extra section headers beyond TODAY'S CALL and the table.
- Good example: "Thursday is your only hard hit — intervals at **204–213 W** under and **244–267 W** over. Everything else stays easy enough to talk through. ACWR 1.13 means don't stack a second hard day."
"""

PLAIN_DECISIONS = {
    "green": "You're cleared for the planned hard session — hit the targets, not extras.",
    "amber": "Hold the calendar — no bonus intensity today.",
    "red": "Rest or easy movement only — hard work can wait.",
}

JOURNAL_FILLER_RE = re.compile(
    r"\b("
    r"glycolytic flux|oxidative fibers|parasympathetic tone|mechanical tension|"
    r"neuromuscular loading|polarized distribution|hydrogen ions|"
    r"type I fibers|type II fibers|lactate threshold physiology"
    r")\b",
    re.I,
)

TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
PLAIN_LEAD_MARKER = "PLAIN_LEAD:"


def word_count_excluding_table(text: str) -> int:
    if not text:
        return 0
    kept: list[str] = []
    in_table = False
    for line in text.splitlines():
        if TABLE_LINE_RE.match(line):
            in_table = True
            continue
        if in_table and not line.strip():
            in_table = False
        if in_table:
            continue
        kept.append(line)
    blob = " ".join(kept)
    return len(re.findall(r"\b[\w']+\b", blob))


def _next_quality_workout(
    proposed_plan: dict | None,
    *,
    clock: dict | None,
) -> dict | None:
    if not proposed_plan:
        return None
    today = (clock or {}).get("today")
    best: dict | None = None
    best_date: date | None = None
    hard_types = {"tempo", "threshold", "intervals", "hills", "speed", "race"}
    for workout in proposed_plan.get("workouts") or []:
        session_type = str(workout.get("session_type") or "").lower()
        if session_type not in hard_types and "hard" not in str(workout.get("intensity") or "").lower():
            continue
        day_key = str(workout.get("date") or "")[:10]
        try:
            day = date.fromisoformat(day_key)
        except ValueError:
            continue
        if today and day < today:
            continue
        if best_date is None or day < best_date:
            best_date = day
            best = workout
    return best


def pick_watch_number(
    context: dict | None,
    safety: dict | None,
    *,
    proposed_plan: dict | None = None,
    clock: dict | None = None,
) -> str | None:
    """One actionable number for the athlete's watch."""
    quality = _next_quality_workout(proposed_plan, clock=clock)
    if quality:
        intensity = str(quality.get("intensity") or "").strip()
        title = str(quality.get("title") or "Quality session").strip()
        day_key = str(quality.get("date") or "")[:10]
        try:
            day_name = date.fromisoformat(day_key).strftime("%A")
        except ValueError:
            day_name = "Quality day"
        if intensity and intensity.lower() not in {"easy", "none", "recovery", "—", "-"}:
            return f"{day_name} **{title}** — {intensity}"
        return f"{day_name} **{title}**"

    physiology = (context or {}).get("physiology") or {}
    ftp = physiology.get("ftp_watts") or physiology.get("ftp_estimated_watts")
    if ftp:
        return f"Use **{ftp} W** as your FTP anchor for today's efforts"
    lthr = physiology.get("lthr_bpm")
    if lthr:
        easy_high = round(float(lthr) * 0.83)
        return f"Easy days stay under **{easy_high} bpm** (Z2 with your LTHR **{lthr}**)"

    load = (safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    if isinstance(acwr, (int, float)):
        return f"ACWR **{acwr:.2f}** — keep hard days to the plan cap"
    return None


def build_plain_why_sentence(
    safety: dict | None,
    context: dict | None,
    *,
    band: str,
) -> str:
    load = (safety or {}).get("load") or {}
    acwr = load.get("minutes_acwr")
    if isinstance(acwr, (int, float)) and acwr >= 1.3:
        return f"ACWR is **{acwr:.2f}** — stacking extra hard days borrows from next week."
    if isinstance(acwr, (int, float)) and acwr >= 1.15:
        return f"Load is elevated (**{acwr:.2f}**) — protect easy days so quality sessions land clean."
    if band == "red":
        return "Recovery comes first today so later hard sessions still land clean."
    if band == "amber":
        return "Absorb what you've already banked — no hero sessions today."
    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    sleep = health.get("sleep_score")
    if isinstance(sleep, (int, float)) and sleep < 70:
        return f"Sleep was **{sleep}** — match intensity to that, not ambition."
    return "Stay inside the week shape — one quality day, everything else truly easy."


def build_plain_lead(
    context: dict | None,
    safety: dict | None,
    *,
    proposed_plan: dict | None = None,
    clock: dict | None = None,
) -> str:
    from app.services.ai_coach import readiness_score, today_call_status

    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    score, _ = readiness_score(health, safety)
    band, status = today_call_status(score)
    decision = PLAIN_DECISIONS.get(band, PLAIN_DECISIONS["amber"])
    watch = pick_watch_number(context, safety, proposed_plan=proposed_plan, clock=clock)
    why = build_plain_why_sentence(safety, context, band=band)

    parts = [f"{status} — {decision}"]
    if watch:
        parts.append(watch)
    parts.append(why)
    return " ".join(parts)


def has_plain_lead(text: str) -> bool:
    if PLAIN_LEAD_MARKER in text:
        return True
    head = (text or "")[:500]
    head_lower = head.lower()
    status_open = re.search(
        r"(🟢|🟡|🔴)?\s*(PRIMED|CAUTION|REST)\s*/\s*(ACCUMULATE|ABSORB|RESTORE)",
        head,
        re.I,
    )
    has_watch_number = bool(
        re.search(
            r"(\*\*[^*]+\*\*|\d+[\d–\-]*\s*W|\d+\s*bpm|ACWR\s+\*\*[\d.]+|\*\*[\d.]+\*\*)",
            head,
            re.I,
        )
    )
    if status_open and has_watch_number:
        return True
    if re.search(r"\b(only hard hit|cleared for|rest or easy|hold the calendar)\b", head_lower):
        return has_watch_number
    return False


def strip_journal_filler(text: str) -> str:
    if not text:
        return text
    return JOURNAL_FILLER_RE.sub("", text)


def collapse_formal_labels(text: str) -> str:
    """Remove leftover formal triplet label lines."""
    if not text:
        return text
    drop_prefixes = (
        "• 🔬 THE SCIENCE:",
        "• 🗣️ LOCKER ROOM LINGO:",
        "• 💡 REAL-WORLD EXAMPLE:",
        "METRIC:",
        "THE BIOLOGY:",
        "💡 EXAMPLE:",
    )
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in drop_prefixes):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def ensure_plain_lead(
    text: str,
    *,
    context: dict | None,
    safety: dict | None,
    proposed_plan: dict | None = None,
    clock: dict | None = None,
) -> str:
    if has_plain_lead(text):
        return text
    lead = build_plain_lead(
        context,
        safety,
        proposed_plan=proposed_plan,
        clock=clock,
    )
    marker = f"{PLAIN_LEAD_MARKER} {lead}"
    if "📊" in text and "WHAT CHANGED" in text:
        parts = text.split("📊", 1)
        return f"{parts[0].rstrip()}\n\n{marker}\n\n📊{parts[1]}"
    if "🟢 TODAY'S CALL" in text:
        parts = text.split("🟢 TODAY'S CALL", 1)
        return f"{marker}\n\n🟢 TODAY'S CALL{parts[1]}"
    return f"{marker}\n\n{text}"


def apply_plain_language_layer(
    text: str,
    *,
    context: dict | None = None,
    safety: dict | None = None,
    proposed_plan: dict | None = None,
    clock: dict | None = None,
) -> str:
    """Post-process narrator output into plain partner voice."""
    cleaned = collapse_formal_labels(strip_journal_filler(text))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if word_count_excluding_table(cleaned) <= 250:
        cleaned = ensure_plain_lead(
            cleaned,
            context=context,
            safety=safety,
            proposed_plan=proposed_plan,
            clock=clock,
        )
    return cleaned.replace(PLAIN_LEAD_MARKER, "").strip()


def apply_plain_language_reply(
    reply: dict,
    *,
    context: dict | None = None,
    safety: dict | None = None,
    proposed_plan: dict | None = None,
    clock: dict | None = None,
) -> dict:
    reply["reply"] = apply_plain_language_layer(
        reply.get("reply") or "",
        context=context,
        safety=safety,
        proposed_plan=proposed_plan,
        clock=clock,
    )
    return reply


def plain_language_prompt_block() -> str:
    return PLAIN_LANGUAGE_PHASE4_RULES
