"""Science Workout Library (SWL) — Phase 1.

Curated, evidence-tagged session templates with zone-resolved prescriptions
(FTP, LTHR, threshold pace, CSS). Used by session_blueprints before generic
RPE fallbacks.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.session_blueprints import sport_family

LIBRARY_VERSION = "2.0.0"
LIBRARY_DIR = Path(__file__).resolve().parents[2] / "data" / "workout_library"

_SPORT_ALIASES = {
    "run": "running",
    "running": "running",
    "trail": "trail_running",
    "trail running": "trail_running",
    "trail_running": "trail_running",
    "ride": "cycling",
    "bike": "cycling",
    "cycling": "cycling",
    "swim": "swimming",
    "swimming": "swimming",
    "strength": "strength",
    "strength training": "strength",
    "yoga": "mobility",
    "mobility": "mobility",
    "yoga / mobility": "mobility",
    "triathlon": "triathlon",
    "tri": "triathlon",
    "row": "rowing",
    "rowing": "rowing",
    "walk": "walking",
    "walking / hiking": "walking",
    "cross_training": "cross_training",
    "cross-training": "cross_training",
    "team sport": "cross_training",
}


def _normalize_sport(sport: str | None, family: str | None = None) -> str:
    blob = (sport or "").strip().lower()
    if blob in _SPORT_ALIASES:
        return _SPORT_ALIASES[blob]
    family_map = {
        "run": "running",
        "ride": "cycling",
        "swim": "swimming",
        "strength": "strength",
        "yoga": "mobility",
        "row": "rowing",
        "walk": "walking",
    }
    if family and family in family_map:
        return family_map[family]
    return blob or "running"


def _resolve_library_sport(workout: dict[str, Any], family: str) -> str:
    blob = f"{workout.get('sport') or ''} {workout.get('title') or ''}".lower()
    if "trail" in blob:
        return "trail_running"
    if "triathlon" in blob or "tri " in blob or blob.strip() == "tri":
        return "triathlon"
    return _normalize_sport(workout.get("sport"), family)


def parse_swim_pace_seconds(value: str | float | int | None) -> float | None:
    """Parse swim pace to seconds per 100m (e.g. '1:35/100m')."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value).strip().lower()
    text = text.replace("/100m", "").replace("min/100m", "").strip()
    return parse_pace_seconds(text)


def parse_pace_seconds(value: str | float | int | None) -> float | None:
    """Parse pace to seconds per km (e.g. '5:30/km', \"5'30\", 330)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value).strip().lower()
    text = text.replace("/km", "").replace("min/km", "").replace("'", ":").strip()
    if re.match(r"^\d+(\.\d+)?$", text):
        return float(text)
    match = re.match(r"^(\d+):(\d{1,2})(?:\.(\d))?$", text)
    if match:
        minutes, seconds, tenths = match.groups()
        sec = int(minutes) * 60 + int(seconds)
        if tenths:
            sec += int(tenths) / 10
        return float(sec)
    return None


def format_pace(seconds_per_km: float | None) -> str:
    if not seconds_per_km or seconds_per_km <= 0:
        return ""
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/km"


def format_swim_pace(seconds_per_100m: float | None) -> str:
    if not seconds_per_100m or seconds_per_100m <= 0:
        return ""
    minutes = int(seconds_per_100m // 60)
    seconds = int(round(seconds_per_100m % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/100m"


def format_watts(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return ""
    return f"{int(round(low))}–{int(round(high))} W"


def format_hr(low: float | None, high: float | None, *, lthr: float | None) -> str:
    if lthr and low is not None and high is not None:
        return f"{int(round(lthr * low))}–{int(round(lthr * high))} bpm"
    return "RPE-guided (confirm LTHR for HR targets)"


def _load_json_templates(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return list(payload.get("templates") or [])
    return []


def _normalize_loaded_template(raw: dict[str, Any]) -> dict[str, Any]:
    from app.services.workout_library_schema import normalize_template

    return normalize_template(raw)


@lru_cache(maxsize=1)
def load_templates() -> tuple[tuple[dict[str, Any], ...], str]:
    templates: list[dict[str, Any]] = []
    if not LIBRARY_DIR.is_dir():
        return tuple(), LIBRARY_VERSION

    paths = sorted(LIBRARY_DIR.glob("*.json"))
    packs_dir = LIBRARY_DIR / "packs"
    if packs_dir.is_dir():
        paths.extend(sorted(packs_dir.glob("*.json")))

    for path in paths:
        if path.name == "manifest.json":
            continue
        for raw in _load_json_templates(path):
            templates.append(_normalize_loaded_template(raw))

    return tuple(templates), LIBRARY_VERSION


def clear_library_cache() -> None:
    load_templates.cache_clear()


def physiology_from_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    profile = context.get("profile") or {}
    physiology = dict(context.get("physiology") or {})
    coros_fitness = (context.get("coros") or {}).get("fitness") or {}
    anchor_keys = (
        "ftp_watts",
        "lthr_bpm",
        "max_hr_bpm",
        "bike_lthr_bpm",
        "resting_hr_bpm",
        "threshold_pace_sec_per_km",
        "lt1_pace_sec_per_km",
        "marathon_pace_sec_per_km",
        "css_sec_per_100m",
        "vo2max",
        "zone_run_hr_method",
        "zone_bike_power_method",
        "zone_run_pace_method",
    )
    for key in anchor_keys:
        if physiology.get(key) is None and profile.get(key) is not None:
            physiology[key] = profile.get(key)
    if physiology.get("threshold_pace_sec_per_km") is None:
        parsed = parse_pace_seconds(
            physiology.get("threshold_pace") or coros_fitness.get("threshold_pace")
        )
        if parsed:
            physiology["threshold_pace_sec_per_km"] = parsed
    if physiology.get("vo2max") is None and coros_fitness.get("vo2max"):
        physiology["vo2max"] = coros_fitness.get("vo2max")
    from app.services.zone_engine import attach_zone_tables

    return attach_zone_tables(physiology)


def physiology_from_profile(profile: Any) -> dict[str, Any]:
    if profile is None:
        return {}
    from app.services.zone_engine import attach_zone_tables, profile_anchor_fields

    anchors = profile_anchor_fields(profile)
    base = {
        "ftp_watts": anchors.get("ftp_watts"),
        "lthr_bpm": anchors.get("lthr_bpm"),
        "max_hr_bpm": anchors.get("max_hr_bpm"),
        "bike_lthr_bpm": anchors.get("bike_lthr_bpm"),
        "resting_hr_bpm": anchors.get("resting_hr_bpm"),
        "threshold_pace_sec_per_km": anchors.get("threshold_pace_sec_per_km"),
        "lt1_pace_sec_per_km": anchors.get("lt1_pace_sec_per_km"),
        "marathon_pace_sec_per_km": anchors.get("marathon_pace_sec_per_km"),
        "css_sec_per_100m": anchors.get("css_sec_per_100m"),
        "vo2max": anchors.get("vo2max"),
        "zone_run_hr_method": anchors.get("zone_run_hr_method"),
        "zone_bike_power_method": anchors.get("zone_bike_power_method"),
        "zone_run_pace_method": anchors.get("zone_run_pace_method"),
    }
    return attach_zone_tables(base)


def anchors_from_physiology(physiology: dict[str, Any] | None) -> dict[str, Any]:
    from app.services.zone_engine import build_anchors

    physiology = physiology or {}
    if physiology.get("anchors"):
        return dict(physiology["anchors"])
    return build_anchors(physiology)


def resolve_target_band(
    targets: dict[str, Any] | None,
    anchors: dict[str, Any],
) -> dict[str, str]:
    """Turn template target bands into human-readable prescription strings."""
    targets = targets or {}
    parts: dict[str, str] = {}
    ftp = anchors.get("ftp_watts")
    lthr = anchors.get("lthr_bpm")
    threshold_pace = anchors.get("threshold_pace_sec_per_km")
    css = anchors.get("css_sec_per_100m")

    if "pct_ftp" in targets and ftp:
        band = targets["pct_ftp"]
        low = ftp * float(band.get("low", band.get("mid", 0.75)))
        high = ftp * float(band.get("high", band.get("mid", 0.75)))
        parts["power"] = format_watts(low, high)
        parts["pct_ftp"] = f"{int(float(band.get('low', 0)) * 100)}–{int(float(band.get('high', 0)) * 100)}% FTP"

    if "hr_pct_lthr" in targets and lthr:
        band = targets["hr_pct_lthr"]
        low = float(band.get("low", 0.7))
        high = float(band.get("high", 0.8))
        parts["hr"] = format_hr(low, high, lthr=lthr)
        parts["lthr_pct"] = f"{int(low * 100)}–{int(high * 100)}% LTHR"

    if "pace_pct_threshold" in targets and threshold_pace:
        band = targets["pace_pct_threshold"]
        low_p = threshold_pace * float(band.get("low", 1.0))
        high_p = threshold_pace * float(band.get("high", 1.0))
        parts["pace"] = f"{format_pace(min(low_p, high_p))}–{format_pace(max(low_p, high_p))}"

    if "css_pct" in targets and css:
        band = targets["css_pct"]
        low_s = css * float(band.get("low", 1.0))
        high_s = css * float(band.get("high", 1.0))
        parts["swim_pace"] = f"{format_swim_pace(min(low_s, high_s))}–{format_swim_pace(max(low_s, high_s))}"

    if "rpe" in targets:
        band = targets["rpe"]
        parts["rpe"] = f"RPE {band.get('low', 6)}–{band.get('high', 7)}"

    return parts


def _infer_intent(workout: dict[str, Any], family: str) -> str:
    session_type = str(workout.get("session_type") or "easy").lower()
    blob = f"{workout.get('title') or ''} {workout.get('sport') or ''} {session_type}".lower()
    if any(token in blob for token in ("vo2", "vo₂", "aerobic power", "5 x 3", "4 x 4")):
        return "vo2"
    if any(token in blob for token in ("sweet spot", "sweet-spot", "sst")):
        return "sweet_spot"
    if any(token in blob for token in ("over-under", "over under", "over/under")):
        return "over_under"
    if any(token in blob for token in ("stride", "strides", "acceleration")):
        return "strides"
    if any(token in blob for token in ("fartlek",)):
        return "fartlek"
    if any(token in blob for token in ("race pace", "marathon pace", "half marathon")):
        return "race_pace"
    if any(token in blob for token in ("progression", "fast finish")):
        return "progression"
    if family == "run" and session_type == "hills" or "uphill" in blob or "vert" in blob:
        return "hills"
    if session_type == "tempo":
        return "tempo"
    if session_type == "threshold":
        return "threshold"
    if session_type in {"intervals", "speed"}:
        return "vo2" if family in {"run", "ride", "swim"} else session_type
    if session_type == "long":
        return "long"
    if session_type == "strength":
        if any(token in blob for token in ("power", "plyo", "explosive")):
            return "strength_power"
        if any(token in blob for token in ("hypertrophy", "8-12", "muscle")):
            return "strength_hypertrophy"
        if "prehab" in blob or "injury" in blob:
            return "strength_prehab"
        return "strength_general"
    if session_type == "mobility":
        if "pre-run" in blob or "pre run" in blob:
            return "mobility_pre_run"
        if "post-ride" in blob or "cyclist" in blob:
            return "mobility_post_ride"
        if "swim" in blob and "shoulder" in blob:
            return "mobility_swim_shoulder"
        return "mobility_general"
    if session_type == "cross-training":
        return "cross_training"
    if session_type == "race":
        return "race"
    return session_type if session_type else "easy"


def _template_matches(
    template: dict[str, Any],
    *,
    sport: str,
    session_type: str,
    intent: str,
    title_blob: str,
    spine_lock: bool,
    phase_type: str | None = None,
) -> bool:
    template_sports = {str(s).lower() for s in (template.get("sports") or [template.get("sport")]) if s}
    if template_sports and sport not in template_sports:
        return False

    phase_fit = template.get("phase_fit")
    if phase_fit and phase_type:
        allowed = {str(p).lower() for p in phase_fit}
        if phase_type.lower() not in allowed:
            return False

    allowed_types = {str(t).lower() for t in template.get("session_types") or []}
    template_intent = str(template.get("intent") or "").lower()
    if allowed_types and session_type not in allowed_types and template_intent != intent:
        return False

    keywords = [str(k).lower() for k in template.get("match_keywords") or []]
    if keywords and not all(keyword in title_blob for keyword in keywords):
        return False

    if spine_lock and template.get("contraindications"):
        blocked = {str(c).lower() for c in template["contraindications"]}
        if "spine_lock" in blocked or "loaded_hinge" in blocked:
            return False

    if not spine_lock and template.get("requires_spine_lock"):
        return False

    return True


def get_template_by_id(
    template_id: str | None,
    *,
    version: int | None = None,
) -> dict[str, Any] | None:
    if not template_id:
        return None
    templates, _ = load_templates()
    matches = [template for template in templates if template.get("id") == template_id]
    if not matches:
        return None
    if version is not None:
        for template in matches:
            if int(template.get("version") or 1) == version:
                return template
        return None
    return max(matches, key=lambda item: int(item.get("version") or 1))


def pick_template(
    workout: dict[str, Any],
    *,
    safety: dict[str, Any] | None = None,
    preferred_intent: str | None = None,
    phase_type: str | None = None,
) -> dict[str, Any] | None:
    templates, _ = load_templates()
    if not templates:
        return None

    family = sport_family(workout.get("sport"), workout.get("session_type"), workout.get("title"))
    sport = _resolve_library_sport(workout, family)
    session_type = str(workout.get("session_type") or "easy").lower()
    intent = (preferred_intent or _infer_intent(workout, family)).lower()
    title_blob = f"{workout.get('title') or ''} {workout.get('description') or ''}".lower()
    spine_lock = bool((safety or {}).get("spine_lock"))

    candidates: list[tuple[int, dict[str, Any]]] = []
    for template in templates:
        if not _template_matches(
            template,
            sport=sport,
            session_type=session_type,
            intent=intent,
            title_blob=title_blob,
            spine_lock=spine_lock,
            phase_type=phase_type,
        ):
            continue
        priority = int(template.get("priority") or 0)
        if str(template.get("intent") or "").lower() == intent:
            priority += 50
        if template.get("intent") == session_type:
            priority += 25
        version = int(template.get("version") or 1)
        candidates.append((priority, version, template))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _duration(value: Any, default: int = 45) -> int:
    try:
        minutes = int(round(float(value)))
    except (TypeError, ValueError):
        minutes = default
    return max(20, min(minutes, 420))


def _split_duration(total: int, warmup_min: int, cooldown_min: int) -> tuple[int, int, int]:
    warmup = warmup_min if total >= warmup_min + cooldown_min + 8 else max(5, total // 5)
    cooldown = cooldown_min if total >= warmup + cooldown_min + 8 else max(5, total // 5)
    main = max(8, total - warmup - cooldown)
    return warmup, main, cooldown


def _render_repeat_main(
    main_spec: dict[str, Any],
    main_min: int,
    anchors: dict[str, Any],
) -> tuple[str, str]:
    reps = int(main_spec.get("reps") or 1)
    on_spec = main_spec.get("on") or {}
    off_spec = main_spec.get("off") or {}
    on_min = float(on_spec.get("duration_min") or 5)
    off_min = float(off_spec.get("duration_min") or 2) if off_spec else 0.0

    on_targets = resolve_target_band(on_spec.get("targets"), anchors)
    off_targets = resolve_target_band(off_spec.get("targets"), anchors) if off_spec else {}

    on_label = on_spec.get("label") or "work"
    off_label = off_spec.get("label") or "recovery"

    on_parts = [on_targets.get("power"), on_targets.get("hr"), on_targets.get("pace"), on_targets.get("swim_pace")]
    on_text = " · ".join(part for part in on_parts if part) or on_targets.get("rpe", "controlled hard effort")
    off_parts = [off_targets.get("power"), off_targets.get("hr"), off_targets.get("pace"), off_targets.get("swim_pace")]
    off_text = " · ".join(part for part in off_parts if part) or off_targets.get("rpe", "easy")

    detail = (
        f"{reps} × {on_min:g} min {on_label} ({on_text})"
        + (f", {off_min:g} min {off_label} ({off_text}) between" if off_min else "")
    )
    intro = str(main_spec.get("detail_intro") or "").strip()
    if intro:
        detail = f"{detail}. {intro}"

    intensity = str(main_spec.get("intensity") or on_spec.get("intensity") or "Hard / controlled")
    return intensity, detail


def _render_steady_main(
    main_spec: dict[str, Any],
    main_min: int,
    anchors: dict[str, Any],
) -> tuple[str, str]:
    targets = resolve_target_band(main_spec.get("targets"), anchors)
    parts = [targets.get("power"), targets.get("hr"), targets.get("pace"), targets.get("swim_pace")]
    target_text = " · ".join(part for part in parts if part) or targets.get("rpe", "conversational")
    detail = str(main_spec.get("detail") or main_spec.get("detail_template") or "")
    detail = detail.replace("{main_min}", str(main_min)).replace("{targets}", target_text)
    if "{targets}" not in str(main_spec.get("detail_template") or "") and target_text not in detail:
        detail = f"{detail} Target: {target_text}." if detail else f"Steady {main_min} min. Target: {target_text}."
    intensity = str(main_spec.get("intensity") or "Moderate")
    return intensity, detail.strip()


def render_structure(
    template: dict[str, Any],
    workout: dict[str, Any],
    anchors: dict[str, Any],
) -> list[dict[str, Any]]:
    total = _duration(workout.get("duration_min"), template.get("duration_min", {}).get("default", 45))
    warmup_min = int(template.get("warmup_min") or 10)
    cooldown_min = int(template.get("cooldown_min") or 10)
    warmup_min, main_min, cooldown_min = _split_duration(total, warmup_min, cooldown_min)

    warmup_spec = template.get("warmup") or {}
    cooldown_spec = template.get("cooldown") or {}
    main_spec = template.get("main") or {}

    if main_spec.get("type") == "repeat":
        main_intensity, main_detail = _render_repeat_main(main_spec, main_min, anchors)
    else:
        main_intensity, main_detail = _render_steady_main(main_spec, main_min, anchors)

    return [
        {
            "segment": "Warm-up",
            "duration_min": warmup_min,
            "intensity": str(warmup_spec.get("intensity") or "Easy"),
            "detail": str(warmup_spec.get("detail") or "Easy aerobic start. No hard efforts yet."),
        },
        {
            "segment": "Main set",
            "duration_min": main_min,
            "intensity": main_intensity,
            "detail": main_detail,
        },
        {
            "segment": "Cool-down",
            "duration_min": cooldown_min,
            "intensity": str(cooldown_spec.get("intensity") or "Easy"),
            "detail": str(cooldown_spec.get("detail") or "Easy spin or jog. Light stretching."),
        },
    ]


def _finalize_library_workout(
    item: dict[str, Any],
    template: dict[str, Any],
    physiology: dict[str, Any] | None,
) -> dict[str, Any]:
    anchors = anchors_from_physiology(physiology)
    item = dict(item)
    item["structure"] = render_structure(template, item, anchors)
    item["library_template_id"] = template.get("id")
    item["library_version"] = LIBRARY_VERSION

    if template.get("title") and not (item.get("title") or "").strip():
        item["title"] = template["title"]

    if not (item.get("description") or "").strip():
        evidence = ", ".join(template.get("evidence_tags") or []) or "evidence-based endurance practice"
        item["description"] = (
            f"{template.get('summary') or item.get('title') or 'Structured session'}. "
            f"Grounded in: {evidence}."
        )

    intensity = (template.get("main") or {}).get("intensity")
    if intensity and not (item.get("intensity") or "").strip():
        item["intensity"] = intensity

    return item


def apply_template_by_id(
    workout: dict[str, Any],
    template_id: str,
    physiology: dict[str, Any] | None = None,
    safety: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Render a workout from an explicit library template id."""
    template = get_template_by_id(template_id)
    if not template:
        return None
    spine_lock = bool((safety or {}).get("spine_lock"))
    contraindications = {str(c).lower() for c in (template.get("contraindications") or [])}
    if spine_lock and ("spine_lock" in contraindications or "loaded_hinge" in contraindications):
        return None
    if not spine_lock and template.get("requires_spine_lock"):
        return None
    return _finalize_library_workout(workout, template, physiology)


def apply_library_template(
    workout: dict[str, Any],
    physiology: dict[str, Any] | None = None,
    safety: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """If a library template matches, return enriched workout copy."""
    item = dict(workout or {})
    template_id = item.get("library_template_id")
    if template_id:
        applied = apply_template_by_id(item, str(template_id), physiology, safety)
        if applied:
            return applied

    template = pick_template(item, safety=safety)
    if not template:
        return None

    return _finalize_library_workout(item, template, physiology)


def list_templates(
    *,
    sport: str | None = None,
    intent: str | None = None,
) -> list[dict[str, Any]]:
    templates, _ = load_templates()
    results = []
    for template in templates:
        if sport:
            sports = {str(s).lower() for s in (template.get("sports") or [template.get("sport")]) if s}
            if sports and _normalize_sport(sport) not in sports:
                continue
        if intent and str(template.get("intent") or "").lower() != intent.lower():
            continue
        results.append(template)
    return results


def validate_library_catalog() -> dict[str, Any]:
    from app.services.workout_library_schema import validate_catalog

    templates, version = load_templates()
    report = validate_catalog(list(templates))
    report["library_version"] = version
    return report


def library_stats() -> dict[str, Any]:
    templates, version = load_templates()
    by_sport: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    versions: dict[str, int] = {}
    for template in templates:
        for sport in template.get("sports") or [template.get("sport")]:
            if sport:
                by_sport[str(sport)] = by_sport.get(str(sport), 0) + 1
        intent = str(template.get("intent") or "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1
        tid = str(template.get("id") or "")
        ver = int(template.get("version") or 1)
        versions[tid] = max(versions.get(tid, 0), ver)
    return {
        "version": version,
        "total": len(templates),
        "unique_ids": len(versions),
        "by_sport": by_sport,
        "by_intent": by_intent,
        "versioned_ids": sum(1 for ver in versions.values() if ver > 1),
    }
