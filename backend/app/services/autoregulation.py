"""Daily autoregulation — Today's Call tiers, downgrade rules, warning flags."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.models import AthleteProfile
from app.services.biometric_baselines import (
    compute_baselines,
    fetch_biometric_rows,
    hrv_delta_pct,
    recent_readiness_scores,
    recent_sleep_hours,
    sleep_hours_from_row,
)
from app.services.training_load import compute_acwr


class TrainingCallLevel(str, Enum):
    HARD = "hard"
    MODERATE = "moderate"
    EASY = "easy"
    REST = "rest"


class WarningFlag(str, Enum):
    RECOVERY_DEBT = "recovery_debt"
    INJURY_RISK = "injury_risk"
    SLEEP_DEBT = "sleep_debt"
    PERIOD_INCOMING = "period_incoming"
    SPINE_VULNERABILITY = "spine_vulnerability"


LEVEL_ORDER = [
    TrainingCallLevel.REST,
    TrainingCallLevel.EASY,
    TrainingCallLevel.MODERATE,
    TrainingCallLevel.HARD,
]

CALL_META = {
    TrainingCallLevel.REST: {
        "color": "red",
        "label": "🔴 REST / RESTORE",
        "directive": "Restore first — off or mobility only.",
        "max_hard_sessions_today": 0,
    },
    TrainingCallLevel.EASY: {
        "color": "orange",
        "label": "🟠 EASY / BUILD BASE",
        "directive": "Easy aerobic or mobility only — no quality work today.",
        "max_hard_sessions_today": 0,
    },
    TrainingCallLevel.MODERATE: {
        "color": "amber",
        "label": "🟡 MODERATE / STEADY",
        "directive": "Steady aerobic allowed; keep any intensity controlled.",
        "max_hard_sessions_today": 1,
    },
    TrainingCallLevel.HARD: {
        "color": "green",
        "label": "🟢 HARD / QUALITY OK",
        "directive": "Quality sessions allowed if the week calls for them.",
        "max_hard_sessions_today": 1,
    },
}

WARNING_LINKS = {
    WarningFlag.RECOVERY_DEBT.value: "/health/hrv",
    WarningFlag.INJURY_RISK.value: "/training/volume",
    WarningFlag.SLEEP_DEBT.value: "/health/sleep",
    WarningFlag.SPINE_VULNERABILITY.value: "/profile#profile-health",
}


def _level_index(level: TrainingCallLevel) -> int:
    return LEVEL_ORDER.index(level)


def _downgrade(level: TrainingCallLevel, steps: int = 1) -> TrainingCallLevel:
    index = max(0, _level_index(level) - max(0, steps))
    return LEVEL_ORDER[index]


def _readiness_base(readiness: float | None) -> TrainingCallLevel:
    if readiness is None:
        return TrainingCallLevel.EASY
    if readiness >= 85:
        return TrainingCallLevel.HARD
    if readiness >= 75:
        return TrainingCallLevel.MODERATE
    if readiness >= 65:
        return TrainingCallLevel.EASY
    return TrainingCallLevel.REST


def _fallback_base(
    hrv: float | None,
    hrv_baseline: float | None,
    sleep_hours: float | None,
) -> TrainingCallLevel:
    hrv_ok = hrv is not None and hrv_baseline is not None and hrv >= hrv_baseline
    sleep_ok = sleep_hours is not None and sleep_hours >= 7.0
    if hrv_ok and sleep_ok:
        return TrainingCallLevel.MODERATE
    if sleep_hours is not None and sleep_hours >= 6.0:
        return TrainingCallLevel.EASY
    return TrainingCallLevel.REST


def resolve_todays_call(
    *,
    readiness_score: float | None,
    hrv: float | None,
    hrv_baseline: float | None,
    sleep_hours: float | None,
    acwr: float | None,
    recent_sleep: list[float] | None = None,
    recent_readiness: list[float] | None = None,
    spine_vulnerable: bool = False,
    menstrual_downgrade_steps: int = 0,
    menstrual_reasons: list[str] | None = None,
    menstrual_warnings: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Pure tier resolver — used by compute_todays_call and tests."""
    downgrade_reasons: list[str] = []
    warnings: list[dict[str, str]] = []

    if readiness_score is not None:
        base = _readiness_base(readiness_score)
        base_source = "readiness"
    else:
        base = _fallback_base(hrv, hrv_baseline, sleep_hours)
        base_source = "hrv_sleep_fallback"

    level = base
    delta = hrv_delta_pct(hrv, hrv_baseline)

    if isinstance(acwr, (int, float)) and acwr > 1.5:
        level = TrainingCallLevel.REST
        downgrade_reasons.append(f"ACWR {acwr:.2f} > 1.5 — spike risk")
    elif delta is not None and delta <= -15:
        level = TrainingCallLevel.REST
        downgrade_reasons.append(f"HRV {delta:.1f}% vs baseline — deep suppression")
    elif sleep_hours is not None and sleep_hours < 5:
        level = TrainingCallLevel.REST
        downgrade_reasons.append(f"Sleep {sleep_hours:.1f}h < 5h")

    if level not in (TrainingCallLevel.REST,) and downgrade_reasons:
        pass  # already forced REST
    elif level not in (TrainingCallLevel.REST,):
        steps = 0
        if delta is not None and delta <= -7:
            steps += 1
            downgrade_reasons.append(f"HRV {delta:.1f}% vs baseline")
        if sleep_hours is not None and sleep_hours < 6:
            steps += 1
            downgrade_reasons.append(f"Sleep {sleep_hours:.1f}h < 6h")
        if steps:
            level = _downgrade(level, steps)

    if isinstance(acwr, (int, float)) and acwr >= 1.3:
        warnings.append(
            {
                "code": WarningFlag.INJURY_RISK.value,
                "message": f"Training load ratio {acwr:.2f} — injury risk elevated",
                "severity": "warn",
                "link": WARNING_LINKS[WarningFlag.INJURY_RISK.value],
            }
        )

    recent_sleep = recent_sleep or []
    if len(recent_sleep) >= 2 and sum(1 for hours in recent_sleep[:3] if hours < 7) >= 2:
        warnings.append(
            {
                "code": WarningFlag.SLEEP_DEBT.value,
                "message": "Two of the last three nights under 7h sleep",
                "severity": "warn",
                "link": WARNING_LINKS[WarningFlag.SLEEP_DEBT.value],
            }
        )

    recent_readiness = recent_readiness or []
    if len(recent_readiness) >= 3 and all(score < 65 for score in recent_readiness[:3]):
        warnings.append(
            {
                "code": WarningFlag.RECOVERY_DEBT.value,
                "message": "Readiness under 65 for three consecutive days",
                "severity": "warn",
                "link": WARNING_LINKS[WarningFlag.RECOVERY_DEBT.value],
            }
        )

    if spine_vulnerable:
        warnings.append(
            {
                "code": WarningFlag.SPINE_VULNERABILITY.value,
                "message": "Active lower-back issue — protect spine today",
                "severity": "warn",
                "link": WARNING_LINKS[WarningFlag.SPINE_VULNERABILITY.value],
            }
        )
        if level in (TrainingCallLevel.HARD, TrainingCallLevel.MODERATE):
            level = _downgrade(level, 1)
            downgrade_reasons.append("Active lower-back injury")

    if menstrual_downgrade_steps > 0 and level not in (TrainingCallLevel.REST,):
        level = _downgrade(level, menstrual_downgrade_steps)
        downgrade_reasons.extend(menstrual_reasons or [])

    warnings.extend(menstrual_warnings or [])

    meta = CALL_META[level]
    acwr_zone = "unknown"
    if isinstance(acwr, (int, float)):
        if acwr > 1.5:
            acwr_zone = "high"
        elif acwr >= 1.3:
            acwr_zone = "caution"
        elif acwr < 0.8:
            acwr_zone = "low"
        else:
            acwr_zone = "in_range"

    return {
        "call_level": level.value,
        "base_level": base.value,
        "base_source": base_source,
        "label": meta["label"],
        "color": meta["color"],
        "directive": meta["directive"],
        "max_hard_sessions_today": meta["max_hard_sessions_today"],
        "downgrade_reasons": downgrade_reasons,
        "warnings": warnings,
        "metrics": {
            "readiness_score": readiness_score,
            "hrv": hrv,
            "hrv_baseline": hrv_baseline,
            "hrv_delta_pct": delta,
            "sleep_hours": sleep_hours,
            "acwr": acwr,
            "acwr_zone": acwr_zone,
        },
    }


def compute_todays_call(
    db: Session,
    athlete_profile_id: int,
    *,
    on_date: date | None = None,
    profile: AthleteProfile | None = None,
    physiology: dict | None = None,
) -> dict[str, Any]:
    on_date = on_date or date.today()
    rows = fetch_biometric_rows(db, athlete_profile_id, end_date=on_date, days=28)
    today_row = next((row for row in rows if row.metric_date == on_date), None)
    baselines = compute_baselines(rows, exclude_date=on_date)

    from app.services.coach_safety import injury_constraints
    from app.services.menstrual_engine import (
        build_cycle_context_for_athlete,
        menstrual_downgrade_steps,
    )

    injuries = injury_constraints(db, athlete_profile_id)
    spine_vulnerable = any(
        "back" in str(item).lower() or "spine" in str(item).lower()
        for item in injuries.get("active") or []
    )

    if profile is None:
        profile = (
            db.query(AthleteProfile).filter(AthleteProfile.id == athlete_profile_id).first()
        )

    cycle_ctx = (
        build_cycle_context_for_athlete(db, profile, on_date=on_date)
        if profile is not None
        else None
    )
    m_steps, m_reasons, m_warnings = menstrual_downgrade_steps(cycle_ctx)

    acwr_bundle = compute_acwr(db, athlete_profile_id, physiology=physiology)
    acwr = acwr_bundle.get("acwr")

    result = resolve_todays_call(
        readiness_score=today_row.readiness_score if today_row else None,
        hrv=today_row.heart_rate_variability if today_row else None,
        hrv_baseline=baselines.get("hrv_mean"),
        sleep_hours=sleep_hours_from_row(today_row),
        acwr=acwr,
        recent_sleep=recent_sleep_hours(rows, on_date, nights=3),
        recent_readiness=recent_readiness_scores(rows, on_date, days=3),
        spine_vulnerable=spine_vulnerable,
        menstrual_downgrade_steps=m_steps,
        menstrual_reasons=m_reasons,
        menstrual_warnings=m_warnings,
    )
    result["date"] = on_date.isoformat()
    result["baselines"] = baselines
    result["acwr"] = acwr_bundle
    result["cycle"] = cycle_ctx
    return result


def apply_autoregulation_to_safety(safety: dict, autoreg: dict | None) -> dict:
    """Merge Today's Call into the safety profile used by coach + validator."""
    if not autoreg:
        return safety
    adjusted = dict(safety)
    adjusted["autoregulation"] = autoreg
    adjusted["todays_call"] = autoreg

    level = autoreg.get("call_level")
    reasons = autoreg.get("downgrade_reasons") or []
    reason_text = "; ".join(reasons) if reasons else autoreg.get("directive") or "Autoregulation cap"

    if level == TrainingCallLevel.REST.value:
        adjusted["readiness"] = {
            "action": "rest_or_mobility",
            "max_hard_sessions_today": 0,
            "reason": reason_text,
        }
        adjusted["max_hard_sessions"] = 0
    elif level == TrainingCallLevel.EASY.value:
        adjusted["readiness"] = {
            "action": "downgrade_to_easy",
            "max_hard_sessions_today": 0,
            "reason": reason_text,
        }
        adjusted["max_hard_sessions"] = 0
    elif level == TrainingCallLevel.MODERATE.value:
        adjusted["max_hard_sessions"] = min(int(adjusted.get("max_hard_sessions") or 0), 1)

    return adjusted
