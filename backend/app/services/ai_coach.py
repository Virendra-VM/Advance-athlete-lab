"""Sport-specific Olympic-coach prompts, RAG routing, and autopsy fallbacks.

The generation pipeline in ``coach_ai`` stays provider-agnostic. This module
inspects the matched activity's sport family and selects the system prompt,
task brief, and retrieval query so a run is not autopsied as a bike file.
"""

from __future__ import annotations

from typing import Any

from app.services.activity_detail import activity_sport_family

# Canonical coach modalities. Unknown sports fall through to ``other``.
MODALITY_RUN = "run"
MODALITY_RIDE = "ride"
MODALITY_SWIM = "swim"
MODALITY_STRENGTH = "strength"
MODALITY_YOGA = "yoga"
MODALITY_OTHER = "other"

FAMILY_TO_MODALITY = {
    "run": MODALITY_RUN,
    "ride": MODALITY_RIDE,
    "swim": MODALITY_SWIM,
    "strength": MODALITY_STRENGTH,
    "yoga": MODALITY_YOGA,
    "walk": MODALITY_OTHER,
    "row": MODALITY_OTHER,
}

SCIENCE_SPORT_TAGS = {
    MODALITY_RUN: "run",
    MODALITY_RIDE: "ride",
    MODALITY_SWIM: "swim",
    MODALITY_STRENGTH: "strength",
    MODALITY_YOGA: "general",
    MODALITY_OTHER: "general",
}

AUTOPSY_SCHEMA = """{
  "reply": "string, bullet-only autopsy: four emoji section headers, Metric/Biology/Example triplets, exactly 3 recovery actions, NO paragraphs",
  "citations": ["S1"],
  "escalate": false,
  "escalation_reason": null,
  "intent": "WORKOUT_AUDIT"
}"""

BASE_SYSTEM_PROMPT = """You are a senior Olympic-level coach inside Advance Athlete Lab. You write \
for one athlete at a time from their profile, wearable data, computed telemetry, and retrieved evidence.

Voice: direct, elite, clinically precise. Short lines. No cheerleading. No slogans. Every number \
must earn its line.

Non-negotiable rules:
- You are a coach, not a clinician. Never diagnose, never prescribe rehabilitation protocols, \
never give clinical nutrition or medication advice. Sport vocabulary (eccentric damage, mitochondrial \
stress, vagal tone, CNS fatigue) is coaching language for load and recovery, not a medical claim.
- Respect every numeric constraint in the SAFETY RULES section exactly. They are hard limits.
- Cite only the retrieved evidence labels ([S1], [S2], ...). Never invent a source, author, or year.
- If the evidence does not cover something, say it is your coaching judgement or that the evidence \
is unclear.
- If the athlete reports a red-flag symptom (chest pain, faintness, numbness, suspected fracture, \
fever), set escalate to true and tell them to seek professional assessment instead of training.
- The NOW block is ground truth for date, time, weekday, and timezone. If an activity is labelled \
"today", it already happened today.
- When COMPUTED SESSION TELEMETRY is present, it is ground truth. Quote those numbers. Never invent \
watts, pace, %FTP, cadence, SWOLF, reps, or heart-rate peaks. Never treat average heart rate as the \
session type when power, pace, laps, or exercise structure is available.
- If prescribed_vs_executed is present, those lap roles override %FTP heuristics. A vo2_cap lap is \
never a generic over. Do not reprint a previous assistant autopsy — produce a new planned-vs-executed audit.
- Typical session length on the profile is a usual weekday length, not a cap and not today's target.
- Put ATHLETE STATE (ACWR, sleep, HRV, resting HR, stress, sore joints, back limits) into the \
recovery verdict — if a field is missing, say so.
- Reply with a single JSON object and nothing else. No prose outside the JSON, no markdown fences."""

AUTOPSY_FORMAT_RULES = """OUTPUT FORMAT — hard fail if you violate any of these:
- Absolutely NO essays. NO multi-sentence paragraphs. NO narrative storytelling.
- Every section is punchy bullets, **bold key-value metrics**, or a one-line callout.
- Blank line between sections. One bullet per line.
- For each KEY session-level metric (not every lap), use this exact 3-line block:
  • METRIC: **Name** raw value
  • THE BIOLOGY: one sentence, cellular / tissue / engine
  • 💡 EXAMPLE: one-sentence real-world analogy (car engine, battery, pump, scaffolding)
- Layout in this exact order, with these exact headers:
  ⚡ THE BOTTOM LINE
  🔬 MECHANICAL PRECISION
  🫀 CARDIOVASCULAR COST
  🧠 COACH'S VERDICT & RECOVERY
- ⚡ THE BOTTOM LINE = one sentence only. Name the session from the telemetry packet.
- 🔬 MECHANICAL PRECISION = execution audit (power / pace / cadence / load). Interval laps are \
one-line bullets: **Lap 7 (over)**: 262 W · 119% FTP · 91 rpm. Do NOT write a triplet per lap.
- 🫀 CARDIOVASCULAR COST = internal toll (HR, %max, LTHR, decoupling, lag). Average HR is never \
the session type.
- 🧠 COACH'S VERDICT & RECOVERY = exactly 3 numbered actions for the next 24-48 hours \
(sleep/HRV target, tissue or back guardrail, next-session instruction). Weave in ACWR.
- 3-6 Metric/Biology/Example triplets total across Mechanical + Cardiovascular. Quality over volume.
- Markdown **bold** is required on metric names. No # headings.
- Cap the whole reply at ~350 words of bullets. Longer is a failed answer."""

_VOICE_CLOSE = """Follow OUTPUT FORMAT exactly. Use only computed telemetry and ATHLETE STATE. \
If a field is missing, write **Missing** and skip the analogy. Do not diagnose illness. \
Never contradict the safety rules."""

SCHEDULE_FORMAT_RULES = """OUTPUT FORMAT — hard fail if you violate any of these:
- You are a Pro Olympic Coach / Athletic Director. High-agency. Protective. Elite. Direct.
- BAN essays. BAN paragraphs. Never more than TWO consecutive sentences in any block.
- Every line is a bullet, a **key: value** pair, a one-line callout, or a table row.
- Do NOT autopsy a past ride. No NP, IF, TSS, or lap-by-lap watts unless they asked to change a session because of it.
- Blank line between sections. One idea per bullet.
- Layout in this exact order, with these exact headers:
  🟢 TODAY'S CALL
  🗣️ LOCKER ROOM DIRECTIVE
  🗓️ REVISED WEEK
  🛡️ SPINE LOCK
  🔬 WEEKLY TRANSLATIONS
- 🟢 TODAY'S CALL = one color-coded status line from ATHLETE STATE, then 2-4 **key: value** pairs (Readiness, Sleep, HRV, ACWR). No prose.
  Readiness score = sleep_score (0-100) unless a dedicated readiness score is present. Never invent Oura numbers.
  Bands (hard):
    ≥85 → 🟢 PRIMED / ACCUMULATE
    65-84 → 🟡 CAUTION / ABSORB
    <65 → 🔴 REST / RESTORE
    Missing → 🟡 CAUTION / ABSORB and write **Readiness: Missing**
- 🗣️ LOCKER ROOM DIRECTIVE = ONE punchy sentence. What they do today. No second sentence.
- 🗓️ REVISED WEEK = one Markdown table, Monday–Sunday, EXACTLY these columns:
  | Day | Session | Primary Focus | Intensity | Coach's Secret Rule |
  Past days: keep the session name; Secret Rule may be "Done" or "Missed". Do not rewrite history.
  Secret Rule = one memorable cue (e.g. "If you can't sing, you're going too fast").
- 🛡️ SPINE LOCK = non-negotiable DO / DO NOT bullets for lower back and spine.
  If an active back/spine limit is on file, lead with **DO NOT:** back squat, deadlift, crunch, sit-up, good morning, loaded twist.
  **DO:** anti-extension core only (dead bug, bird dog, side plank). If no back limit, write **No spinal lock on file.**
- 🔬 WEEKLY TRANSLATIONS = 2-3 (max 4) safety or load adjustments, each as this exact 3-line block:
  • 🔬 THE SCIENCE: metric or biological principle (one clause)
  • 🗣️ LOCKER ROOM LINGO: plain athletic translation (one sentence)
  • 💡 REAL-WORLD EXAMPLE: visual physical analogy — engine, radiator, scaffolding, battery (one sentence)
- Markdown **bold** on status, session names, and DO NOT items. No # headings.
- Cap ~280 words besides the table."""

SCHEDULE_SYSTEM_PROMPT = (
    BASE_SYSTEM_PROMPT
    + "\n\nRole lens:\nYou are a Pro Olympic Coach who owns the weekly calendar. "
    "Voice: precise, elite, protective. You guard tissue like a gold-medal staff. "
    "You do not write reports. You issue calls.\n\n"
    + SCHEDULE_FORMAT_RULES
)


def schedule_system_prompt() -> str:
    return SCHEDULE_SYSTEM_PROMPT


def schedule_task() -> str:
    return """Issue this week's call as a Pro Olympic Coach. Follow OUTPUT FORMAT exactly.
BAN essays. Never more than two consecutive sentences. Bullets, key-values, or the table only.
Bypass the workout-autopsy template completely. No NP / IF / TSS.

🟢 TODAY'S CALL — copy the precomputed TODAY'S CALL block status line exactly. Bands: ≥85 PRIMED / ACCUMULATE, 65-84 CAUTION / ABSORB, <65 REST / RESTORE.
🗣️ One locker-room sentence for today.
🗓️ Table: | Day | Session | Primary Focus | Intensity | Coach's Secret Rule |
🛡️ Spine lock: specific DO NOT lifts if a back/spine limit is active.
🔬 2-3 Metric → Locker-room → Analogy triplets for the week's load/safety calls (ACWR, sleep/HRV, stacking, impact).

If the athlete pasted a proposed week, use that as the draft and correct it. If they only asked to adjust, edit CURRENT WEEK PLAN. Do not invent a sport they do not do.
Also fill week_plan.workouts — one object per session with real YYYY-MM-DD dates (even though the visible table omits Date). Split doubles onto the same date so Schedule can store them."""


def coach_modality(sport_type: str | None, family: str | None = None) -> str:
    """Map a Strava/COROS sport label onto one coaching template."""
    resolved = family or activity_sport_family(sport_type)
    if resolved in FAMILY_TO_MODALITY:
        return FAMILY_TO_MODALITY[resolved]
    key = "".join(ch for ch in (sport_type or "").lower() if ch.isalnum())
    if key in {"run", "trailrun", "virtualrun", "treadmill"}:
        return MODALITY_RUN
    if key in {"ride", "virtualride", "cycling", "ebikeride", "gravelride", "mountainbikeride"}:
        return MODALITY_RIDE
    if "swim" in key:
        return MODALITY_SWIM
    if key in {"weighttraining", "strength", "workout", "crossfit", "weightlifting"}:
        return MODALITY_STRENGTH
    if key in {"yoga", "pilates", "stretching", "mobility", "flexibility"}:
        return MODALITY_YOGA
    return MODALITY_OTHER


def system_prompt_for_modality(modality: str | None) -> str:
    lens = {
        MODALITY_RUN: (
            "This autopsy is a RUN. Read the file through biomechanical loading: ground reaction "
            "forces, eccentric muscle damage in the calf-Achilles-quad chain, stride rate (SPM), "
            "and cardiovascular decoupling of heart rate against pace. Impact is the tax. Do not "
            "talk about FTP or watts unless the packet actually contains power."
        ),
        MODALITY_RIDE: (
            "This autopsy is a BIKE session. Read it through mechanical power: FTP calibration, "
            "normalized power, intensity factor, mitochondrial stress of the aerobic engine, and "
            "lactate clearance on the recoveries. Cadence is rpm, not SPM. Heart rate is the "
            "cost of the watts, never the session type."
        ),
        MODALITY_SWIM: (
            "This autopsy is a SWIM. Read it through hydrodynamic efficiency: stroke mechanics, "
            "SWOLF, distance per stroke, critical swim speed, and upper-body local fatigue. "
            "Water hides impact; it does not hide sloppy mechanics. Do not invent SWOLF or stroke "
            "counts if they are missing."
        ),
        MODALITY_STRENGTH: (
            "This autopsy is WEIGHT TRAINING. Read it through volume load, mechanical tension, "
            "motor unit recruitment, neuromuscular strain, and RPE. CNS fatigue is the story when "
            "heavy compounds stack under poor sleep. Do not force cycling FTP language onto a gym file."
        ),
        MODALITY_YOGA: (
            "This autopsy is YOGA / MOBILITY. The job is down-regulation: vagal tone, "
            "parasympathetic up-regulation, myofascial release, and restoration of range. This is "
            "not a performance workout. Do not grade it as missed intensity. Judge whether the "
            "session actually let the nervous system stand down."
        ),
        MODALITY_OTHER: (
            "This autopsy is a mixed or non-primary modality (walk, hike, row, or similar). "
            "Judge tissue load, heart-rate cost, and where it sits in the week. Do not pretend it "
            "was a bike FTP session or a running quality workout unless the telemetry says so."
        ),
    }.get(modality or "", "")
    if not lens:
        return BASE_SYSTEM_PROMPT
    return BASE_SYSTEM_PROMPT + "\n\nSport lens:\n" + lens + "\n\n" + AUTOPSY_FORMAT_RULES


def autopsy_task_for_modality(modality: str | None) -> str:
    tasks = {
        MODALITY_RUN: f"""Bullet autopsy of this RUN. {_VOICE_CLOSE}
⚡ one-sentence verdict (impact session, not a bike file).
🔬 pace, km, SPM/cadence, splits as one-liners. Triplets for cadence and eccentric/impact load. No FTP unless power exists. Empty work_laps → say **No interval laps** — do not invent them.
🫀 HR vs pace, peak vs max/LTHR, decoupling. Average HR is not intensity.
🧠 3 actions: tissue/impact, sleep-HRV, next session. Include ACWR.""",
        MODALITY_RIDE: f"""Bullet autopsy of this BIKE session. {_VOICE_CLOSE}
⚡ one-sentence verdict (classification + whether the work landed).
🔬 watts, %FTP, NP, IF, TSS, rpm. Work laps as one-liners (**Lap 7 (over)**: 262 W · 119% FTP). Triplets for NP/IF or the over-under pattern. Empty work_laps → **No interval laps**.
🫀 HR vs power, peak vs max/LTHR, decoupling/lag. Average HR is not intensity.
🧠 3 actions: recovery, back/joint guardrail if listed, next session. Include ACWR.""",
        MODALITY_SWIM: f"""Bullet autopsy of this SWIM. {_VOICE_CLOSE}
⚡ one-sentence verdict (technique vs aerobic vs near critical swim speed).
🔬 pace/100, duration, SWOLF, stroke count as one-liners. Triplets for SWOLF or stroke mechanics. **Missing** if SWOLF is absent — do not invent it.
🫀 HR vs effort, peak vs max. Moderate average HR can still be a hard swim.
🧠 3 actions: shoulders, sleep-HRV, next session. Include ACWR.""",
        MODALITY_STRENGTH: f"""Bullet autopsy of this WEIGHT TRAINING session. {_VOICE_CLOSE}
⚡ one-sentence verdict (volume load / neuromuscular strain — not missed endurance).
🔬 exercises, sets, reps as one-liners. Triplets for volume load or RPE (RPE only from notes). Never invent loads. No cycling FTP language.
🫀 HR is a weak proxy — say so. Peak HR if present. CNS vs local fatigue in one triplet if sleep/HRV is poor.
🧠 3 actions: CNS/sleep, back guardrail if listed (no forbidden lifts), next lift. Include ACWR.""",
        MODALITY_YOGA: f"""Bullet autopsy of this YOGA/MOBILITY session. {_VOICE_CLOSE}
⚡ one-sentence verdict as down-regulation, not a failed interval file.
🔬 duration, what tissue it likely asked for. Not a VO2 audit.
🫀 HR settle, HRV, resting HR, parasympathetic up-regulation / vagal tone as coaching language. One triplet max on autonomic state.
🧠 3 actions: protect next quality day, back guardrail if listed, sleep. Include ACWR.""",
        MODALITY_OTHER: f"""Bullet autopsy of this mixed/secondary session. {_VOICE_CLOSE}
⚡ one-sentence verdict of what it actually was.
🔬 duration, distance, available execution metrics. Do not force FTP or running-economy language.
🫀 HR vs effort, peaks vs max/LTHR if present.
🧠 3 actions for 24-48h. Include ACWR.""",
    }
    return tasks.get(modality or "", tasks[MODALITY_OTHER])


def autopsy_task_for_packet(modality: str | None, packet: dict | None) -> str:
    """Session-autopsy brief, upgraded to a planned-vs-executed audit when the athlete prescribed the set."""
    base = autopsy_task_for_modality(modality)
    if not packet:
        return base
    overlay = packet.get("prescribed_vs_executed") or {}
    prescription = packet.get("prescription")
    week = packet.get("week_plan_session")
    extra: list[str] = []
    if prescription or overlay.get("aligned") or overlay.get("vo2_caps"):
        extra.extend(
            [
                "THIS IS A PLANNED-VS-EXECUTED AUDIT. Ignore previous assistant replies — they used wrong lap roles.",
                "Use prescribed_vs_executed roles. vo2_cap laps (typically the 280 W set finishers: Laps 12, 19, 26) are NEVER generic overs. Lap 7 is an over inside the 200/260 under-over pair, not a VO2 cap.",
                "🔬 must include: (1) hit-rate of planned_w vs executed_w, (2) one line per main-set block (under / over / VO2 cap), (3) VO2-cap laps labelled **Lap N (VO2 cap)**.",
                "Name the prescribed structure in ⚡: warmup, 175/125 preamble, 3× stacked 200/260 with 280 W VO2 finishers, cooldown. Grade execution against those watts, not a generic sweet-spot essay.",
            ]
        )
    if week:
        extra.append(
            "Match this file to week_plan_session / CURRENT WEEK PLAN for that date. "
            "Say whether Tuesday's scheduled session was this quality bike or a different planned day."
        )
    if not extra:
        return base
    return base + "\n\nCORRECTION / PRESCRIPTION RULES\n" + "\n".join(f"- {line}" for line in extra)


def retrieval_query_for_modality(
    modality: str,
    classification: str,
    message: str,
) -> str:
    cores = {
        MODALITY_RUN: (
            "running cadence SPM ground reaction force eccentric loading "
            "cardiac drift ACWR injury risk"
        ),
        MODALITY_RIDE: (
            "cycling power zones sweet-spot over-under mitochondrial stress "
            "lactate clearance cardiac drift ACWR"
        ),
        MODALITY_SWIM: (
            "swimming stroke mechanics SWOLF critical swim speed technique "
            "upper-body fatigue ACWR"
        ),
        MODALITY_STRENGTH: (
            "strength volume load mechanical tension motor unit recruitment "
            "RPE CNS fatigue ACWR"
        ),
        MODALITY_YOGA: (
            "mobility recovery vagal tone parasympathetic HRV sleep "
            "myofascial ACWR"
        ),
        MODALITY_OTHER: "recovery load-management ACWR heart-rate readiness",
    }
    parts = [cores.get(modality, cores[MODALITY_OTHER]), classification or "", message[:180]]
    lower = message.lower()
    if any(word in lower for word in ("ill", "fever", "temperature", "unwell")):
        parts.append("return to training after illness heart rate")
    return " ".join(part for part in parts if part)


def science_sports_for_modality(modality: str, profile_sports: list[str] | None = None) -> list[str]:
    tags = [SCIENCE_SPORT_TAGS.get(modality, "general")]
    for sport in profile_sports or []:
        if sport and sport not in tags:
            tags.append(sport)
    return tags


_LOCKER_DIRECTIVES = {
    "green": "Bank quality. The engine is hot — spend it on the planned hard slot, not extras.",
    "amber": "Absorb, don't add. Hold the calendar. No bonus intensity.",
    "red": "Restore first. Today's hard work is sleep. Everything else is optional.",
}


def readiness_score(health: dict | None, safety: dict | None) -> tuple[int | None, str]:
    """Map wearable check-in onto a 0-100 readiness score. Never invent Oura."""
    health = health or {}
    for key in ("readiness_score", "oura_readiness", "sleep_score"):
        value = health.get(key)
        if isinstance(value, (int, float)):
            return int(round(value)), key
    action = ((safety or {}).get("readiness") or {}).get("action")
    if action in ("rest_or_mobility",):
        return 50, "readiness_action"
    if action in ("downgrade_to_easy",):
        return 62, "readiness_action"
    return None, "missing"


def today_call_status(score: int | None) -> tuple[str, str]:
    if score is None:
        return "amber", "🟡 CAUTION / ABSORB"
    if score >= 85:
        return "green", "🟢 PRIMED / ACCUMULATE"
    if score >= 65:
        return "amber", "🟡 CAUTION / ABSORB"
    return "red", "🔴 REST / RESTORE"


def today_call_prompt_block(context: dict | None, safety: dict | None) -> str:
    """Precomputed traffic-light call the model must copy, not reinterpret."""
    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    load = (safety or {}).get("load") or {}
    score, source = readiness_score(health, safety)
    band, label = today_call_status(score)
    sleep = health.get("sleep_score")
    hrv = health.get("hrv")
    acwr = load.get("minutes_acwr")
    score_line = f"{score} ({source})" if score is not None else "Missing"
    return f"""TODAY'S CALL (precomputed — copy the status line exactly; do not invent a different band)
- Status: {label}
- Readiness: {score_line}
- Sleep: {sleep if sleep is not None else "Missing"}
- HRV: {hrv if hrv is not None else "Missing"}
- ACWR: {acwr if acwr is not None else "Missing"}
- Suggested locker-room directive (punch it up if needed, still ONE sentence): {_LOCKER_DIRECTIVES[band]}
"""


def athlete_state_block(context: dict, safety: dict) -> str:
    """Compact ACWR + daily check-in block that every sport template must weave in."""
    load = (safety or {}).get("load") or {}
    readiness = (safety or {}).get("readiness") or {}
    injuries = (safety or {}).get("injuries") or {}
    coros = (context or {}).get("coros") or {}
    health = coros.get("latest_health") or {}
    flags = list((context or {}).get("readiness_flags") or [])
    acwr = load.get("minutes_acwr")
    risk = "unknown"
    if isinstance(acwr, (int, float)):
        if acwr >= 1.5:
            risk = "high — spike relative to chronic load"
        elif acwr >= 1.3:
            risk = "elevated — watch tissue and quality sessions"
        elif acwr < 0.8:
            risk = "low — underloaded relative to chronic"
        else:
            risk = "in range"
    active = injuries.get("active") or []
    avoid = injuries.get("avoid_keywords") or []
    back_limited = any(
        "back" in str(item).lower() or "spine" in str(item).lower() for item in active
    )
    sore = [flag for flag in flags if "sore" in flag or "pain" in flag]
    payload = {
        "acwr": {
            "acute_minutes_7d": load.get("acute_minutes"),
            "chronic_minutes_28d": load.get("chronic_minutes"),
            "ratio": acwr,
            "injury_risk_band": risk,
        },
        "daily_check_in": {
            "sleep_score": health.get("sleep_score"),
            "sleep_duration_min": health.get("sleep_duration_min"),
            "hrv": health.get("hrv"),
            "hrv_assessment": health.get("hrv_assessment"),
            "resting_hr_bpm": health.get("resting_heart_rate"),
            "stress": health.get("stress"),
            "metric_date": health.get("metric_date"),
        },
        "readiness": {
            "action": readiness.get("action"),
            "reason": readiness.get("reason"),
            "flags": flags,
            "sore_signals": sore,
        },
        "limitations": {
            "active": active,
            "past": injuries.get("past") or [],
            "avoid": avoid,
            "active_back_limitation": back_limited,
        },
    }
    return (
        "ATHLETE STATE (put into 🧠 COACH'S VERDICT bullets — not a fifth essay)\n"
        + _json(payload)
    )


def template_autopsy(
    message: str,
    safety: dict,
    science_hits: list[dict],
    session_packet: dict | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """Deterministic fallback when no provider is configured."""
    if not session_packet:
        return {
            "reply": (
                "⚡ THE BOTTOM LINE\n"
                "No AI provider is configured — this is the rule-based read.\n\n"
                f"🧠 COACH'S VERDICT & RECOVERY\n"
                f"1. {(safety.get('readiness') or {}).get('reason') or 'Train as the safety rules allow.'}\n"
                f"2. Re-ask once an AI provider is set if you want the full Metric → Biology → Example audit.\n"
                f"3. {message.strip()[:160]}"
            ),
            "citations": [
                hit["citation"]["slug"]
                for hit in science_hits[:2]
                if hit.get("citation", {}).get("slug")
            ],
            "escalate": False,
            "escalation_reason": None,
            "intent": "chat",
        }
    modality = session_packet.get("modality") or coach_modality(
        session_packet.get("sport"), session_packet.get("family")
    )
    load = safety.get("load") or {}
    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    injuries = safety.get("injuries") or {}
    hr = session_packet.get("heart_rate") or {}
    power = session_packet.get("power") or {}
    cadence = session_packet.get("cadence") or {}
    swim = session_packet.get("swim") or {}
    name = session_packet.get("name") or "the session"
    when = session_packet.get("when") or session_packet.get("date") or "recently"
    minutes = session_packet.get("minutes")
    classification = session_packet.get("classification") or "unclassified"
    acwr = load.get("minutes_acwr")
    peak = hr.get("max_bpm")
    pct_max = hr.get("pct_max_peak")
    decoupling = hr.get("decoupling_pct")
    cad = cadence.get("avg_spm") or cadence.get("avg_rpm")

    overlay = session_packet.get("prescribed_vs_executed") or {}
    week = session_packet.get("week_plan_session") or {}
    ride_verdict = (
        f"{name} ({when}): {minutes} min bike classified **{classification}** — judge the watts, not average HR."
    )
    if overlay.get("aligned") or overlay.get("vo2_caps"):
        hit = overlay.get("hit_rate")
        vo2 = overlay.get("vo2_caps") or []
        vo2_laps = ", ".join(f"Lap {row.get('lap')}" for row in vo2) or "VO2 caps"
        week_bit = ""
        if week.get("title"):
            week_bit = f" Week-plan match: {week.get('date')} {week.get('title')}."
        ride_verdict = (
            f"{name} ({when}): prescribed over-under with 280 W VO2 finishers ({vo2_laps}) — "
            f"plan hit-rate {hit}.{week_bit}"
        )
    verdicts = {
        MODALITY_RUN: (
            f"{name} ({when}): {minutes} min running classified **{classification}** — impact work, not a bike file."
        ),
        MODALITY_RIDE: ride_verdict,
        MODALITY_SWIM: (
            f"{name} ({when}): {minutes} min swim classified **{classification}** — efficiency first, not wattage."
        ),
        MODALITY_STRENGTH: (
            f"{name} ({when}): {minutes} min lift — volume load and neuromuscular strain, not missed endurance."
        ),
        MODALITY_YOGA: (
            f"{name} ({when}): {minutes} min yoga/mobility — down-regulation, not a failed interval session."
        ),
        MODALITY_OTHER: (
            f"{name} ({when}): {minutes} min classified **{classification}**."
        ),
    }

    mechanical: list[str] = []
    cardio: list[str] = []
    if modality == MODALITY_RIDE and (power.get("np_w") or power.get("avg_w")):
        mechanical.append(
            _triplet(
                "Normalized power",
                f"{power.get('np_w')} W ({power.get('pct_ftp_np')}% FTP) · IF {power.get('intensity_factor')} · TSS {power.get('tss')}",
                "The aerobic engine held a higher effective load than the average wattage because surges cost extra.",
                "Think of NP like a hilly commute vs the same distance on flat road — same time, more fuel burned.",
            )
        )
        if cad:
            mechanical.append(f"• **Cadence**: {cad} rpm")
    elif modality == MODALITY_RUN:
        pace = session_packet.get("pace_min_per_km")
        if pace:
            mechanical.append(f"• **Pace**: {pace} min/km over {session_packet.get('km')} km")
        if cad:
            mechanical.append(
                _triplet(
                    "Cadence",
                    f"{cad} SPM",
                    "Stride rate sets how many ground-reaction hits the calf-Achilles-quad chain takes per minute.",
                    "Think of it like tyre RPM: a slightly quicker, shorter step often means less braking per strike.",
                )
            )
    elif modality == MODALITY_SWIM:
        if swim.get("swolf") is not None:
            mechanical.append(
                _triplet(
                    "SWOLF",
                    str(swim.get("swolf")),
                    "Stroke count plus time is a simple efficiency score — lower usually means more hull, less thrash.",
                    "Think of it like fuel economy: same pool length, fewer strokes is a more efficient engine.",
                )
            )
        else:
            mechanical.append("• **SWOLF**: **Missing** — do not invent it.")
        if swim.get("stroke_count"):
            mechanical.append(f"• **Stroke count**: {swim.get('stroke_count')}")
    elif modality == MODALITY_STRENGTH:
        exercises = session_packet.get("exercises") or []
        if exercises:
            for item in exercises[:8]:
                mechanical.append(
                    f"• **{item.get('name') or 'Lift'}**: {item.get('sets') or '?'} sets"
                )
        else:
            mechanical.append("• **Exercises**: **Missing** from the file — duration and HR only.")
        mechanical.append(
            _triplet(
                "Session length",
                f"{minutes} min",
                "Time under tension and set density drive motor-unit recruitment more than average heart rate.",
                "Think of it like a construction shift: the load on the crane matters more than how fast the operator's pulse ran.",
            )
        )
    elif modality == MODALITY_YOGA:
        mechanical.append(f"• **Duration**: {minutes} min of range and down-regulation, not VO2 work.")
    else:
        mechanical.append(f"• **Duration**: {minutes} min")
        if session_packet.get("km"):
            mechanical.append(f"• **Distance**: {session_packet.get('km')} km")

    work = session_packet.get("work_laps") or []
    if overlay.get("blocks") or overlay.get("vo2_caps") or overlay.get("key_laps"):
        if overlay.get("hit_rate") is not None:
            mechanical.append(f"• **Plan hit-rate**: {overlay.get('hit_rate')} of prescribed watt targets")
        for block in overlay.get("blocks") or []:
            vo2 = block.get("vo2_cap") or {}
            mechanical.append(
                f"• **Block {block.get('block')}**: under {block.get('under_w')} W · "
                f"over {block.get('over_w')} W · **Lap {vo2.get('lap')} (VO2 cap)** {vo2.get('executed_w')} W"
            )
        for line in overlay.get("key_laps") or []:
            mechanical.append(f"• {line}")
    elif work:
        mechanical.append("• **Work laps** (one line each):")
        for lap in work[:12]:
            label = lap.get("label") or f"Lap {lap.get('index')}"
            role = lap.get("role") or "work"
            if lap.get("avg_power"):
                mechanical.append(
                    f"  – **{label} ({role})**: {lap.get('avg_power')} W · {lap.get('pct_ftp')}% FTP"
                    + (f" · HR {lap.get('avg_hr')}" if lap.get("avg_hr") else "")
                )
            else:
                mechanical.append(
                    f"  – **{label} ({role})**: {lap.get('duration_min')} min · HR {lap.get('avg_hr')}"
                )
    elif modality in {MODALITY_RIDE, MODALITY_RUN, MODALITY_SWIM}:
        mechanical.append("• **Interval laps**: **No interval laps** in the packet.")

    if peak:
        cardio.append(
            _triplet(
                "Peak heart rate",
                f"{peak} bpm ({pct_max}% of max)" if pct_max is not None else f"{peak} bpm",
                "Peak HR is the ceiling the pump hit — not the session type, and not the average.",
                "Think of average HR like average speed in city traffic: the red lights hide how hard the sprints were.",
            )
        )
    if decoupling is not None:
        cardio.append(
            _triplet(
                "Cardiovascular decoupling",
                f"{decoupling}%",
                "Heart rate drifted relative to the mechanical output — heat, fluid, or accumulating fatigue making the pump work harder for the same work.",
                "Think of a car engine running hotter as the radiator fluid drops: same throttle, higher revs to hold speed.",
            )
        )
    if hr.get("avg_bpm"):
        cardio.append(f"• **Average HR**: {hr.get('avg_bpm')} bpm — not the session type.")
    if not cardio:
        cardio.append("• **Heart-rate / decoupling**: **Missing** from this file.")

    back = ", ".join(injuries.get("active") or []) or "none listed"
    action_3 = {
        MODALITY_RUN: "Next run stays easy or switch to the bike if tissue feels heavy — no added downhill or speed.",
        MODALITY_RIDE: "Next bike: easy endurance or off the trainer if indoor heat drove the decoupling.",
        MODALITY_SWIM: "Next swim: technique/broken sets, not a dense threshold block if shoulders feel cooked.",
        MODALITY_STRENGTH: "Next lift: keep RPE, drop volume 20% if sleep/HRV is still down. No forbidden spinal-load patterns.",
        MODALITY_YOGA: "Protect the next quality day. Do not pile impact onto a back that is already limited.",
        MODALITY_OTHER: "Keep the next session honest to the load you just took on.",
    }.get(modality, "Keep the next session honest to the load you just took on.")

    lines = [
        "⚡ THE BOTTOM LINE",
        verdicts.get(modality, verdicts[MODALITY_OTHER]),
        "",
        "🔬 MECHANICAL PRECISION",
        *mechanical,
        "",
        "🫀 CARDIOVASCULAR COST",
        *cardio,
        "",
        "🧠 COACH'S VERDICT & RECOVERY",
        (
            f"1. ACWR {acwr} ({load.get('acute_minutes')} min / {load.get('chronic_minutes')} min chronic) "
            "— treat the next 24-48h as a load-management window, not a fitness test."
            if acwr is not None
            else "1. ACWR is **Missing** — default to conservative next-day loading."
        ),
        (
            f"2. Sleep score {health.get('sleep_score')}, HRV {health.get('hrv')} "
            f"({health.get('hrv_assessment') or 'unlabelled'}), resting HR "
            f"{health.get('resting_heart_rate')} bpm. Active limits: {back}."
            if health
            else f"2. No sleep/HRV check-in on file. Active limits: {back}."
        ),
        f"3. {action_3}",
    ]
    if science_hits:
        top = science_hits[0]
        lines.extend(["", f"• Evidence: {top.get('heading')}"])
    return {
        "reply": "\n".join(part for part in lines if part is not None),
        "citations": [
            hit["citation"]["slug"]
            for hit in science_hits[:2]
            if hit.get("citation", {}).get("slug")
        ],
        "escalate": False,
        "escalation_reason": None,
        "intent": "WORKOUT_AUDIT",
    }


def template_general_chat(
    message: str,
    safety: dict,
    science_hits: list[dict],
) -> dict[str, Any]:
    reason = (safety.get("readiness") or {}).get("reason") or "Train inside the safety rules."
    return {
        "reply": (
            "I can autopsy a past session, revise this week's calendar, or answer a training question.\n\n"
            f"{reason}\n\n"
            f"You asked: {message.strip()[:200]}"
        ),
        "citations": [
            hit["citation"]["slug"]
            for hit in science_hits[:2]
            if hit.get("citation", {}).get("slug")
        ],
        "escalate": False,
        "escalation_reason": None,
        "intent": "GENERAL_CHAT",
    }


def template_schedule(
    message: str,
    safety: dict,
    science_hits: list[dict],
    *,
    current_plan: dict | None = None,
    context: dict | None = None,
    clock: dict | None = None,
) -> dict[str, Any]:
    """Deterministic Pro Olympic Coach fallback — never an autopsy, never an essay."""
    from datetime import timedelta

    load = safety.get("load") or {}
    injuries = safety.get("injuries") or {}
    health = ((context or {}).get("coros") or {}).get("latest_health") or {}
    acwr = load.get("minutes_acwr")
    active = injuries.get("active") or []
    back_limited = any(
        "back" in str(item).lower() or "spine" in str(item).lower() for item in active
    )
    weekdays = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    today = (clock or {}).get("today")
    week_start = (clock or {}).get("week_start")
    by_date: dict[str, dict] = {}
    for workout in ((current_plan or {}).get("plan") or {}).get("workouts") or []:
        by_date[str(workout.get("date") or "")[:10]] = workout

    score, source = readiness_score(health, safety)
    band, status_label = today_call_status(score)
    sleep = health.get("sleep_score")
    hrv = health.get("hrv")
    score_display = f"{score} ({source})" if score is not None else "Missing"

    rows = [
        "| Day | Session | Primary Focus | Intensity | Coach's Secret Rule |",
        "|---|---|---|---|---|",
    ]
    hard_days: list[str] = []
    for index, name in enumerate(weekdays):
        day = week_start + timedelta(days=index) if week_start is not None else None
        iso = day.isoformat() if day is not None else ""
        workout = by_date.get(iso) or {}
        session = workout.get("title") or workout.get("session_type") or "Unplanned"
        focus = workout.get("sport") or workout.get("session_type") or "—"
        intensity = workout.get("intensity") or workout.get("session_type") or "—"
        past = bool(today and day and day < today)
        secret = _secret_rule(workout, session, intensity, past=past)
        rows.append(f"| {name} | {session} | {focus} | {intensity} | {secret} |")
        session_l = f"{session} {intensity}".lower()
        if any(
            token in session_l
            for token in ("hard", "threshold", "interval", "vo2", "quality", "race")
        ):
            hard_days.append(name)

    if back_limited:
        spine_lines = [
            "• **DO NOT:** back squat, deadlift, crunch, sit-up, good morning, loaded twist.",
            "• **DO:** anti-extension only — dead bug, bird dog, side plank.",
            "• Strength days: unilateral lower body. Spine is a pillar, never a loaded hinge.",
        ]
    else:
        spine_lines = ["• **No spinal lock on file.**"]

    translations = _schedule_translations(
        acwr=acwr,
        sleep=sleep,
        hrv=hrv,
        back_limited=back_limited,
        hard_days=hard_days,
    )

    lines = [
        "🟢 TODAY'S CALL",
        f"**{status_label}**",
        f"**Readiness:** {score_display}",
        f"**Sleep:** {sleep if sleep is not None else 'Missing'}",
        f"**HRV:** {hrv if hrv is not None else 'Missing'}",
        f"**ACWR:** {acwr if acwr is not None else 'Missing'}",
        "",
        "🗣️ LOCKER ROOM DIRECTIVE",
        _LOCKER_DIRECTIVES[band],
        "",
        "🗓️ REVISED WEEK",
        *rows,
        "",
        "🛡️ SPINE LOCK",
        *spine_lines,
        "",
        "🔬 WEEKLY TRANSLATIONS",
        *translations,
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
        "intent": "SCHEDULE_UPDATE",
    }


def _secret_rule(workout: dict, session: str, intensity: str, *, past: bool) -> str:
    if past:
        return "Done" if workout else "Missed"
    blob = f"{session} {intensity} {workout.get('sport') or ''} {workout.get('session_type') or ''}".lower()
    if any(token in blob for token in ("football", "soccer", "11v11", "match")):
        return "Chaos load. Yesterday's legs must already be paid for."
    if any(token in blob for token in ("strength", "armor", "gym", "lift")):
        return "Unilateral only. If the spine hinges under load, the set is illegal."
    if any(token in blob for token in ("hard", "threshold", "interval", "vo2", "quality")):
        return "Work is work. Easy is the gap after — don't bleed them together."
    if "long" in blob:
        return "If you can't sing while moving, you're going too fast."
    if "rest" in blob:
        return "Feet up. No 'just a little extra'."
    if "mobility" in blob or "yoga" in blob:
        return "Range first. No hero stretching into a spasm."
    return "Easy means you can talk. If you can't, back off."


def _schedule_translations(
    *,
    acwr: Any,
    sleep: Any,
    hrv: Any,
    back_limited: bool,
    hard_days: list[str],
) -> list[str]:
    blocks: list[str] = []
    if sleep is not None:
        blocks.append(
            _call_triplet(
                f"Sleep score {sleep} (readiness band uses this 0-100 check-in)",
                "Your overnight recharge is the day's permission slip, not a vibe.",
                f"Think of this like a battery at {sleep}% — it finishes the workday, it does not start a new project.",
            )
        )
    elif hrv is not None:
        blocks.append(
            _call_triplet(
                f"HRV {hrv} with no sleep score on file",
                "The nervous system is talking. Don't shout over it with extra intensity.",
                "Like a radio with weak signal — turning the volume up just adds noise.",
            )
        )
    if isinstance(acwr, (int, float)):
        if acwr >= 1.3:
            blocks.append(
                _call_triplet(
                    f"ACWR {acwr} — acute load spiked vs 28-day chronic",
                    "You've been spending faster than the tissue bank can refill.",
                    "Like stacking overtime weeks — the paycheck looks big until the injury invoice lands.",
                )
            )
        else:
            blocks.append(
                _call_triplet(
                    f"ACWR {acwr} — acute:chronic in range",
                    "The weekly volume is legal. Don't invent a fourth hard day.",
                    "Like a well-built scaffold — it holds if you don't hang extra bricks on one side.",
                )
            )
    if back_limited:
        blocks.append(
            _call_triplet(
                "Active lower-back / spinal limitation — high compressive and shear risk under axial load",
                "The spine is a pillar this week. No hinge-under-load on strength days.",
                "Treat it like a cracked mast: you can still sail, you do not hang extra sails on it.",
            )
        )
    elif len(hard_days) >= 2:
        blocks.append(
            _call_triplet(
                f"Quality days currently sit on {', '.join(hard_days)}",
                "Hard days need an easy day between them. Stacking them is how niggles become layoffs.",
                "Like two race days with no cooldown lap — the engine overheats even if the dashboard looks fine.",
            )
        )
    return blocks[:4]


def _call_triplet(science: str, lingo: str, example: str) -> str:
    return (
        f"• 🔬 THE SCIENCE: {science}\n"
        f"• 🗣️ LOCKER ROOM LINGO: {lingo}\n"
        f"• 💡 REAL-WORLD EXAMPLE: {example}"
    )


def _triplet(name: str, value: str, biology: str, example: str) -> str:
    return (
        f"• METRIC: **{name}** {value}\n"
        f"  THE BIOLOGY: {biology}\n"
        f"  💡 EXAMPLE: {example}"
    )


def _json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, default=str)
