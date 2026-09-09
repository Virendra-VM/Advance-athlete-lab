"""Deterministic warmup / main / cooldown detail for planned sessions.

LLM week tables often land as a title plus an empty structure. These blueprints
fill named work for run, bike, swim, strength, yoga, and the rest so Schedule
and Coach always have something an athlete can follow.
"""

from __future__ import annotations

HARD_TYPES = {
    "tempo",
    "threshold",
    "intervals",
    "hills",
    "speed",
    "race",
}

_QUALITY_TOKENS = ("interval", "threshold", "vo2", "ftp", "over-under", "over under")


def enrich_plan(plan_data: dict, safety: dict | None = None) -> dict:
    plan = dict(plan_data or {})
    plan["workouts"] = [enrich_workout(item, safety) for item in plan.get("workouts") or []]
    return plan


def enrich_workout(workout: dict, safety: dict | None = None) -> dict:
    """Return a copy with warmup / main / cooldown detail when the row is thin."""
    item = dict(workout or {})
    session_type = str(item.get("session_type") or "easy").strip().lower()
    if session_type == "rest":
        item["structure"] = _rest_structure()
        if not (item.get("description") or "").strip():
            item["description"] = (
                "Full rest. Optional 8–10 min easy mobility if you feel restless — no training load."
            )
        return item

    duration = _duration(item.get("duration_min"))
    if not _structure_is_thin(item.get("structure"), session_type):
        return item

    family = sport_family(item.get("sport"), session_type, item.get("title"))
    spine_lock = bool((safety or {}).get("spine_lock"))
    warmup_min, main_min, cooldown_min = _split_duration(duration)
    warmup = _warmup(family, warmup_min)
    main = _main_set(family, session_type, main_min, spine_lock=spine_lock, title=item.get("title"))
    cooldown = _cooldown(family, cooldown_min)
    item["structure"] = [warmup, main, cooldown]
    if not (item.get("description") or "").strip():
        item["description"] = (
            f"{warmup['segment']} ({warmup_min} min): {warmup['detail']} "
            f"{main['segment']} ({main_min} min): {main['detail']} "
            f"{cooldown['segment']} ({cooldown_min} min): {cooldown['detail']}"
        )
    return item


def downgrade_today_workout(workout: dict, safety: dict | None = None) -> dict:
    """Keep duration and sport; drop quality when today's health call is poor."""
    item = dict(workout or {})
    action = ((safety or {}).get("readiness") or {}).get("action") or "proceed"
    auto = (safety or {}).get("autoregulation") or (safety or {}).get("todays_call") or {}
    call_level = str(auto.get("call_level") or "").lower()
    session_type = str(item.get("session_type") or "").lower()
    sport = item.get("sport") or "aerobic"
    duration = item.get("duration_min")
    rest_today = action == "rest_or_mobility" or call_level == "rest"
    hard = session_type in HARD_TYPES
    easy_today = hard or action == "downgrade_to_easy" or call_level in {"easy", "caution"}
    if rest_today:
        item["session_type"] = "mobility"
        item["title"] = "Restore / mobility"
        item["intensity"] = "Recovery"
        item["description"] = (
            "Today-only adjustment for poor HRV, readiness, stress, or ACWR. "
            "Keep the rest of the week. Easy mobility and breathing only."
        )
    elif easy_today:
        item["session_type"] = "easy"
        item["title"] = f"Easy {sport}"
        item["intensity"] = "Easy / conversational"
        item["description"] = (
            "Today-only adjustment: quality converted to easy aerobic at the same duration. "
            "The rest of the week stays as written."
        )
    item["duration_min"] = duration
    item["structure"] = []
    return enrich_workout(item, safety)


def sport_family(sport: str | None, session_type: str | None = None, title: str | None = None) -> str:
    blob = f"{sport or ''} {session_type or ''} {title or ''}".lower()
    if any(token in blob for token in ("yoga", "mobility", "pilates", "stretch")):
        return "yoga"
    if any(token in blob for token in ("strength", "gym", "lift", "armor", "weights")):
        return "strength"
    if any(token in blob for token in ("swim", "pool")):
        return "swim"
    if any(token in blob for token in ("cycl", "bike", "ride", "spin")):
        return "ride"
    if any(token in blob for token in ("run", "jog", "trail")):
        return "run"
    if any(token in blob for token in ("row", "erg")):
        return "row"
    if any(token in blob for token in ("football", "soccer", "11v11", "team")):
        return "team"
    if any(token in blob for token in ("walk", "hike")):
        return "walk"
    return "easy"


def _duration(value) -> int:
    try:
        minutes = int(round(float(value)))
    except (TypeError, ValueError):
        minutes = 45
    return max(20, min(minutes, 420))


def _split_duration(total: int) -> tuple[int, int, int]:
    warmup = 8 if total < 40 else 10 if total < 90 else 12
    cooldown = 8 if total < 40 else 10
    if warmup + cooldown >= total:
        warmup = max(5, total // 5)
        cooldown = max(5, total // 5)
    main = max(8, total - warmup - cooldown)
    return warmup, main, cooldown


def _structure_is_thin(structure, session_type: str) -> bool:
    if not isinstance(structure, list) or not structure:
        return True
    blob = " ".join(
        f"{item.get('segment') or ''} {item.get('detail') or ''} {item.get('intensity') or ''}"
        for item in structure
        if isinstance(item, dict)
    ).lower()
    details = [
        str(item.get("detail") or "").strip()
        for item in structure
        if isinstance(item, dict)
    ]
    named = any(len(detail) >= 24 for detail in details)
    has_bookends = "warm" in blob and any(token in blob for token in ("cool", "stretch", "foam"))
    if session_type in {"easy", "mobility", "long"} and any(token in blob for token in _QUALITY_TOKENS):
        return True
    if named and has_bookends:
        return False
    if named and len(structure) >= 3:
        return False
    return True


def _seg(name: str, minutes: int, intensity: str, detail: str) -> dict:
    return {
        "segment": name,
        "duration_min": minutes,
        "intensity": intensity,
        "detail": detail,
    }


def _rest_structure() -> list[dict]:
    return [
        _seg(
            "Rest / optional mobility",
            10,
            "Easy",
            "No training load. If restless: 5 min easy walk, then 5 min hip and thoracic mobility. Stop there.",
        )
    ]


def _warmup(family: str, minutes: int) -> dict:
    details = {
        "run": (
            "Easy jog 4 min. Dynamic: leg swings, world's greatest stretch, 2 × 20 m strides. "
            "Ankle circles and calf raises."
        ),
        "ride": (
            "Easy spin 5 min, cadence 85–95. 3 × 30 s spin-ups, 30 s easy. Open hips on the bike; "
            "no hard efforts yet."
        ),
        "swim": (
            "200–400 easy mixed stroke. 4 × 50 drill / swim. Shoulder circles and band pull-aparts on deck."
        ),
        "strength": (
            "5 min easy bike or walk. Then: world's greatest stretch, glute bridge, 2 × 8 bodyweight squats, "
            "band pull-aparts, dead bug 1 × 6."
        ),
        "yoga": (
            "2 min easy breathing. Cat-cow, thread-the-needle, gentle sun salute × 3. No binds or deep folds yet."
        ),
        "row": "Easy row 4 min. Hip hinge drills, 10 bodyweight squats, 8 scapular rows. 2 × 10 stroke build.",
        "team": (
            "Easy jog 4 min, hip openers, 2 × 20 m skips, 2 × 20 m strides. Ankle mobility before any cutting."
        ),
        "walk": "Start very easy. Ankle circles, hip openers, 30 s each calf stretch. Build to conversational pace.",
        "easy": "Easy movement 4 min. Joint circles, 6 bodyweight squats, 6 arm circles. Then settle into the session.",
    }
    return _seg("Warm-up", minutes, "Easy", details.get(family, details["easy"]))


def _cooldown(family: str, minutes: int) -> dict:
    details = {
        "run": (
            "Easy jog/walk 4 min. Stretch calves, hip flexors, quads, 45 s each. Foam roll calves and quads 2 min. "
            "90/90 hip stretch."
        ),
        "ride": (
            "Easy spin 4 min, dropping cadence. Stretch hip flexors, quads, pecs. Foam roll quads and glutes 2 min. "
            "Child's pose or kneeling hip flexor."
        ),
        "swim": (
            "100–200 easy. Shoulder doorway stretch, lat stretch, child's pose. Foam roll lats and thoracic 2 min if available."
        ),
        "strength": (
            "Easy walk 3 min. Stretch hip flexors, pecs, hamstrings. Foam roll glutes and T-spine 2 min. "
            "90/90 hips, then 1 min easy nasal breathing."
        ),
        "yoga": (
            "Longer holds: pigeon or figure-4, supine twist, legs up the wall 2 min. Savasana 2 min. No loaded folds."
        ),
        "row": "Easy row 3 min. Hip flexor stretch, hamstring stretch, foam roll glutes and lats. Child's pose.",
        "team": (
            "Walk 4 min. Stretch adductors, hip flexors, calves. Foam roll quads and IT band 2 min. Easy breathing."
        ),
        "walk": "Slow the last minutes. Calf and hip flexor stretch 45 s each. Foam roll calves if they feel tight.",
        "easy": (
            "Easy movement 3 min. Stretch the tissues you used. Foam roll 2 min. Finish with 5 slow breaths."
        ),
    }
    return _seg("Cool-down", minutes, "Easy", details.get(family, details["easy"]))


def _main_set(
    family: str,
    session_type: str,
    minutes: int,
    *,
    spine_lock: bool,
    title: str | None,
) -> dict:
    if family == "strength" or session_type == "strength":
        return _seg("Main set", minutes, "RPE 6–7", _strength_main(spine_lock))
    if family == "yoga" or session_type == "mobility":
        return _seg("Main set", minutes, "Easy / restore", _yoga_main(minutes))
    if session_type in HARD_TYPES:
        return _seg("Main set", minutes, "Hard / controlled", _quality_main(family, session_type, minutes))
    if session_type == "long":
        return _seg("Main set", minutes, "Easy / conversational", _long_main(family, minutes))
    if family == "team":
        return _seg(
            "Main set",
            minutes,
            "Skills / game",
            "Technical work then small-sided play. Cap sprint volume. If legs are already loaded, stay on the ball, skip extra running.",
        )
    return _seg("Main set", minutes, "Easy / conversational", _easy_main(family, minutes, title))


def _strength_main(spine_lock: bool) -> str:
    if spine_lock:
        return (
            "Unilateral lower body only. Spine is a pillar — no loaded hinge or flexion. "
            "Split squat 3×8/side; glute bridge 3×10; push-up 3×8–10; single-arm row 3×10; "
            "suitcase carry 3×30 m; dead bug 3×8; bird dog 3×6/side; side plank 3×25 s. "
            "DO NOT: back squat, deadlift, crunch, sit-up, good morning, loaded twist."
        )
    return (
        "Goblet squat 3×8; Romanian deadlift 3×8; push-up or dumbbell press 3×8–10; "
        "dumbbell row 3×10; farmer carry 3×40 m; side plank 3×30 s; calf raise 3×12. "
        "Rest ~90 s. Last reps should leave 2–3 in reserve."
    )


def _yoga_main(minutes: int) -> str:
    extra = " Add 5 min thoracic rotations and 90/90 hip switches." if minutes >= 30 else ""
    return (
        "Flow: cat-cow, downward dog, low lunge, warrior II, hip opener, supine twist. "
        "Hold 4–6 breaths. Skip loaded spinal flexion if the back is irritable."
        + extra
    )


def _quality_main(family: str, session_type: str, minutes: int) -> str:
    if family == "ride":
        if session_type in {"intervals", "speed"}:
            return "3 × 6 min at strong but repeatable power (about RPE 8), 4 min easy spin between. Stay seated unless the set is a climb."
        if session_type == "hills":
            return "6 × 2 min seated climb at strong effort, 2 min easy spin down. Cadence 70–80 on the work."
        return "3 × 10 min at controlled threshold (RPE 7), 5 min easy between. No surges in the last 2 min of each rep."
    if family == "swim":
        return "8 × 100 m at strong sustainable pace (near CSS) with 20–30 s rest. Count strokes; don't thrash the last 25."
    if family == "row":
        return "5 × 4 min strong with 2 min easy. Rate 24–28 on the work. Keep the hinge long — no rounding."
    if family == "run":
        if session_type == "hills":
            return "8 × 45–60 s strong uphill, walk or jog down. Form over speed. Stop if anything sharp shows up."
        if session_type in {"intervals", "speed"}:
            return "5 × 3 min at comfortably hard (RPE 8), 2 min easy jog. Even splits; first rep is a feeler."
        return "2 × 10 min at controlled threshold (RPE 7), 3 min easy jog between. Talk in short phrases only."
    return "2 × 8 min at controlled hard effort, 3 min easy between. If it stops being repeatable, drop to easy."


def _long_main(family: str, minutes: int) -> str:
    fuel = " Start taking carbohydrate after 60 min." if minutes >= 75 else ""
    if family == "ride":
        return "Steady Z2. Cadence 80–95. You could hold a conversation." + fuel
    if family == "run":
        return "Steady conversational run. If form fades, insert 1 min walk every 10–15 min." + fuel
    if family == "swim":
        return "Broken aerobic swimming: 4–8 × 200–400 easy with 20 s rest. Smooth stroke, not a grind."
    return "Steady aerobic work you could repeat tomorrow. Fuel if it runs past 75 minutes."


def _easy_main(family: str, minutes: int, title: str | None) -> str:
    if family == "ride":
        return f"Easy spin {minutes} min. Gossip pace, nasal breathing if you can. Cadence 85–95. No surges."
    if family == "run":
        return f"Easy run {minutes} min. Talk test the whole way. If you can't sing a line, slow down."
    if family == "swim":
        return "Easy continuous or broken swimming. Count a relaxed stroke. Shoulders stay loose."
    if family == "walk":
        return "Conversational walk on easy terrain. Unclench the hands and jaw."
    label = (title or "Easy aerobic").strip()
    return f"{label}: keep it conversational the whole block. Finish able to do it again tomorrow."
