"""Training zone engine — multi-methodology anchors and zone tables.

Computes run HR (LTHR / max-HR / HRR), run pace (threshold-derived),
bike power (Coggan), and swim CSS zones from athlete profile anchors.
"""

from __future__ import annotations

from typing import Any

from app.services.workout_library import format_pace, format_swim_pace, parse_pace_seconds

# Coggan power zones as fractions of FTP.
POWER_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.0, 0.55),
    ("Z2 endurance", 0.56, 0.75),
    ("Z3 tempo", 0.76, 0.90),
    ("Z4 threshold", 0.91, 1.05),
    ("Z5 VO2max", 1.06, 1.20),
    ("Z6 anaerobic", 1.21, 1.50),
    ("Z7 neuromuscular", 1.51, 3.00),
)

# Friel-style HR zones relative to lactate threshold (LT2 / LTHR).
LTHR_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.0, 0.81),
    ("Z2 aerobic", 0.81, 0.89),
    ("Z3 tempo", 0.90, 0.93),
    ("Z4 threshold", 0.94, 0.99),
    ("Z5 super-threshold", 1.00, 1.06),
)

MAX_HR_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.50, 0.60),
    ("Z2 aerobic", 0.60, 0.70),
    ("Z3 tempo", 0.70, 0.80),
    ("Z4 threshold", 0.80, 0.90),
    ("Z5 VO2max", 0.90, 1.05),
)

# HRR (Karvonen) zone fractions of reserve (max − resting).
HRR_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Z1 recovery", 0.50, 0.60),
    ("Z2 aerobic", 0.60, 0.70),
    ("Z3 tempo", 0.70, 0.80),
    ("Z4 threshold", 0.80, 0.90),
    ("Z5 VO2max", 0.90, 1.00),
)

# Run pace zones as multipliers of threshold pace (sec/km — higher = slower).
RUN_PACE_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Recovery", 1.20, 1.30),
    ("Easy", 1.12, 1.20),
    ("Marathon", 1.05, 1.12),
    ("Threshold", 0.98, 1.02),
    ("VO2 / interval", 0.92, 0.98),
    ("Repetition", 0.88, 0.92),
)

# Swim CSS pace zones as multipliers of CSS (sec/100m).
SWIM_CSS_ZONE_DEFS: tuple[tuple[str, float, float], ...] = (
    ("Warmup", 1.10, 1.18),
    ("Aerobic", 1.05, 1.10),
    ("CSS / threshold", 0.98, 1.02),
    ("VO2", 0.92, 0.98),
)

RUN_HR_METHODS = frozenset({"lthr", "max_hr", "hrr"})
DEFAULT_RUN_HR_METHOD = "lthr"
DEFAULT_BIKE_POWER_METHOD = "coggan"
DEFAULT_RUN_PACE_METHOD = "threshold"


def _round(value: float | None, places: int = 0) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def bike_power_zones(ftp_watts: float | None) -> list[dict[str, Any]]:
    if not ftp_watts or ftp_watts < 50:
        return []
    ftp = float(ftp_watts)
    zones: list[dict[str, Any]] = []
    for name, low_frac, high_frac in POWER_ZONE_DEFS:
        zones.append(
            {
                "name": name,
                "low_w": round(ftp * low_frac),
                "high_w": round(ftp * high_frac),
                "low_frac": low_frac,
                "high_frac": high_frac,
                "method": DEFAULT_BIKE_POWER_METHOD,
            }
        )
    return zones


def run_hr_zones(
    *,
    lthr_bpm: float | None = None,
    max_hr_bpm: float | None = None,
    resting_hr_bpm: float | None = None,
    method: str | None = None,
) -> list[dict[str, Any]]:
    """Heart-rate zones for running (and general aerobic work)."""
    method = (method or DEFAULT_RUN_HR_METHOD).strip().lower()
    if method not in RUN_HR_METHODS:
        method = DEFAULT_RUN_HR_METHOD

    if method == "hrr":
        if not max_hr_bpm or max_hr_bpm < 120 or not resting_hr_bpm or resting_hr_bpm < 30:
            return []
        reserve = float(max_hr_bpm) - float(resting_hr_bpm)
        if reserve <= 10:
            return []
        zones: list[dict[str, Any]] = []
        for name, low_frac, high_frac in HRR_ZONE_DEFS:
            zones.append(
                {
                    "name": name,
                    "low_bpm": round(resting_hr_bpm + reserve * low_frac),
                    "high_bpm": round(resting_hr_bpm + reserve * high_frac),
                    "low_frac": low_frac,
                    "high_frac": high_frac,
                    "relative_to": "hrr",
                }
            )
        return zones

    if method == "max_hr" and max_hr_bpm and max_hr_bpm >= 120:
        anchor = float(max_hr_bpm)
        defs = MAX_HR_ZONE_DEFS
        kind = "max_hr"
    elif lthr_bpm and lthr_bpm >= 90:
        anchor = float(lthr_bpm)
        defs = LTHR_ZONE_DEFS
        kind = "lthr"
    elif max_hr_bpm and max_hr_bpm >= 120:
        anchor = float(max_hr_bpm)
        defs = MAX_HR_ZONE_DEFS
        kind = "max_hr"
    else:
        return []

    zones = []
    for name, low_frac, high_frac in defs:
        zones.append(
            {
                "name": name,
                "low_bpm": round(anchor * low_frac),
                "high_bpm": round(anchor * high_frac),
                "low_frac": low_frac,
                "high_frac": high_frac,
                "relative_to": kind,
            }
        )
    return zones


def run_pace_zones(
    threshold_pace_sec_per_km: float | None,
    *,
    lt1_pace_sec_per_km: float | None = None,
    marathon_pace_sec_per_km: float | None = None,
    method: str | None = None,
) -> list[dict[str, Any]]:
    """Run pace zones derived from threshold pace (sec/km)."""
    _ = lt1_pace_sec_per_km, marathon_pace_sec_per_km, method
    if not threshold_pace_sec_per_km or threshold_pace_sec_per_km <= 0:
        return []
    anchor = float(threshold_pace_sec_per_km)
    zones: list[dict[str, Any]] = []
    for name, low_mult, high_mult in RUN_PACE_ZONE_DEFS:
        low_sec = anchor * low_mult
        high_sec = anchor * high_mult
        zones.append(
            {
                "name": name,
                "low_sec_per_km": round(min(low_sec, high_sec), 1),
                "high_sec_per_km": round(max(low_sec, high_sec), 1),
                "low_pace": format_pace(min(low_sec, high_sec)),
                "high_pace": format_pace(max(low_sec, high_sec)),
                "low_mult": low_mult,
                "high_mult": high_mult,
                "relative_to": "threshold_pace",
            }
        )
    return zones


def swim_css_zones(css_sec_per_100m: float | None) -> list[dict[str, Any]]:
    if not css_sec_per_100m or css_sec_per_100m <= 0:
        return []
    anchor = float(css_sec_per_100m)
    zones: list[dict[str, Any]] = []
    for name, low_mult, high_mult in SWIM_CSS_ZONE_DEFS:
        low_sec = anchor * low_mult
        high_sec = anchor * high_mult
        zones.append(
            {
                "name": name,
                "low_sec_per_100m": round(min(low_sec, high_sec), 1),
                "high_sec_per_100m": round(max(low_sec, high_sec), 1),
                "low_pace": format_swim_pace(min(low_sec, high_sec)),
                "high_pace": format_swim_pace(max(low_sec, high_sec)),
                "relative_to": "css",
            }
        )
    return zones


def resolve_effective_hr_method(profile: Any, anchors: dict[str, Any] | None = None) -> str:
    """Pick HR zone model — fall back to max-HR when LTHR is missing."""
    anchors = anchors or profile_anchor_fields(profile)
    method = (anchors.get("zone_run_hr_method") or DEFAULT_RUN_HR_METHOD).strip().lower()
    if method == "lthr" and not anchors.get("lthr_bpm") and anchors.get("max_hr_bpm"):
        return "max_hr"
    if method not in RUN_HR_METHODS:
        return DEFAULT_RUN_HR_METHOD
    return method


def build_anchor_nudges(profile: Any, physiology: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Coach-facing hints when anchors are estimated rather than tested."""
    physiology = physiology or {}
    nudges: list[dict[str, Any]] = []
    lthr_manual = getattr(profile, "lthr_bpm", None) if profile is not None else None
    max_hr = getattr(profile, "max_hr_bpm", None) if profile is not None else None
    ftp_manual = getattr(profile, "ftp_watts", None) if profile is not None else None
    threshold = getattr(profile, "threshold_pace_sec_per_km", None) if profile is not None else None

    if physiology.get("lthr_source") == "estimated_from_max_hr" or (
        not lthr_manual and max_hr
    ):
        nudges.append(
            {
                "code": "confirm_lthr_test",
                "severity": "info",
                "message": (
                    "LTHR is estimated from max HR (90%). Add a 20-min threshold test "
                    "or D-race checkpoint for accurate HR zones."
                ),
                "action": "d_race_lthr_test",
            }
        )

    if not ftp_manual and physiology.get("ftp_source") == "estimated":
        nudges.append(
            {
                "code": "confirm_ftp_test",
                "severity": "info",
                "message": (
                    "FTP is estimated from recent ride power. A 30-min FTP test locks "
                    "in bike power zones."
                ),
                "action": "d_race_ftp_test",
            }
        )

    if not threshold:
        nudges.append(
            {
                "code": "add_threshold_pace",
                "severity": "info",
                "message": (
                    "Threshold run pace unlocks pace-based workouts. Connect COROS, "
                    "log a race, or enter pace manually."
                ),
                "action": "estimate_or_manual_pace",
            }
        )

    method = resolve_effective_hr_method(profile)
    stored_method = getattr(profile, "zone_run_hr_method", None) if profile else None
    if stored_method == "lthr" and method == "max_hr" and max_hr and not lthr_manual:
        nudges.append(
            {
                "code": "using_max_hr_zones",
                "severity": "info",
                "message": "Using max-HR zones because LTHR is not set yet.",
                "action": "set_lthr_or_keep_max_hr",
            }
        )

    return nudges


def profile_anchor_fields(profile: Any) -> dict[str, Any]:
    """Read stored anchor columns from an AthleteProfile (or dict)."""
    if profile is None:
        return {}

    def _get(key: str, default=None):
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    threshold = _get("threshold_pace_sec_per_km")
    if threshold is None:
        threshold = parse_pace_seconds(_get("threshold_pace"))

    css = _get("css_sec_per_100m")
    resting = _get("resting_hr_bpm")

    anchors = {
        "ftp_watts": _get("ftp_watts"),
        "lthr_bpm": _get("lthr_bpm"),
        "max_hr_bpm": _get("max_hr_bpm"),
        "bike_lthr_bpm": _get("bike_lthr_bpm"),
        "resting_hr_bpm": resting,
        "threshold_pace_sec_per_km": threshold,
        "lt1_pace_sec_per_km": _get("lt1_pace_sec_per_km"),
        "marathon_pace_sec_per_km": _get("marathon_pace_sec_per_km"),
        "css_sec_per_100m": css,
        "vo2max": _get("vo2max"),
        "zone_run_hr_method": _get("zone_run_hr_method") or DEFAULT_RUN_HR_METHOD,
        "zone_bike_power_method": _get("zone_bike_power_method") or DEFAULT_BIKE_POWER_METHOD,
        "zone_run_pace_method": _get("zone_run_pace_method") or DEFAULT_RUN_PACE_METHOD,
    }
    anchors["zone_run_hr_method"] = resolve_effective_hr_method(profile, anchors)
    return anchors


def merge_coros_anchors(anchors: dict[str, Any], coros_fitness: dict[str, Any] | None) -> dict[str, Any]:
    """Fill missing anchor values from latest COROS fitness snapshot."""
    coros_fitness = coros_fitness or {}
    merged = dict(anchors)
    if merged.get("vo2max") is None and coros_fitness.get("vo2max"):
        merged["vo2max"] = coros_fitness.get("vo2max")
    if merged.get("threshold_pace_sec_per_km") is None:
        parsed = parse_pace_seconds(coros_fitness.get("threshold_pace"))
        if parsed:
            merged["threshold_pace_sec_per_km"] = parsed
    return merged


def build_zone_tables(anchors: dict[str, Any] | None) -> dict[str, Any]:
    """Compute all zone tables from resolved anchors."""
    anchors = anchors or {}
    run_hr_method = resolve_effective_hr_method(anchors)
    run_lthr = anchors.get("lthr_bpm") or anchors.get("bike_lthr_bpm")
    threshold = anchors.get("threshold_pace_sec_per_km")
    css = anchors.get("css_sec_per_100m")
    if css is None and threshold:
        css = threshold * 0.18

    power = bike_power_zones(anchors.get("ftp_watts"))
    run_hr = run_hr_zones(
        lthr_bpm=run_lthr,
        max_hr_bpm=anchors.get("max_hr_bpm"),
        resting_hr_bpm=anchors.get("resting_hr_bpm"),
        method=run_hr_method,
    )
    run_pace = run_pace_zones(
        threshold,
        lt1_pace_sec_per_km=anchors.get("lt1_pace_sec_per_km"),
        marathon_pace_sec_per_km=anchors.get("marathon_pace_sec_per_km"),
        method=anchors.get("zone_run_pace_method"),
    )
    swim_pace = swim_css_zones(css)

    return {
        "power_zones": power,
        "hr_zones": run_hr,
        "run_pace_zones": run_pace,
        "swim_pace_zones": swim_pace,
        "methods": {
            "run_hr": run_hr_method,
            "bike_power": anchors.get("zone_bike_power_method") or DEFAULT_BIKE_POWER_METHOD,
            "run_pace": anchors.get("zone_run_pace_method") or DEFAULT_RUN_PACE_METHOD,
        },
    }


def build_anchors(anchors: dict[str, Any] | None) -> dict[str, Any]:
    """Normalized anchor dict for workout library / compliance."""
    anchors = anchors or {}
    threshold = anchors.get("threshold_pace_sec_per_km")
    if threshold is None:
        threshold = parse_pace_seconds(anchors.get("threshold_pace"))
    css = anchors.get("css_sec_per_100m")
    if css is None and threshold:
        css = threshold * 0.18
    return {
        "ftp_watts": anchors.get("ftp_watts"),
        "lthr_bpm": anchors.get("lthr_bpm") or anchors.get("bike_lthr_bpm"),
        "max_hr_bpm": anchors.get("max_hr_bpm"),
        "resting_hr_bpm": anchors.get("resting_hr_bpm"),
        "threshold_pace_sec_per_km": threshold,
        "lt1_pace_sec_per_km": anchors.get("lt1_pace_sec_per_km"),
        "marathon_pace_sec_per_km": anchors.get("marathon_pace_sec_per_km"),
        "css_sec_per_100m": css,
        "vo2max": anchors.get("vo2max"),
    }


def attach_zone_tables(physiology: dict[str, Any]) -> dict[str, Any]:
    """Merge zone tables into an existing physiology dict."""
    anchors = profile_anchor_fields(physiology)
    for key, value in physiology.items():
        if key.startswith("zone_") or value is None:
            continue
        if anchors.get(key) is None and key in anchors:
            anchors[key] = value
    tables = build_zone_tables(anchors)
    merged = dict(physiology)
    merged.update(tables)
    merged["anchors"] = build_anchors(anchors)
    return merged
