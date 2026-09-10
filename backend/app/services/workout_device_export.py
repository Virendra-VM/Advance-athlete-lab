"""Phase 5 SWL — export library workouts to Garmin/COROS-compatible device formats."""

from __future__ import annotations

import re
from typing import Any

from app.services.workout_compliance import resolve_numeric_targets
from app.services.workout_library import (
    apply_library_template,
    get_template_by_id,
    anchors_from_physiology,
)

EXPORT_VERSION = "1.0.0"

FIT_SPORT = {
    "running": 1,
    "cycling": 2,
    "swimming": 5,
    "strength": 10,
    "mobility": 10,
    "walking": 11,
    "trail_running": 1,
    "triathlon": 18,
    "rowing": 15,
    "cross_training": 10,
}

FIT_INTENSITY = {
    "warmup": 2,
    "cooldown": 3,
    "recovery": 4,
    "rest": 1,
    "work": 5,
    "interval": 5,
    "active": 0,
    "easy": 0,
}


def _ms_from_minutes(minutes: float) -> int:
    return max(1, int(round(float(minutes) * 60 * 1000)))


def _sport_key(workout: dict[str, Any], template: dict[str, Any] | None) -> str:
    sports = (template or {}).get("sports") or []
    if sports:
        return str(sports[0]).lower()
    blob = f"{workout.get('sport') or ''}".lower()
    if "cycl" in blob or "bike" in blob or "ride" in blob:
        return "cycling"
    if "swim" in blob:
        return "swimming"
    if "run" in blob or "trail" in blob:
        return "running"
    if "walk" in blob:
        return "walking"
    if "row" in blob:
        return "rowing"
    if "strength" in blob or "weight" in blob:
        return "strength"
    return "running"


def _step_target_fields(
    targets: dict[str, dict[str, float]] | None,
    *,
    prefer_power: bool,
) -> dict[str, Any]:
    targets = targets or {}
    if prefer_power and targets.get("power_w"):
        band = targets["power_w"]
        return {
            "target_type": 4,
            "custom_target_value_low": int(round(band["low"])),
            "custom_target_value_high": int(round(band["high"])),
            "target": {
                "type": "power",
                "low": int(round(band["low"])),
                "high": int(round(band["high"])),
                "unit": "w",
            },
        }
    if targets.get("hr_bpm"):
        band = targets["hr_bpm"]
        return {
            "target_type": 1,
            "custom_target_value_low": int(round(band["low"])),
            "custom_target_value_high": int(round(band["high"])),
            "target": {
                "type": "heart_rate",
                "low": int(round(band["low"])),
                "high": int(round(band["high"])),
                "unit": "bpm",
            },
        }
    return {
        "target_type": 2,
        "target": {"type": "open"},
    }


def _device_step(
    *,
    name: str,
    duration_min: float,
    role: str,
    targets: dict[str, dict[str, float]] | None,
    prefer_power: bool,
) -> dict[str, Any]:
    target_fields = _step_target_fields(targets, prefer_power=prefer_power)
    return {
        "name": name[:48],
        "duration_min": round(float(duration_min), 2),
        "duration_ms": _ms_from_minutes(duration_min),
        "role": role,
        "intensity": FIT_INTENSITY.get(role, 0),
        **target_fields,
    }


def template_to_device_steps(
    template: dict[str, Any],
    workout: dict[str, Any],
    physiology: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Flatten a library template into device-ready steps."""
    anchors = anchors_from_physiology(physiology)
    sport = _sport_key(workout, template)
    prefer_power = sport == "cycling" and bool(anchors.get("ftp_watts"))

    warmup_min = float(template.get("warmup_min") or 10)
    cooldown_min = float(template.get("cooldown_min") or 10)
    total_min = float(workout.get("duration_min") or template.get("duration_min", {}).get("default", 45))
    main_min = max(8.0, total_min - warmup_min - cooldown_min)

    steps: list[dict[str, Any]] = []
    steps.append(
        _device_step(
            name="Warm-up",
            duration_min=warmup_min,
            role="warmup",
            targets=None,
            prefer_power=prefer_power,
        )
    )

    main = template.get("main") or {}
    if main.get("type") == "repeat":
        reps = int(main.get("reps") or 1)
        on_spec = main.get("on") or {}
        off_spec = main.get("off") or {}
        on_min = float(on_spec.get("duration_min") or 5)
        off_min = float(off_spec.get("duration_min") or 0) if off_spec else 0.0
        on_targets = resolve_numeric_targets(on_spec.get("targets"), anchors)
        off_targets = resolve_numeric_targets(off_spec.get("targets"), anchors) if off_spec else None
        on_label = str(on_spec.get("label") or "Work")
        off_label = str(off_spec.get("label") or "Recovery")
        for rep in range(1, reps + 1):
            steps.append(
                _device_step(
                    name=f"{on_label} {rep}/{reps}",
                    duration_min=on_min,
                    role="interval",
                    targets=on_targets,
                    prefer_power=prefer_power,
                )
            )
            if off_min > 0:
                steps.append(
                    _device_step(
                        name=f"{off_label} {rep}/{reps}",
                        duration_min=off_min,
                        role="recovery",
                        targets=off_targets,
                        prefer_power=prefer_power,
                    )
                )
    else:
        steps.append(
            _device_step(
                name=str(main.get("intensity") or "Main set"),
                duration_min=main_min,
                role="work",
                targets=resolve_numeric_targets(main.get("targets"), anchors),
                prefer_power=prefer_power,
            )
        )

    steps.append(
        _device_step(
            name="Cool-down",
            duration_min=cooldown_min,
            role="cooldown",
            targets=None,
            prefer_power=prefer_power,
        )
    )
    return steps


def build_device_export(
    workout: dict[str, Any],
    physiology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build export package (JSON steps + encoded files) for one planned workout."""
    enriched = dict(workout)
    template_id = enriched.get("library_template_id")
    template = get_template_by_id(str(template_id)) if template_id else None
    if template is None:
        enriched = apply_library_template(enriched, physiology=physiology) or enriched
        template_id = enriched.get("library_template_id")
        template = get_template_by_id(str(template_id)) if template_id else None
    if template is None:
        raise ValueError("No library template available for device export.")

    steps = template_to_device_steps(template, enriched, physiology)
    sport = _sport_key(enriched, template)
    title = str(enriched.get("title") or template.get("title") or "AAL Workout")
    safe_name = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_") or "workout"

    package = {
        "export_version": EXPORT_VERSION,
        "template_id": template.get("id"),
        "template_version": template.get("version") or 1,
        "title": title,
        "sport": sport,
        "filename_stem": safe_name,
        "steps": steps,
        "formats": {},
    }

    package["formats"]["json"] = {
        "content_type": "application/json",
        "filename": f"{safe_name}.json",
        "payload": {
            "title": title,
            "sport": sport,
            "template_id": template.get("id"),
            "steps": steps,
        },
    }

    fit_bytes = encode_fit_workout(steps, sport=sport, title=title)
    package["formats"]["fit"] = {
        "content_type": "application/vnd.ant.fit",
        "filename": f"{safe_name}.fit",
        "bytes": fit_bytes,
    }

    if sport == "cycling":
        zwo = encode_zwo_workout(steps, title=title, physiology=physiology)
        package["formats"]["zwo"] = {
            "content_type": "application/xml",
            "filename": f"{safe_name}.zwo",
            "text": zwo,
        }

    return package


def encode_fit_workout(steps: list[dict[str, Any]], *, sport: str, title: str) -> bytes:
    from garmin_fit_sdk import Encoder, Profile

    mesg_num = Profile["mesg_num"]
    encoder = Encoder()
    encoder.write_mesg(
        {
            "mesg_num": mesg_num["FILE_ID"],
            "type": 5,
            "manufacturer": 1,
            "product": 0,
            "serial_number": 0,
            "time_created": 0,
        }
    )
    encoder.write_mesg(
        {
            "mesg_num": mesg_num["WORKOUT"],
            "sport": FIT_SPORT.get(sport, 0),
            "num_valid_steps": len(steps),
            "wkt_name": title[:48],
        }
    )
    for index, step in enumerate(steps):
        payload: dict[str, Any] = {
            "mesg_num": mesg_num["WORKOUT_STEP"],
            "message_index": index,
            "wkt_step_name": step["name"],
            "duration_type": 0,
            "duration_value": step["duration_ms"],
            "target_type": step.get("target_type", 2),
            "intensity": step.get("intensity", 0),
        }
        if step.get("target_type") == 4:
            payload["custom_target_value_low"] = step.get("custom_target_value_low")
            payload["custom_target_value_high"] = step.get("custom_target_value_high")
        elif step.get("target_type") == 1:
            payload["custom_target_value_low"] = step.get("custom_target_value_low")
            payload["custom_target_value_high"] = step.get("custom_target_value_high")
        encoder.write_mesg(payload)
    return encoder.close()


def encode_zwo_workout(
    steps: list[dict[str, Any]],
    *,
    title: str,
    physiology: dict[str, Any] | None,
) -> str:
    """Zwift / TrainerRoad-compatible ZWO for cycling workouts."""
    anchors = anchors_from_physiology(physiology)
    ftp = float(anchors.get("ftp_watts") or 200)

    def _power_attrs(step: dict[str, Any]) -> str:
        target = step.get("target") or {}
        if target.get("type") == "power":
            low = float(target["low"]) / ftp
            high = float(target["high"]) / ftp
            if abs(low - high) < 0.02:
                return f' Power="{low:.3f}"'
            return f' PowerLow="{low:.3f}" PowerHigh="{high:.3f}"'
        return ""

    def _tag(step: dict[str, Any]) -> str:
        duration = int(round(step["duration_min"] * 60))
        attrs = f'Duration="{duration}"{_power_attrs(step)}'
        role = step.get("role")
        if role == "warmup":
            return f"    <Warmup {attrs} />"
        if role == "cooldown":
            return f"    <Cooldown {attrs} />"
        if role in {"recovery", "rest"}:
            return f"    <Rest {attrs} />"
        if role == "interval" and step.get("target", {}).get("type") == "power":
            power = float(step["target"]["low"]) / ftp
            return f'    <IntervalsT Repeat="1" OnDuration="{duration}" OffDuration="0" OnPower="{power:.3f}" OffPower="0.55"/>'
        power_attr = _power_attrs(step)
        if power_attr:
            return f"    <SteadyState {attrs}{power_attr} />"
        return f"    <SteadyState {attrs} />"

    body = "\n".join(_tag(step) for step in steps)
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<workout_file>\n"
        "  <author>Advance Athlete Lab</author>\n"
        f"  <name>{safe_title}</name>\n"
        "  <sportType>bike</sportType>\n"
        "  <workout>\n"
        f"{body}\n"
        "  </workout>\n"
        "</workout_file>\n"
    )


def validate_fit_bytes(data: bytes) -> dict[str, Any]:
    import fitdecode

    steps = 0
    sport = None
    with fitdecode.FitReader(data) as reader:
        for frame in reader:
            if isinstance(frame, fitdecode.FitDataMessage):
                if frame.name == "workout":
                    sport = next((f.value for f in frame.fields if f.name == "sport"), None)
                if frame.name == "workout_step":
                    steps += 1
    return {"valid": steps > 0, "sport": sport, "step_count": steps}
