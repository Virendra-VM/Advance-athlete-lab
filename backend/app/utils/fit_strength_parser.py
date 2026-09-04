"""Parse exercise/set breakdown from COROS strength-workout FIT files.

COROS strength FIT layout (confirmed against real files)
-------------------------------------------------------
Messages present:
  - ``set`` (global 225) — one per work set AND rest interval
  - ``lap`` — mirrors each set as a lap
  - ``record`` — HR/time samples

Each active set carries:
  set_type          : 'active' | 'rest'
  category          : exercise family string, e.g. 'push_up', 'hip_stability'
  category_subtype  : int subtype within the family (optional)
  repetitions       : int | None
  duration          : float seconds (already scaled by fitdecode)
  weight            : float kg | None

Grouping strategy
-----------------
Consecutive active sets that share the same (category, category_subtype)
become one exercise. Rest sets immediately after an active set become
that set's ``rest_s``.
"""

from __future__ import annotations

import io
import math
import warnings
from typing import Any

from app.utils.exercise_catalog import (
    build_muscle_map,
    muscles_for_category,
    resolve_exercise_name,
)


def _safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, int) and value in (0xFFFF, 0xFFFFFFFF, 65535, 4294967295):
        return None
    return value


def _set_type_value(raw: Any) -> str:
    if raw is None:
        return "active"
    if hasattr(raw, "name") and not isinstance(raw, (str, bytes)):
        raw = raw.name
    text = str(raw).strip().lower()
    if "rest" in text:
        return "rest"
    return "active"


def _category_key(raw: Any) -> str:
    if hasattr(raw, "name") and not isinstance(raw, (str, bytes)):
        raw = raw.name
    return str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")


def extract_exercises_from_fit_bytes(fit_bytes: bytes) -> list[dict[str, Any]]:
    """Return exercise dicts from a COROS strength FIT file.

    Each exercise:
        {
          "index", "name", "category", "subtype",
          "muscles": {"primary": [...], "secondary": [...]},
          "sets": [{ "index", "reps", "weight_kg", "duration_s", "rest_s" }]
        }
    """
    if not fit_bytes:
        return []

    try:
        import fitdecode
    except ImportError:
        return []

    raw_sets: list[dict[str, Any]] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with fitdecode.FitReader(io.BytesIO(fit_bytes)) as fit:
                for frame in fit:
                    if not isinstance(frame, fitdecode.FitDataMessage):
                        continue
                    if frame.name != "set":
                        continue
                    fields = {f.name: f.value for f in frame.fields}
                    raw_sets.append(fields)
    except Exception:
        return []

    if not raw_sets:
        return []

    exercises: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[Any, Any] | None = None
    last_active: dict[str, Any] | None = None

    for raw in raw_sets:
        set_type = _set_type_value(raw.get("set_type"))

        if set_type == "rest":
            rest_s = _safe(raw.get("duration"))
            if last_active is not None and rest_s is not None:
                try:
                    last_active["rest_s"] = int(round(float(rest_s)))
                except (TypeError, ValueError):
                    pass
            continue

        category = raw.get("category")
        subtype = _safe(raw.get("category_subtype"))
        cat_key = _category_key(category)
        key = (cat_key, subtype)

        if current is None or key != current_key:
            muscles = muscles_for_category(cat_key)
            current = {
                "index": len(exercises) + 1,
                "name": resolve_exercise_name(category, subtype),
                "category": cat_key or None,
                "subtype": int(subtype) if subtype is not None else None,
                "muscles": muscles,
                "sets": [],
            }
            exercises.append(current)
            current_key = key

        reps = _safe(raw.get("repetitions"))
        duration = _safe(raw.get("duration"))
        weight = _safe(raw.get("weight"))

        duration_s = None
        if duration is not None:
            try:
                duration_s = int(round(float(duration)))
                if duration_s <= 0:
                    duration_s = None
            except (TypeError, ValueError):
                duration_s = None

        weight_kg = None
        if weight is not None:
            try:
                w = float(weight)
                if w > 0:
                    weight_kg = round(w / 16.0, 2) if w > 500 else round(w, 2)
            except (TypeError, ValueError):
                weight_kg = None

        set_row = {
            "index": len(current["sets"]) + 1,
            "reps": int(reps) if reps is not None else None,
            "weight_kg": weight_kg,
            "duration_s": duration_s,
            "rest_s": None,
        }
        current["sets"].append(set_row)
        last_active = set_row

    return [ex for ex in exercises if ex.get("sets")]


def extract_workout_from_fit_bytes(fit_bytes: bytes) -> dict[str, Any]:
    """Return exercises + derived muscle map from a strength FIT file."""
    exercises = extract_exercises_from_fit_bytes(fit_bytes)
    return {
        "exercises": exercises,
        "muscle_map": build_muscle_map(exercises) if exercises else None,
    }
