"""Schema validation for Science Workout Library templates."""

from __future__ import annotations

from typing import Any

REQUIRED_TEMPLATE_FIELDS = ("id", "sports", "session_types", "intent", "main", "evidence_tags")
VALID_MAIN_TYPES = {"steady", "repeat"}


def _steady_main(
    *,
    intensity: str,
    detail: str,
    targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"intensity": intensity, "detail": detail}
    if targets:
        body["targets"] = targets
    return body


def _repeat_main(
    *,
    intensity: str,
    reps: int,
    on_min: float,
    off_min: float,
    on_targets: dict[str, Any],
    off_targets: dict[str, Any] | None = None,
    detail_intro: str = "",
    on_label: str = "work",
    off_label: str = "recovery",
) -> dict[str, Any]:
    off = {"duration_min": off_min, "label": off_label, "targets": off_targets or {"rpe": {"low": 3, "high": 4}}}
    return {
        "type": "repeat",
        "intensity": intensity,
        "reps": reps,
        "on": {"duration_min": on_min, "label": on_label, "targets": on_targets},
        "off": off,
        "detail_intro": detail_intro,
    }


def normalize_template(raw: dict[str, Any]) -> dict[str, Any]:
    template = dict(raw)
    template.setdefault("version", 1)
    template["version"] = int(template["version"])
    if "sport" in template and "sports" not in template:
        template["sports"] = [template.pop("sport")]
    sports = template.get("sports")
    if isinstance(sports, str):
        template["sports"] = [sports]
    template.setdefault("priority", 10)
    template.setdefault("warmup_min", 10)
    template.setdefault("cooldown_min", 8)
    template.setdefault("warmup", {"detail": "Easy start. No hard efforts yet."})
    template.setdefault("cooldown", {"detail": "Easy cool-down and light stretch."})
    return template


def validate_template(template: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_TEMPLATE_FIELDS:
        if not template.get(field):
            errors.append(f"missing {field}")

    template_id = template.get("id")
    if template_id and not isinstance(template_id, str):
        errors.append("id must be a string")

    version = template.get("version", 1)
    if not isinstance(version, int) or version < 1:
        errors.append("version must be a positive integer")

    sports = template.get("sports")
    if sports is not None and not isinstance(sports, list):
        errors.append("sports must be a list")

    main = template.get("main") or {}
    if main.get("type") == "repeat":
        if not main.get("reps") or not main.get("on"):
            errors.append(f"{template_id}: repeat main requires reps and on")
    elif not main.get("detail") and not main.get("detail_template"):
        errors.append(f"{template_id}: main requires detail or detail_template")

    evidence = template.get("evidence_tags")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{template_id}: evidence_tags must be a non-empty list")

    return errors


def validate_catalog(templates: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    ids: dict[str, list[int]] = {}
    normalized: list[dict[str, Any]] = []

    for raw in templates:
        template = normalize_template(raw)
        normalized.append(template)
        errors.extend(validate_template(template))
        tid = str(template.get("id") or "")
        ver = int(template.get("version") or 1)
        ids.setdefault(tid, []).append(ver)

    for tid, versions in ids.items():
        if len(versions) != len(set(versions)):
            errors.append(f"duplicate version for template id {tid!r}")

    return {
        "valid": not errors,
        "errors": errors,
        "total": len(normalized),
        "unique_ids": len(ids),
        "templates": normalized,
    }
