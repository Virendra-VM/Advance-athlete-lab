"""Parse an athlete's prescribed session and score it against executed laps.

The coach used to treat every hard lap as a generic 'over'. Athletes prescribe
structure (warmup, preamble, under/over, VO2 cap, cooldown). This module turns
that paste — and the weekly plan row — into a planned-vs-executed overlay the
prompt must obey.
"""

from __future__ import annotations

import re
from typing import Any

DURATION_RE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)\s*(?:mins?|min|minutes?|m)\b",
    re.IGNORECASE,
)
WATTS_RE = re.compile(r"(?P<w>\d{2,4})\s*(?:w|watts)\b", re.IGNORECASE)
REPEAT_RE = re.compile(
    r"repeat(?:\s+this\s+set)?\s+(\d+)\s+times",
    re.IGNORECASE,
)
VO2_LAPS_RE = re.compile(
    r"laps?\s+((?:\d+\s*(?:,|and|&)?\s*)+)\s+(?:are|is|were|was)\s+(?:the\s+)?vo2",
    re.IGNORECASE,
)
MAIN_HINT = re.compile(r"main set|under and over|over-under|over under", re.IGNORECASE)
COOL_HINT = re.compile(r"cool\s*-?\s*down", re.IGNORECASE)
WARM_HINT = re.compile(r"warm\s*-?\s*up", re.IGNORECASE)


def parse_prescribed_workout(text: str) -> dict[str, Any] | None:
    """Return expanded steps or None if the message is not a structured prescription."""
    if not text or not DURATION_RE.search(text):
        return None
    if not (WATTS_RE.search(text) or MAIN_HINT.search(text) or WARM_HINT.search(text)):
        return None

    preamble: list[dict[str, Any]] = []
    main_block: list[dict[str, Any]] = []
    cooldown: list[dict[str, Any]] = []
    section = "preamble"
    repeats = 1

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        repeat_match = REPEAT_RE.search(line)
        if repeat_match:
            repeats = max(1, int(repeat_match.group(1)))
            continue
        if MAIN_HINT.search(line) and not DURATION_RE.search(line):
            section = "main"
            continue
        if COOL_HINT.search(line) and not WATTS_RE.search(line):
            section = "cooldown"
        step = _parse_step_line(line, section)
        if step is None:
            if COOL_HINT.search(line):
                section = "cooldown"
            elif WARM_HINT.search(line):
                section = "preamble"
            continue
        if step["role"] == "cooldown" or section == "cooldown":
            step["role"] = "cooldown"
            cooldown.append(step)
        elif section == "main":
            main_block.append(step)
        else:
            preamble.append(step)

    if main_block:
        _label_main_block(main_block)

    if not preamble and not main_block and not cooldown:
        return None
    if not main_block and not any(step.get("target_w") for step in preamble):
        return None

    steps: list[dict[str, Any]] = []
    steps.extend(preamble)
    for block_index in range(repeats):
        for step in main_block:
            cloned = dict(step)
            cloned["block"] = block_index + 1
            steps.append(cloned)
    steps.extend(cooldown)
    if len(steps) < 3:
        return None
    for index, step in enumerate(steps, start=1):
        step["index"] = index
    return {
        "source": "athlete_message",
        "repeats": repeats,
        "main_steps_per_block": len(main_block),
        "step_count": len(steps),
        "steps": steps,
        "vo2_lap_overrides": _parse_vo2_laps(text),
    }


def _parse_step_line(line: str, section: str) -> dict[str, Any] | None:
    duration_match = DURATION_RE.search(line)
    if not duration_match:
        return None
    minutes = float(duration_match.group("n"))
    if minutes <= 0 or minutes > 180:
        return None
    watts_match = WATTS_RE.search(line)
    watts = int(watts_match.group("w")) if watts_match else None
    lower = line.lower()
    role = "work"
    if WARM_HINT.search(lower):
        role = "warmup"
    elif COOL_HINT.search(lower):
        role = "cooldown"
    elif "rest" in lower or "recovery" in lower:
        role = "recovery"
    elif "vo2" in lower:
        role = "vo2_cap"
    elif section == "preamble" and watts:
        role = "preamble"
    return {
        "duration_s": int(round(minutes * 60)),
        "target_w": watts,
        "role": role,
        "section": "cooldown" if role == "cooldown" else section,
        "raw": line[:160],
    }


def _label_main_block(block: list[dict[str, Any]]) -> None:
    targets = sorted({step["target_w"] for step in block if step.get("target_w")})
    if not targets:
        return
    lowest, highest = targets[0], targets[-1]
    for step in block:
        if step["role"] in {"recovery", "vo2_cap"}:
            continue
        watts = step.get("target_w")
        if watts is None:
            continue
        if watts == highest and highest > lowest:
            step["role"] = "vo2_cap"
        elif watts == lowest:
            step["role"] = "under"
        else:
            step["role"] = "over"


def _parse_vo2_laps(text: str) -> list[int]:
    match = VO2_LAPS_RE.search(text or "")
    if not match:
        return []
    return [int(value) for value in re.findall(r"\d+", match.group(1))]


def align_laps_to_plan(
    laps: list[dict[str, Any]],
    prescription: dict[str, Any],
    *,
    ftp: float | None = None,
) -> dict[str, Any]:
    steps = list(prescription.get("steps") or [])
    if not laps or not steps:
        return {"aligned": False, "reason": "missing_laps_or_steps"}

    paired: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if abs(len(laps) - len(steps)) <= 1:
        for lap, step in zip(laps, steps):
            paired.append((lap, step))
    else:
        return {"aligned": False, "reason": "lap_count_mismatch", "laps": len(laps), "steps": len(steps)}

    overrides = set(prescription.get("vo2_lap_overrides") or [])
    rows = []
    hits = 0
    for lap, step in paired:
        actual = lap.get("avg_power")
        target = step.get("target_w")
        delta = None
        pct_error = None
        hit = None
        if actual is not None and target:
            delta = round(float(actual) - float(target), 1)
            pct_error = round(100.0 * delta / float(target), 1)
            hit = abs(delta) <= max(8.0, 0.04 * float(target))
            if hit:
                hits += 1
        role = step.get("role") or lap.get("role")
        lap_index = lap.get("index")
        if lap_index in overrides:
            role = "vo2_cap"
        pct_ftp = None
        if ftp and actual:
            pct_ftp = round(100.0 * float(actual) / float(ftp))
        row = {
            "index": lap_index,
            "label": lap.get("label") or f"Lap {lap_index}",
            "role": role,
            "block": step.get("block"),
            "planned_s": step.get("duration_s"),
            "executed_s": lap.get("duration_s"),
            "planned_w": target,
            "executed_w": actual,
            "delta_w": delta,
            "pct_error": pct_error,
            "hit": hit,
            "pct_ftp": pct_ftp or lap.get("pct_ftp"),
            "avg_hr": lap.get("avg_hr"),
            "avg_cadence": lap.get("avg_cadence"),
        }
        rows.append(row)

    return {
        "aligned": True,
        "hit_rate": round(hits / max(1, sum(1 for row in rows if row["planned_w"])), 2),
        "laps": rows,
        "blocks": _block_summaries(rows),
        "vo2_caps": [row for row in rows if row["role"] == "vo2_cap"],
        "overs": [row for row in rows if row["role"] == "over"],
        "unders": [row for row in rows if row["role"] == "under"],
    }


def _block_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        block = row.get("block")
        if not block:
            continue
        grouped.setdefault(int(block), []).append(row)
    summaries = []
    for block in sorted(grouped):
        steps = grouped[block]
        vo2 = next((row for row in steps if row["role"] == "vo2_cap"), None)
        overs = [row for row in steps if row["role"] == "over"]
        unders = [row for row in steps if row["role"] == "under"]
        summaries.append(
            {
                "block": block,
                "laps": [row["index"] for row in steps],
                "under_w": _mean([row["executed_w"] for row in unders]),
                "over_w": _mean([row["executed_w"] for row in overs]),
                "vo2_cap": {
                    "lap": vo2.get("index"),
                    "planned_w": vo2.get("planned_w"),
                    "executed_w": vo2.get("executed_w"),
                    "avg_hr": vo2.get("avg_hr"),
                }
                if vo2
                else None,
            }
        )
    return summaries


def apply_roles_from_alignment(
    laps: list[dict[str, Any]], alignment: dict[str, Any]
) -> list[dict[str, Any]]:
    if not alignment.get("aligned"):
        return laps
    by_index = {row["index"]: row for row in alignment.get("laps") or []}
    for lap in laps:
        mapped = by_index.get(lap.get("index"))
        if not mapped:
            continue
        lap["role"] = mapped["role"]
        lap["planned_w"] = mapped.get("planned_w")
        lap["delta_w"] = mapped.get("delta_w")
        lap["hit"] = mapped.get("hit")
        lap["block"] = mapped.get("block")
    return laps


def compact_execution_overlay(alignment: dict[str, Any]) -> dict[str, Any] | None:
    if not alignment.get("aligned"):
        return None
    rows = alignment.get("laps") or []

    def _line(row: dict[str, Any]) -> str:
        planned = row.get("planned_w")
        executed = row.get("executed_w")
        delta = row.get("delta_w")
        sign = f"{delta:+.0f} W" if delta is not None else "n/a"
        return (
            f"Lap {row.get('index')} ({row.get('role')}): "
            f"planned {planned} W → {executed} W ({sign})"
        )

    return {
        "aligned": True,
        "hit_rate": alignment.get("hit_rate"),
        "blocks": alignment.get("blocks"),
        "vo2_caps": [
            {
                "lap": row.get("index"),
                "planned_w": row.get("planned_w"),
                "executed_w": row.get("executed_w"),
                "avg_hr": row.get("avg_hr"),
            }
            for row in alignment.get("vo2_caps") or []
        ],
        "key_laps": [
            _line(row)
            for row in rows
            if row.get("role") in {"over", "vo2_cap", "under", "warmup", "cooldown"}
            and (
                row.get("role") in {"vo2_cap", "warmup", "cooldown"}
                or (row.get("role") == "over" and (row.get("index") or 0) <= 11)
                or (row.get("role") == "under" and row.get("block") == 1)
            )
        ][:16],
    }


def match_week_plan_session(
    plan: dict | None,
    session_date: str | None,
    family: str | None,
) -> dict[str, Any] | None:
    if not plan or not session_date:
        return None
    workouts = (plan.get("plan") or {}).get("workouts") or []
    same_day = [
        workout
        for workout in workouts
        if str(workout.get("date") or "")[:10] == str(session_date)[:10]
    ]
    if not same_day:
        return None
    family_key = (family or "").lower()
    sport_aliases = {
        "ride": ("cycl", "bike", "ride"),
        "run": ("run",),
        "swim": ("swim",),
        "strength": ("strength", "gym", "weight"),
        "yoga": ("yoga", "mobility"),
    }
    aliases = sport_aliases.get(family_key, ())
    ranked = []
    for workout in same_day:
        sport = str(workout.get("sport") or "").lower()
        score = 2 if any(alias in sport for alias in aliases) else 0
        ranked.append((score, workout))
    ranked.sort(key=lambda item: item[0], reverse=True)
    best = ranked[0][1]
    return {
        "date": best.get("date"),
        "title": best.get("title"),
        "sport": best.get("sport"),
        "session_type": best.get("session_type"),
        "duration_min": best.get("duration_min"),
        "intensity": best.get("intensity"),
        "description": (best.get("description") or "")[:280],
        "sport_match": ranked[0][0] >= 2,
    }


def collect_prescription_text(message: str, history: list[dict] | None = None) -> str:
    """Use one prescribed workout, not a concat of every user turn.

    Concatenating two copies of the same set would double the steps and
    fail 1:1 lap alignment on the follow-up correction.
    """
    if parse_prescribed_workout(message or ""):
        return message or ""
    for entry in reversed(history or []):
        if entry.get("role") != "user":
            continue
        body = (entry.get("content") or "").strip()
        if parse_prescribed_workout(body):
            return body
    return message or ""


def build_session_plan_overlay(
    *,
    message: str,
    history: list[dict] | None,
    laps: list[dict[str, Any]],
    ftp: float | None,
    week_plan: dict | None,
    session_date: str | None,
    family: str | None,
) -> dict[str, Any]:
    text = collect_prescription_text(message, history)
    prescription = parse_prescribed_workout(text)
    overlay: dict[str, Any] = {
        "week_plan_session": match_week_plan_session(week_plan, session_date, family),
    }
    if prescription is None:
        return overlay
    alignment = align_laps_to_plan(laps, prescription, ftp=ftp)
    if alignment.get("aligned"):
        apply_roles_from_alignment(laps, alignment)
    overlay["prescription"] = {
        "repeats": prescription.get("repeats"),
        "main_steps_per_block": prescription.get("main_steps_per_block"),
        "step_count": prescription.get("step_count"),
        "vo2_lap_overrides": prescription.get("vo2_lap_overrides"),
    }
    overlay["prescribed_vs_executed"] = compact_execution_overlay(alignment) or alignment
    if alignment.get("aligned") and alignment.get("vo2_caps"):
        overlay["classification_note"] = "over-under with VO2-cap finishers — not generic overs"
    return overlay


def _mean(values: list[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)
