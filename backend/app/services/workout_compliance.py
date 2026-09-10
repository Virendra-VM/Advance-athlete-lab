"""Phase 4 SWL — planned vs executed compliance and library prescription bridge."""

from __future__ import annotations

from typing import Any

from app.services.workout_library import (
    anchors_from_physiology,
    get_template_by_id,
    resolve_target_band,
)


def resolve_numeric_targets(
    targets: dict[str, Any] | None,
    anchors: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Turn template target bands into numeric low/high values for scoring."""
    targets = targets or {}
    out: dict[str, dict[str, float]] = {}
    ftp = anchors.get("ftp_watts")
    lthr = anchors.get("lthr_bpm")
    threshold_pace = anchors.get("threshold_pace_sec_per_km")
    css = anchors.get("css_sec_per_100m")

    if "pct_ftp" in targets and ftp:
        band = targets["pct_ftp"]
        out["power_w"] = {
            "low": float(ftp) * float(band.get("low", band.get("mid", 0.75))),
            "high": float(ftp) * float(band.get("high", band.get("mid", 0.75))),
        }
    if "hr_pct_lthr" in targets and lthr:
        band = targets["hr_pct_lthr"]
        out["hr_bpm"] = {
            "low": float(lthr) * float(band.get("low", 0.7)),
            "high": float(lthr) * float(band.get("high", 0.8)),
        }
    if "pace_pct_threshold" in targets and threshold_pace:
        band = targets["pace_pct_threshold"]
        low_p = float(threshold_pace) * float(band.get("low", 1.0))
        high_p = float(threshold_pace) * float(band.get("high", 1.0))
        out["pace_sec_per_km"] = {"low": min(low_p, high_p), "high": max(low_p, high_p)}
    if "css_pct" in targets and css:
        band = targets["css_pct"]
        low_s = float(css) * float(band.get("low", 1.0))
        high_s = float(css) * float(band.get("high", 1.0))
        out["css_sec_per_100m"] = {"low": min(low_s, high_s), "high": max(low_s, high_s)}
    if "rpe" in targets:
        band = targets["rpe"]
        out["rpe"] = {
            "low": float(band.get("low", 6)),
            "high": float(band.get("high", 7)),
        }
    return out


def build_template_prescription(
    template: dict[str, Any],
    workout: dict[str, Any] | None,
    physiology: dict[str, Any] | None,
) -> dict[str, Any]:
    """Structured prescription from a library template for compliance / autopsy."""
    anchors = anchors_from_physiology(physiology)
    main = template.get("main") or {}
    labels = resolve_target_band(main.get("targets"), anchors)
    steps: list[dict[str, Any]] = []

    warmup_min = int(template.get("warmup_min") or 10)
    cooldown_min = int(template.get("cooldown_min") or 10)
    steps.append(
        {
            "index": 1,
            "role": "warmup",
            "duration_min": warmup_min,
            "labels": resolve_target_band((template.get("warmup") or {}).get("targets"), anchors),
        }
    )

    if main.get("type") == "repeat":
        reps = int(main.get("reps") or 1)
        on_spec = main.get("on") or {}
        off_spec = main.get("off") or {}
        on_targets = resolve_numeric_targets(on_spec.get("targets"), anchors)
        off_targets = resolve_numeric_targets(off_spec.get("targets"), anchors) if off_spec else {}
        on_labels = resolve_target_band(on_spec.get("targets"), anchors)
        off_labels = resolve_target_band(off_spec.get("targets"), anchors) if off_spec else {}
        for block in range(1, reps + 1):
            steps.append(
                {
                    "index": len(steps) + 1,
                    "role": "work",
                    "block": block,
                    "duration_min": float(on_spec.get("duration_min") or 5),
                    "targets": on_targets,
                    "labels": on_labels,
                    "label": on_spec.get("label") or "work",
                }
            )
            if off_spec:
                steps.append(
                    {
                        "index": len(steps) + 1,
                        "role": "recovery",
                        "block": block,
                        "duration_min": float(off_spec.get("duration_min") or 2),
                        "targets": off_targets,
                        "labels": off_labels,
                        "label": off_spec.get("label") or "recovery",
                    }
                )
    else:
        steps.append(
            {
                "index": 2,
                "role": "work",
                "duration_min": float((workout or {}).get("duration_min") or 45) - warmup_min - cooldown_min,
                "targets": resolve_numeric_targets(main.get("targets"), anchors),
                "labels": labels,
            }
        )

    steps.append(
        {
            "index": len(steps) + 1,
            "role": "cooldown",
            "duration_min": cooldown_min,
            "labels": resolve_target_band((template.get("cooldown") or {}).get("targets"), anchors),
        }
    )

    return {
        "source": "library_template",
        "template_id": template.get("id"),
        "template_version": template.get("version") or 1,
        "intent": template.get("intent"),
        "title": template.get("title"),
        "evidence_tags": template.get("evidence_tags") or [],
        "step_count": len(steps),
        "steps": steps,
        "target_labels": labels,
        "main_targets": resolve_numeric_targets(main.get("targets"), anchors),
    }


def _in_band(value: float | None, band: dict[str, float] | None, *, tolerance_pct: float = 0.06) -> bool | None:
    if value is None or not band:
        return None
    low = float(band["low"]) * (1 - tolerance_pct)
    high = float(band["high"]) * (1 + tolerance_pct)
    return low <= float(value) <= high


def _score_duration(planned_min: float | None, executed_min: float | None) -> tuple[float, dict[str, Any]]:
    if not planned_min or not executed_min:
        return 70.0, {"status": "unknown", "planned_min": planned_min, "executed_min": executed_min}
    ratio = float(executed_min) / float(planned_min)
    delta_pct = abs(ratio - 1.0) * 100
    if delta_pct <= 10:
        score = 100.0
    elif delta_pct <= 20:
        score = 85.0
    elif delta_pct <= 35:
        score = 65.0
    else:
        score = max(20.0, 100.0 - delta_pct)
    return score, {
        "status": "scored",
        "planned_min": round(planned_min, 1),
        "executed_min": round(executed_min, 1),
        "delta_pct": round(delta_pct, 1),
    }


def _score_intensity(
    prescription: dict[str, Any],
    telemetry: dict[str, Any],
    anchors: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    main_targets = prescription.get("main_targets") or {}
    power_band = main_targets.get("power_w")
    hr_band = main_targets.get("hr_bpm")

    np_w = (telemetry.get("power") or {}).get("np_w")
    avg_hr = (telemetry.get("heart_rate") or {}).get("avg_bpm")
    pct_ftp = (telemetry.get("power") or {}).get("pct_ftp_np")
    pct_lthr = (telemetry.get("heart_rate") or {}).get("pct_lthr_avg")

    hits: list[bool] = []
    detail: dict[str, Any] = {}

    if power_band and np_w:
        hit = _in_band(float(np_w), power_band)
        if hit is not None:
            hits.append(hit)
        detail["np_w"] = np_w
        detail["target_power_w"] = power_band
    elif hr_band and avg_hr:
        hit = _in_band(float(avg_hr), hr_band)
        if hit is not None:
            hits.append(hit)
        detail["avg_hr"] = avg_hr
        detail["target_hr_bpm"] = hr_band

    if pct_ftp and power_band and anchors.get("ftp_watts"):
        ftp = float(anchors["ftp_watts"])
        target_mid = (power_band["low"] + power_band["high"]) / 2
        detail["pct_ftp_np"] = pct_ftp
        detail["target_pct_ftp"] = round(100 * target_mid / ftp, 1)

    if pct_lthr and hr_band and anchors.get("lthr_bpm"):
        detail["pct_lthr_avg"] = pct_lthr
        detail["target_pct_lthr"] = round(
            100 * ((hr_band["low"] + hr_band["high"]) / 2) / float(anchors["lthr_bpm"]),
            1,
        )

    if not hits:
        return 75.0, {"status": "unknown", **detail}

    hit_rate = sum(1 for hit in hits if hit) / len(hits)
    score = 55.0 + 45.0 * hit_rate
    detail["status"] = "scored"
    detail["hit"] = hit_rate >= 0.5
    return score, detail


def _score_interval_execution(
    prescription: dict[str, Any],
    telemetry: dict[str, Any],
) -> tuple[float | None, dict[str, Any]]:
    work_steps = [step for step in prescription.get("steps") or [] if step.get("role") == "work"]
    work_laps = telemetry.get("work_laps") or telemetry.get("laps") or []
    if not work_steps or not work_laps:
        return None, {"status": "skipped"}

    power_targets = [step.get("targets", {}).get("power_w") for step in work_steps if step.get("targets")]
    if not power_targets:
        return None, {"status": "skipped"}

    scored = 0
    hits = 0
    lap_rows: list[dict[str, Any]] = []
    for lap in work_laps[: len(power_targets)]:
        target = power_targets[scored]
        executed = lap.get("avg_power") or lap.get("normalized_power")
        if executed is None or not target:
            continue
        hit = _in_band(float(executed), target, tolerance_pct=0.08)
        if hit:
            hits += 1
        lap_rows.append(
            {
                "lap": lap.get("index"),
                "role": lap.get("role") or "work",
                "planned_w": round((target["low"] + target["high"]) / 2),
                "executed_w": round(float(executed)),
                "hit": hit,
            }
        )
        scored += 1

    if scored == 0:
        return None, {"status": "skipped"}

    hit_rate = hits / scored
    return 55.0 + 45.0 * hit_rate, {
        "status": "scored",
        "hit_rate": round(hit_rate, 2),
        "work_laps": lap_rows,
    }


def grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def score_planned_vs_executed(
    planned: dict[str, Any],
    telemetry: dict[str, Any],
    physiology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one planned workout against executed telemetry."""
    anchors = anchors_from_physiology(physiology)
    template_id = planned.get("library_template_id")
    template = get_template_by_id(str(template_id)) if template_id else None
    prescription = (
        build_template_prescription(template, planned, physiology)
        if template
        else {"source": "week_plan", "main_targets": {}}
    )

    duration_score, duration_detail = _score_duration(
        planned.get("duration_min"),
        telemetry.get("minutes"),
    )
    intensity_score, intensity_detail = _score_intensity(prescription, telemetry, anchors)
    interval_score, interval_detail = _score_interval_execution(prescription, telemetry)

    weights = {"duration": 0.25, "intensity": 0.45, "intervals": 0.30}
    if interval_score is None:
        weights = {"duration": 0.35, "intensity": 0.65, "intervals": 0.0}

    overall = (
        duration_score * weights["duration"]
        + intensity_score * weights["intensity"]
        + (interval_score or 0.0) * weights["intervals"]
    )
    overall = round(min(100.0, max(0.0, overall)), 1)

    overlay = {
        "source": prescription.get("source"),
        "template_id": prescription.get("template_id"),
        "aligned": interval_detail.get("status") == "scored" and interval_detail.get("hit_rate", 0) >= 0.5,
        "hit_rate": interval_detail.get("hit_rate"),
        "key_laps": [
            f"Lap {row['lap']} ({row['role']}): planned {row['planned_w']} W → {row['executed_w']} W"
            + (" ✓" if row.get("hit") else "")
            for row in (interval_detail.get("work_laps") or [])
        ],
        "duration": duration_detail,
        "intensity": intensity_detail,
        "target_labels": prescription.get("target_labels") or {},
    }

    return {
        "score": overall,
        "grade": grade_from_score(overall),
        "prescription": prescription,
        "prescribed_vs_executed": overlay,
        "dimensions": {
            "duration": round(duration_score, 1),
            "intensity": round(intensity_score, 1),
            "intervals": round(interval_score, 1) if interval_score is not None else None,
        },
    }


def compliance_for_planned_workout(
    planned: dict[str, Any],
    activity: Any,
    physiology: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build compliance report when an activity is linked to a planned workout."""
    if activity is None:
        return None
    from app.services.session_telemetry import analyze_activity

    telemetry = analyze_activity(activity, physiology or {})
    return score_planned_vs_executed(planned, telemetry, physiology)
