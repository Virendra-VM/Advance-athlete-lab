"""Resolve COROS/Garmin FIT exercise names and muscle targets.

COROS strength FIT files store Garmin ``ExerciseCategory`` + subtype ids
(e.g. hip_stability / 1 → Dead Bug). COROS MCP does not return the muscle
heatmap, so we derive primary/secondary muscles from the exercise category.
"""

from __future__ import annotations

from typing import Any


def _title(token: str) -> str:
    text = str(token or "").strip().replace("-", "_")
    if not text:
        return "Exercise"
    words = [w for w in text.split("_") if w]
    small = {"with", "and", "of", "to", "in", "on", "at", "for", "the", "a"}
    out: list[str] = []
    for i, w in enumerate(words):
        low = w.lower()
        if i > 0 and low in small:
            out.append(low)
        else:
            out.append(low.capitalize())
    return " ".join(out)


# Subtype lookups for categories we see in real COROS FITs (Garmin Profile).
# Keys are subtype ints; values are display names.
_SUBTYPES: dict[str, dict[int, str]] = {
    "hip_stability": {
        0: "Band Side Lying Leg Raise",
        1: "Dead Bug",
        2: "Weighted Dead Bug",
        5: "Fire Hydrant Kicks",
        7: "Hip Circles",
        9: "Inner Thigh Lift",
        16: "Quadruped",
        17: "Quadruped Hip Extension",
        21: "Side Lying Leg Raise",
        28: "Standing Hip Abduction",
    },
    "plank": {
        0: "45 Degree Plank",
        22: "Kneeling Plank",
        34: "Mountain Climber",
        43: "Plank",
        46: "Plank Knee Twist",
        54: "Plank with Arm Raise",
        66: "Side Plank",
        67: "Weighted Side Plank",
        70: "Side Plank Lift",
        88: "Single Leg Side Plank",
        92: "Straight Arm Plank",
    },
    "push_up": {
        11: "Close Hands Push Up",
        13: "Decline Push Up",
        15: "Diamond Push Up",
        27: "Incline Push Up",
        33: "Kneeling Push Up",
        38: "One Arm Push Up",
        40: "Weighted Push Up",
        69: "Wide Hands Push Up",
        77: "Push Up",
        84: "Pike Push Up",
    },
    "pull_up": {
        3: "Close Grip Chin Up",
        13: "Lat Pulldown",
        24: "Weighted Pull Up",
        26: "Wide Grip Pull Up",
        32: "Kipping Pull Up",
        38: "Pull Up",
        39: "Chin Up",
        42: "Band Assisted Pull Up",
    },
    "squat": {
        0: "Leg Press",
        2: "Back Squats",
        6: "Barbell Back Squat",
        8: "Barbell Front Squat",
        27: "Dumbbell Front Squat",
        29: "Dumbbell Squat",
        37: "Goblet Squat",
        47: "Pistol Squat",
        61: "Squat",
        62: "Weighted Squat",
        69: "Sumo Squat",
        100: "Air Squat",
    },
    "core": {
        0: "Abs Jabs",
        3: "Barbell Rollout",
        6: "Cable Core Press",
        8: "Side Bend",
        18: "Kneeling Ab Wheel",
        46: "Russian Twist",
        49: "Bicycle",
        84: "Toes to Elbows",
        88: "L-Sit",
        89: "Turkish Get Up",
    },
    "lunge": {
        0: "Lunge",
        1: "Walking Lunge",
        2: "Reverse Lunge",
        3: "Lateral Lunge",
        10: "Dumbbell Lunge",
        14: "Forward Lunge",
        20: "Bulgarian Split Squat",
    },
    "crunch": {
        0: "Crunch",
        1: "Weighted Crunch",
        10: "Bicycle Crunch",
        20: "Reverse Crunch",
    },
    "deadlift": {
        0: "Deadlift",
        1: "Barbell Deadlift",
        10: "Romanian Deadlift",
        20: "Sumo Deadlift",
    },
    "bench_press": {
        0: "Bench Press",
        1: "Barbell Bench Press",
        10: "Dumbbell Bench Press",
        20: "Incline Bench Press",
    },
    "row": {
        0: "Row",
        1: "Barbell Bent Over Row",
        10: "Dumbbell Row",
        20: "Seated Cable Row",
    },
    "curl": {
        0: "Curl",
        1: "Barbell Curl",
        10: "Dumbbell Curl",
        20: "Hammer Curl",
    },
    "shoulder_press": {
        0: "Shoulder Press",
        1: "Barbell Shoulder Press",
        10: "Dumbbell Shoulder Press",
    },
    "calf_raise": {
        0: "Calf Raise",
        1: "Standing Calf Raise",
        10: "Seated Calf Raise",
    },
    "leg_curl": {
        0: "Leg Curl",
        1: "Lying Leg Curl",
        10: "Seated Leg Curl",
    },
    "leg_raise": {
        0: "Leg Raise",
        1: "Hanging Leg Raise",
        10: "Lying Leg Raise",
    },
    "triceps_extension": {
        0: "Triceps Extension",
        1: "Skull Crusher",
        10: "Triceps Pushdown",
    },
    "hip_raise": {
        0: "Hip Raise",
        1: "Glute Bridge",
        10: "Single Leg Hip Raise",
    },
    "total_body": {
        0: "Burpee",
        1: "Weighted Burpee",
        10: "Man Maker",
    },
}

# Category fallback display when subtype is missing / unknown.
_CATEGORY_LABELS: dict[str, str] = {
    "hip_stability": "Hip Stability",
    "plank": "Plank",
    "push_up": "Push Up",
    "pull_up": "Pull Up",
    "squat": "Squat",
    "core": "Core",
    "lunge": "Lunge",
    "crunch": "Crunch",
    "deadlift": "Deadlift",
    "bench_press": "Bench Press",
    "row": "Row",
    "curl": "Curl",
    "shoulder_press": "Shoulder Press",
    "calf_raise": "Calf Raise",
    "leg_curl": "Leg Curl",
    "leg_raise": "Leg Raise",
    "triceps_extension": "Triceps Extension",
    "hip_raise": "Hip Raise",
    "total_body": "Total Body",
    "cardio": "Cardio",
    "flye": "Flye",
    "lateral_raise": "Lateral Raise",
    "shrug": "Shrug",
    "sit_up": "Sit Up",
    "olymic_lift": "Olympic Lift",
    "olympic_lift": "Olympic Lift",
    "plyo": "Plyometrics",
    "carry": "Carry",
    "chop": "Chop",
    "hyperextension": "Hyperextension",
    "hip_swing": "Hip Swing",
    "shoulder_stability": "Shoulder Stability",
    "warm_up": "Warm Up",
}

# Primary / secondary muscle regions for the body map.
# Region ids must match MuscleMap.jsx path ids.
_MUSCLES: dict[str, dict[str, list[str]]] = {
    "squat": {"primary": ["quads", "glutes"], "secondary": ["hamstrings", "lower_back", "adductors"]},
    "lunge": {"primary": ["quads", "glutes"], "secondary": ["hamstrings", "adductors"]},
    "deadlift": {"primary": ["hamstrings", "glutes", "lower_back"], "secondary": ["upper_back", "quads"]},
    "hip_raise": {"primary": ["glutes"], "secondary": ["hamstrings", "lower_back"]},
    "hip_stability": {"primary": ["glutes", "adductors"], "secondary": ["abs", "lower_back"]},
    "hip_swing": {"primary": ["glutes", "hamstrings"], "secondary": ["lower_back"]},
    "leg_curl": {"primary": ["hamstrings"], "secondary": ["calves", "glutes"]},
    "leg_raise": {"primary": ["abs"], "secondary": ["hip_flexors"]},
    "calf_raise": {"primary": ["calves"], "secondary": []},
    "plank": {"primary": ["abs"], "secondary": ["shoulders", "glutes", "lower_back"]},
    "core": {"primary": ["abs"], "secondary": ["lower_back", "obliques"]},
    "crunch": {"primary": ["abs"], "secondary": ["obliques"]},
    "sit_up": {"primary": ["abs"], "secondary": ["hip_flexors"]},
    "push_up": {"primary": ["chest", "abs"], "secondary": ["shoulders", "triceps"]},
    "bench_press": {"primary": ["chest"], "secondary": ["shoulders", "triceps"]},
    "flye": {"primary": ["chest"], "secondary": ["shoulders"]},
    "pull_up": {"primary": ["upper_back"], "secondary": ["biceps", "abs", "shoulders"]},
    "row": {"primary": ["upper_back"], "secondary": ["biceps", "lower_back"]},
    "shoulder_press": {"primary": ["shoulders"], "secondary": ["triceps", "abs"]},
    "lateral_raise": {"primary": ["shoulders"], "secondary": []},
    "shrug": {"primary": ["upper_back"], "secondary": ["shoulders"]},
    "curl": {"primary": ["biceps"], "secondary": []},
    "triceps_extension": {"primary": ["triceps"], "secondary": []},
    "total_body": {"primary": ["abs", "quads", "chest"], "secondary": ["shoulders", "glutes"]},
    "cardio": {"primary": ["quads"], "secondary": ["calves", "abs"]},
    "carry": {"primary": ["abs", "upper_back"], "secondary": ["shoulders", "glutes"]},
    "chop": {"primary": ["abs", "obliques"], "secondary": ["shoulders"]},
    "hyperextension": {"primary": ["lower_back"], "secondary": ["glutes", "hamstrings"]},
    "olympic_lift": {"primary": ["quads", "glutes", "upper_back"], "secondary": ["shoulders", "hamstrings"]},
    "plyo": {"primary": ["quads", "glutes"], "secondary": ["calves", "abs"]},
    "shoulder_stability": {"primary": ["shoulders"], "secondary": ["upper_back"]},
    "warm_up": {"primary": [], "secondary": []},
}

_REGION_LABELS: dict[str, str] = {
    "chest": "Chest",
    "abs": "Abs",
    "obliques": "Obliques",
    "shoulders": "Shoulders",
    "biceps": "Biceps",
    "triceps": "Triceps",
    "upper_back": "Upper Back",
    "lower_back": "Lower Back",
    "glutes": "Glutes",
    "quads": "Quads",
    "hamstrings": "Hamstrings",
    "adductors": "Inner Thigh",
    "hip_flexors": "Hip Flexors",
    "calves": "Calves",
}


def resolve_exercise_name(category: Any, subtype: Any = None) -> str:
    """Return a human exercise name from FIT category + subtype."""
    if hasattr(category, "name") and not isinstance(category, (str, bytes)):
        category = category.name
    cat = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not cat or cat in {"none", "invalid", "unknown"}:
        return "Exercise"

    sub = None
    if subtype is not None:
        try:
            sub = int(subtype)
            if sub in (0xFFFF, 65535):
                sub = None
        except (TypeError, ValueError):
            sub = None

    if sub is not None and cat in _SUBTYPES and sub in _SUBTYPES[cat]:
        return _SUBTYPES[cat][sub]

    if cat in _CATEGORY_LABELS:
        return _CATEGORY_LABELS[cat]
    return _title(cat)


def muscles_for_category(category: Any) -> dict[str, list[str]]:
    if hasattr(category, "name") and not isinstance(category, (str, bytes)):
        category = category.name
    cat = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    entry = _MUSCLES.get(cat) or {"primary": [], "secondary": []}
    return {
        "primary": list(entry.get("primary") or []),
        "secondary": list(entry.get("secondary") or []),
    }


def build_muscle_map(exercises: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate set counts into primary/secondary muscle regions."""
    primary_sets: dict[str, int] = {}
    secondary_sets: dict[str, int] = {}

    for exercise in exercises:
        set_count = len(exercise.get("sets") or [])
        if set_count <= 0:
            continue
        muscles = exercise.get("muscles") or {}
        # Fall back to category-based mapping when muscles missing.
        if not muscles.get("primary") and not muscles.get("secondary"):
            muscles = muscles_for_category(exercise.get("category"))
        for region in muscles.get("primary") or []:
            primary_sets[region] = primary_sets.get(region, 0) + set_count
        for region in muscles.get("secondary") or []:
            # Don't double-count if already primary from another exercise.
            if region in primary_sets:
                continue
            secondary_sets[region] = secondary_sets.get(region, 0) + set_count

    # If a region ends up in both (from different exercises), keep primary.
    for region in list(secondary_sets):
        if region in primary_sets:
            secondary_sets.pop(region, None)

    def _rows(bucket: dict[str, int], role: str) -> list[dict[str, Any]]:
        rows = [
            {
                "id": region,
                "label": _REGION_LABELS.get(region, _title(region)),
                "sets": count,
                "role": role,
            }
            for region, count in bucket.items()
            if count > 0
        ]
        rows.sort(key=lambda r: (-int(r["sets"]), str(r["label"])))
        return rows

    primary = _rows(primary_sets, "primary")
    secondary = _rows(secondary_sets, "secondary")
    return {
        "primary": primary,
        "secondary": secondary,
        "regions": {row["id"]: row for row in primary + secondary},
    }
