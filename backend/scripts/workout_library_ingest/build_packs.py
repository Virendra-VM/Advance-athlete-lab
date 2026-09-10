#!/usr/bin/env python3
"""Generate Phase 3 expansion packs for the Science Workout Library.

Usage:
    python scripts/workout_library_ingest/build_packs.py
    python scripts/workout_library_ingest/build_packs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workout_library_schema import (  # noqa: E402
    _repeat_main,
    _steady_main,
    validate_catalog,
)

PACKS_DIR = BACKEND_ROOT / "data" / "workout_library" / "packs"

Z2_HR = {"hr_pct_lthr": {"low": 0.69, "high": 0.83}}
Z2_PACE = {"pace_pct_threshold": {"low": 1.15, "high": 1.32}}
THRESHOLD_HR = {"hr_pct_lthr": {"low": 0.95, "high": 1.02}}
THRESHOLD_PACE = {"pace_pct_threshold": {"low": 0.98, "high": 1.02}}
VO2_HR = {"hr_pct_lthr": {"low": 1.05, "high": 1.12}}
VO2_PACE = {"pace_pct_threshold": {"low": 0.88, "high": 0.94}}
FTP_THRESHOLD = {"pct_ftp": {"low": 0.91, "high": 1.05}}
FTP_SST = {"pct_ftp": {"low": 0.84, "high": 0.94}}
FTP_VO2 = {"pct_ftp": {"low": 1.06, "high": 1.20}}
CSS_THRESH = {"css_pct": {"low": 0.98, "high": 1.02}}
CSS_VO2 = {"css_pct": {"low": 0.88, "high": 0.94}}


def _base(
    id_: str,
    sports: list[str],
    session_types: list[str],
    intent: str,
    title: str,
    summary: str,
    evidence: list[str],
    main: dict,
    *,
    version: int = 1,
    priority: int = 10,
    phase_fit: list[str] | None = None,
    match_keywords: list[str] | None = None,
) -> dict:
    row = {
        "id": id_,
        "version": version,
        "sports": sports,
        "session_types": session_types,
        "intent": intent,
        "priority": priority,
        "title": title,
        "summary": summary,
        "evidence_tags": evidence,
        "warmup_min": 10,
        "cooldown_min": 8,
        "warmup": {"detail": "Easy aerobic start. Dynamic mobility. No hard efforts yet."},
        "cooldown": {"detail": "Easy cool-down. Stretch primary movers. Breathe."},
        "main": main,
    }
    if phase_fit:
        row["phase_fit"] = phase_fit
    if match_keywords:
        row["match_keywords"] = match_keywords
    return row


def running_pack() -> list[dict]:
    items = []
    specs = [
        ("run_treadmill_z2", "easy", "Treadmill Z2", "Indoor aerobic base", Z2_HR),
        ("run_treadmill_tempo", "tempo", "Treadmill tempo", "Indoor sub-threshold", {"hr_pct_lthr": {"low": 0.88, "high": 0.94}}),
        ("run_track_200s", "vo2", "Track 200 m reps", "Neuromuscular speed", VO2_HR),
        ("run_track_1k_repeats", "vo2", "Track 1K repeats", "VO2 speed endurance", VO2_HR),
        ("run_pyramid_1_2_3_2_1", "vo2", "Pyramid intervals", "Variable VO2 pyramid", VO2_HR),
        ("run_cutdown_5_4_3_2_1", "threshold", "Cut-down threshold", "Descending threshold blocks", THRESHOLD_HR),
        ("run_ladder_3_6_9_6_3", "tempo", "Tempo ladder", "Progressive tempo ladder", {"hr_pct_lthr": {"low": 0.85, "high": 0.96}}),
        ("run_doubles_am_easy", "easy", "Double day — easy AM", "Second run easy aerobic", Z2_HR),
        ("run_doubles_pm_strides", "strides", "Double day — strides PM", "Short PM neuromuscular", {"hr_pct_lthr": {"low": 0.70, "high": 0.85}}),
        ("run_hill_sprints_10x10", "hills", "Hill sprints (10×10 s)", "Alactic hill sprints", {"rpe": {"low": 9, "high": 10}}),
        ("run_marathon_pace_3x3", "race_pace", "Marathon pace 3×3 mi", "Marathon specificity", {"hr_pct_lthr": {"low": 0.85, "high": 0.92}}),
        ("run_half_marathon_pace_4x2", "race_pace", "HM pace 4×2 mi", "Half-marathon specificity", {"hr_pct_lthr": {"low": 0.90, "high": 0.96}}),
        ("run_5k_pace_8x400", "race_pace", "5K pace 8×400 m", "5K race-pace reps", VO2_PACE),
        ("run_aerobic_te", "easy", "Aerobic threshold (TE)", "Upper Z2 aerobic development", {"hr_pct_lthr": {"low": 0.80, "high": 0.88}}),
        ("run_broken_long_3x20", "long", "Broken long run", "Long aerobic with short breaks", Z2_HR),
        ("run_walk_ultra", "long", "Ultra run-walk", "Time-on-feet ultra prep", {"hr_pct_lthr": {"low": 0.65, "high": 0.78}}),
        ("run_heat_acclimation_easy", "easy", "Heat acclimation easy", "Easy heat exposure", Z2_HR),
        ("run_altitude_easy", "easy", "Altitude easy run", "Easy aerobic at elevation", Z2_HR),
        ("run_form_drills", "easy", "Easy run + drills", "Economy drills post easy run", Z2_HR),
        ("run_parkrun_sim", "race", "Parkrun simulation", "5K race rehearsal", VO2_HR),
        ("run_negative_split_long", "progression", "Negative-split long", "Progressive long run", Z2_HR),
        ("run_marathon_specific_20", "long", "20 mi long run", "Marathon long run", Z2_HR),
    ]
    for id_, intent, title, summary, targets in specs:
        if intent == "vo2" and "track" in id_:
            main = _repeat_main(intensity="VO₂ max", reps=8, on_min=0.75, off_min=1.5, on_targets=targets, detail_intro="Track 200 m reps — full recovery.")
        elif intent == "vo2":
            main = _repeat_main(intensity="VO₂ max", reps=5, on_min=3, off_min=2, on_targets=targets)
        elif intent == "threshold" and "cutdown" in id_:
            main = _steady_main(intensity="Threshold cut-down", detail="5-4-3-2-1 min threshold blocks descending with 2 min easy between.", targets=targets)
        elif intent in {"long", "easy", "progression", "strides", "race"}:
            main = _steady_main(intensity="Moderate" if intent != "easy" else "Easy", detail=f"{title} for {{main_min}} min.", targets=targets)
        elif intent == "hills":
            main = _repeat_main(intensity="Hill sprint", reps=10, on_min=0.17, off_min=2, on_targets=targets, on_label="uphill sprint")
        else:
            main = _steady_main(intensity="Moderate-hard", detail=f"{title} session.", targets=targets)
        items.append(
            _base(id_, ["running"], ["intervals" if intent == "vo2" else intent if intent != "strides" else "easy"], intent, title, summary, ["polarized", "sessions", intent], main)
        )
    return items


def cycling_pack() -> list[dict]:
    items = []
    specs = [
        ("bike_erg_z2", "easy", "ERG endurance", "Indoor Z2 aerobic", {"pct_ftp": {"low": 0.56, "high": 0.72}}),
        ("bike_erg_sweet_spot_3x15", "sweet_spot", "ERG sweet spot 3×15", "Sustained sweet spot", FTP_SST),
        ("bike_erg_vo2_6x2", "vo2", "ERG VO2 6×2", "Short VO2 on trainer", FTP_VO2),
        ("bike_outdoor_endurance", "easy", "Outdoor endurance", "Outdoor Z2 ride", {"pct_ftp": {"low": 0.56, "high": 0.70}}),
        ("bike_group_ride_recovery", "easy", "Group ride — recovery", "Social easy spin", {"pct_ftp": {"low": 0.50, "high": 0.65}}),
        ("bike_coffee_ride", "easy", "Coffee ride", "Very easy social ride", {"pct_ftp": {"low": 0.45, "high": 0.60}}),
        ("bike_ramp_test_prep", "threshold", "Ramp test prep", "Opener before FTP test", {"pct_ftp": {"low": 0.85, "high": 1.05}}),
        ("bike_polarized_easy", "easy", "Polarized easy day", "Strict Z2 polarized day", {"pct_ftp": {"low": 0.56, "high": 0.75}}),
        ("bike_polarized_vo2", "vo2", "Polarized VO2 day", "Hard polarized day", FTP_VO2),
        ("bike_cadence_high_4x3", "tempo", "High-cadence blocks", "Pedaling efficiency at tempo", {"pct_ftp": {"low": 0.76, "high": 0.88}}),
        ("bike_cadence_low_4x5", "tempo", "Low-cadence strength", "Force production blocks", {"pct_ftp": {"low": 0.75, "high": 0.85}}),
        ("bike_gravel_endurance", "long", "Gravel endurance", "Mixed terrain aerobic", {"pct_ftp": {"low": 0.56, "high": 0.72}}),
        ("bike_criterium_sim", "race_pace", "Criterium simulation", "Repeated surges", {"pct_ftp": {"low": 0.95, "high": 1.15}}),
        ("bike_time_trial_prep", "race_pace", "Time trial prep", "TT pacing practice", {"pct_ftp": {"low": 0.95, "high": 1.02}}),
        ("bike_gran_fondo_long", "long", "Gran fondo long ride", "Event-specific volume", {"pct_ftp": {"low": 0.56, "high": 0.70}}),
        ("bike_indoor_zwift_race_prep", "race_pace", "Virtual race prep", "Race-start efforts", FTP_VO2),
        ("bike_one_leg_drills", "easy", "Single-leg drills", "Pedaling symmetry", {"pct_ftp": {"low": 0.50, "high": 0.65}}),
        ("bike_over_under_short", "over_under", "Short over-unders", "Compact OU session", {"pct_ftp": {"low": 0.88, "high": 1.15}}),
        ("bike_endurance_fasted", "easy", "Fasted easy ride", "Optional fasted Z2 — skip if tired", {"pct_ftp": {"low": 0.56, "high": 0.68}}),
        ("bike_recovery_spin_legs", "easy", "Leg opener spin", "Pre-event opener", {"pct_ftp": {"low": 0.45, "high": 0.55}}),
        ("bike_40k_tt_blocks", "race_pace", "40K TT blocks", "Tri bike TT specificity", {"pct_ftp": {"low": 0.92, "high": 0.98}}),
        ("bike_mountain_climb", "hills", "Mountain climb repeats", "Long climb power", {"pct_ftp": {"low": 0.90, "high": 1.05}}),
    ]
    for id_, intent, title, summary, targets in specs:
        st = "intervals" if intent == "vo2" else "threshold" if intent in {"threshold", "sweet_spot", "over_under"} else intent
        if intent == "vo2":
            main = _repeat_main(intensity="VO₂", reps=6, on_min=2, off_min=3, on_targets=targets)
        elif intent == "sweet_spot":
            main = _repeat_main(intensity="Sweet spot", reps=3, on_min=15, off_min=5, on_targets=targets)
        elif intent == "over_under":
            main = _steady_main(intensity="Over-under", detail="3×9 min OU blocks: 2 min under / 45 s over, 4 min easy between.", targets=targets)
        else:
            main = _steady_main(intensity="Moderate", detail=f"{title} for {{main_min}} min.", targets=targets)
        items.append(_base(id_, ["cycling"], [st if st in {"easy", "long", "tempo", "hills", "race"} else "threshold" if st == "sweet_spot" else "intervals"], intent, title, summary, ["ftp", "zones", intent], main))
    return items


def swimming_pack() -> list[dict]:
    items = []
    specs = [
        ("swim_im_set_10x100", "threshold", "IM 10×100", "Individual medley aerobic", CSS_THRESH),
        ("swim_freestyle_pyramid", "tempo", "Freestyle pyramid", "Pacing discipline", CSS_THRESH),
        ("swim_broken_1500", "long", "Broken 1500", "Aerobic swim volume", {"css_pct": {"low": 1.05, "high": 1.15}}),
        ("swim_paddle_pull_5x200", "tempo", "Paddle pull 5×200", "Upper-body strength endurance", {"css_pct": {"low": 1.00, "high": 1.08}}),
        ("swim_band_only_20", "easy", "Band-only recovery", "Shoulder prehab swim", {"rpe": {"low": 3, "high": 5}}),
        ("swim_snorkel_technique", "easy", "Snorkel technique", "Body position focus", {"rpe": {"low": 4, "high": 5}}),
        ("swim_open_water_continuous", "long", "Open-water continuous", "OW endurance", {"css_pct": {"low": 1.08, "high": 1.18}}),
        ("swim_race_start_8x50", "vo2", "Race-start 8×50", "Start speed", CSS_VO2),
        ("swim_backstroke_recovery", "easy", "Backstroke recovery", "Active recovery mix", {"css_pct": {"low": 1.12, "high": 1.25}}),
        ("swim_kick_only_16x50", "tempo", "Kick-only 16×50", "Kick development", {"rpe": {"low": 6, "high": 7}}),
        ("swim_swolf_test", "easy", "SWOLF efficiency test", "Efficiency benchmarking", {"rpe": {"low": 5, "high": 6}}),
        ("swim_css_neg_split_5x200", "threshold", "CSS negative split 5×200", "Pacing control at CSS", CSS_THRESH),
        ("swim_sprint_25s_20", "vo2", "Sprint 25s ×20", "Anaerobic capacity", CSS_VO2),
        ("swim_endurance_paddle", "long", "Endurance paddle set", "Long pull endurance", {"css_pct": {"low": 1.02, "high": 1.10}}),
    ]
    for id_, intent, title, summary, targets in specs:
        st = "intervals" if intent == "vo2" else intent
        if intent == "vo2":
            main = _repeat_main(intensity="Hard", reps=8, on_min=0.75, off_min=0.5, on_targets=targets, on_label="50 m hard")
        else:
            main = _steady_main(intensity="Moderate", detail=f"{title}.", targets=targets)
        items.append(_base(id_, ["swimming"], [st], intent, title, summary, ["swim", "css", intent], main))
    return items


def strength_pack() -> list[dict]:
    items = []
    specs = [
        ("strength_kettlebell_complex", "strength_general", "Kettlebell complex", "KB full-body strength", {"rpe": {"low": 7, "high": 8}}),
        ("strength_barbell_squat_day", "strength_general", "Barbell squat day", "Squat emphasis", {"rpe": {"low": 7, "high": 8}}),
        ("strength_deadlift_day", "strength_general", "Deadlift day", "Hinge emphasis", {"rpe": {"low": 7, "high": 8}}),
        ("strength_bench_press_day", "strength_general", "Bench press day", "Upper push emphasis", {"rpe": {"low": 7, "high": 8}}),
        ("strength_olympic_clean_pull", "strength_power", "Clean pull technique", "Olympic pull pattern", {"rpe": {"low": 6, "high": 8}}),
        ("strength_snatch_technique", "strength_power", "Snatch technique", "Snatch positions", {"rpe": {"low": 6, "high": 7}}),
        ("strength_calisthenics", "strength_general", "Calisthenics circuit", "Bodyweight strength", {"rpe": {"low": 6, "high": 7}}),
        ("strength_runner_legs", "strength_prehab", "Runner leg strength", "Single-leg runner focus", {"rpe": {"low": 6, "high": 7}}),
        ("strength_cyclist_glutes", "strength_prehab", "Cyclist glute strength", "Hip extension for cycling", {"rpe": {"low": 6, "high": 7}}),
        ("strength_swimmer_band", "strength_prehab", "Swimmer band work", "Rotator cuff and scapular", {"rpe": {"low": 5, "high": 6}}),
        ("strength_upper_hypertrophy", "strength_hypertrophy", "Upper hypertrophy", "Upper body muscle endurance", {"rpe": {"low": 7, "high": 8}}),
        ("strength_lower_hypertrophy", "strength_hypertrophy", "Lower hypertrophy", "Lower body hypertrophy", {"rpe": {"low": 7, "high": 8}}),
        ("strength_plyo_lower", "strength_power", "Lower plyometrics", "Explosive lower body", {"rpe": {"low": 7, "high": 9}}),
        ("strength_mobility_coupled", "strength_general", "Strength + mobility", "Strength with mobility finisher", {"rpe": {"low": 6, "high": 7}}),
        ("strength_trx_full_body", "strength_general", "TRX full body", "Suspension training", {"rpe": {"low": 6, "high": 7}}),
        ("strength_german_volume", "strength_hypertrophy", "German volume 10×10", "Hypertrophy density", {"rpe": {"low": 7, "high": 8}}),
        ("strength_5x5_linear", "strength_general", "5×5 linear progression", "Max strength progression", {"rpe": {"low": 8, "high": 9}}),
        ("strength_wendler_531", "strength_general", "5/3/1 wave", "Periodized strength wave", {"rpe": {"low": 7, "high": 9}}),
    ]
    for id_, intent, title, summary, targets in specs:
        main = _steady_main(
            intensity="RPE guided",
            detail=f"{title}: 3–4 exercises, 3–4 sets, quality reps with full rest.",
            targets=targets,
        )
        items.append(_base(id_, ["strength"], ["strength"], intent, title, summary, ["strength", "periodization"], main, match_keywords=[word for word in title.lower().split()[:2]]))
    return items


def mobility_pack() -> list[dict]:
    items = []
    specs = [
        ("mobility_dynamic_warmup", "mobility_general", "Dynamic warm-up", "Full dynamic warm-up flow"),
        ("mobility_pnf_hamstring", "mobility_general", "PNF hamstring stretch", "PNF flexibility — hamstrings"),
        ("mobility_hip_flexor_deep", "mobility_general", "Deep hip flexor release", "Hip flexor mobility for desk athletes"),
        ("mobility_runner_post_run", "mobility_general", "Post-run stretch routine", "Post-run static stretch"),
        ("mobility_cyclist_hips", "mobility_post_ride", "Cyclist hip release", "Post-ride hip and T-spine"),
        ("mobility_swim_cord", "mobility_swim_shoulder", "Swimmer cord routine", "Band work for swim shoulders"),
        ("mobility_yin_yoga", "mobility_general", "Yin yoga holds", "Long-hold yin practice"),
        ("mobility_pilates_core", "mobility_general", "Pilates core flow", "Core stability and control"),
        ("mobility_foam_roll_full", "mobility_general", "Full foam roll", "Self-myofascial release"),
        ("mobility_breathwork", "mobility_general", "Breathwork recovery", "Parasympathetic breathing"),
        ("mobility_ankle_knee", "mobility_general", "Ankle-knee chain", "Lower leg mobility chain"),
        ("mobility_golf_rotation", "mobility_general", "Rotational mobility", "Thoracic and hip rotation"),
    ]
    for id_, intent, title, summary in specs:
        main = _steady_main(intensity="Easy restore", detail=f"{title} for {{main_min}} min.", targets={"rpe": {"low": 2, "high": 4}})
        items.append(_base(id_, ["mobility"], ["mobility"], intent, title, summary, ["mobility", "recovery"], main))
    return items


def trail_pack() -> list[dict]:
    items = []
    specs = [
        ("trail_technical_downhill", "hills", "Technical downhill", "Downhill skill and eccentric prep"),
        ("trail_vert_intervals", "hills", "Vert intervals", "Vertical gain intervals"),
        ("trail_ridge_run", "long", "Ridge run long", "Rolling trail long run"),
        ("trail_night_easy", "easy", "Night trail easy", "Easy trail in low light"),
        ("trail_snow_easy", "easy", "Snow trail easy", "Easy snow/ice trail"),
        ("trail_skyrace_sim", "race_pace", "Skyrace simulation", "Skyrace effort simulation"),
        ("trail_ultra_back_to_back", "long", "Ultra back-to-back", "Consecutive day trail volume"),
        ("trail_power_hike", "hills", "Power hiking", "Hiking-specific vert training"),
        ("trail_muddy_technical", "easy", "Muddy technical easy", "Technical terrain at easy effort"),
        ("trail_stage_race_day", "race_pace", "Stage race day", "Multi-day stage simulation"),
    ]
    for id_, intent, title, summary in specs:
        st = "race" if intent == "race_pace" else intent
        main = _steady_main(intensity="Moderate", detail=f"{title} on trail terrain.", targets=Z2_HR if intent == "easy" else THRESHOLD_HR)
        items.append(_base(id_, ["trail_running"], [st], intent, title, summary, ["trail", intent], main))
    return items


def tri_pack() -> list[dict]:
    items = []
    specs = [
        ("tri_70_3_brick_long", "cross_training", "70.3 long brick", "Long race-specific brick"),
        ("tri_ironman_brick", "cross_training", "Ironman brick", "IM distance brick simulation"),
        ("tri_swim_run", "cross_training", "Swim-run combo", "Aquathlon prep"),
        ("tri_bike_focus_day", "threshold", "Tri bike focus", "Bike-heavy tri day"),
        ("tri_run_focus_day", "race_pace", "Tri run focus", "Run-heavy off bike"),
        ("tri_race_week_prep", "easy", "Tri race week prep", "Pre-race activation"),
        ("tri_open_water_bike", "cross_training", "OW swim + bike", "Open-water to bike transition"),
        ("tri_duathlon_run_bike_run", "cross_training", "Duathlon simulation", "Run-bike-run practice"),
    ]
    for id_, intent, title, summary in specs:
        main = _steady_main(intensity="Race prep", detail=f"{title}.", targets=FTP_SST if "bike" in id_ else THRESHOLD_HR)
        st = "cross-training" if intent == "cross_training" else "easy" if intent == "easy" else "threshold"
        items.append(_base(id_, ["triathlon"], [st], intent, title, summary, ["triathlon", "race-specific"], main))
    return items


def rowing_pack() -> list[dict]:
    items = []
    specs = [
        ("row_easy_aerobic", "easy", "Easy aerobic row", "Z2 rowing base"),
        ("row_long_steady", "long", "Long steady row", "Aerobic endurance row"),
        ("row_2k_pace_intervals", "vo2", "2K pace intervals", "VO2 rowing intervals"),
        ("row_6k_pace_steady", "threshold", "6K pace steady", "Threshold row"),
        ("row_500m_repeats", "vo2", "500 m repeats", "Anaerobic power repeats"),
        ("row_technique_drills", "easy", "Rowing technique", "Catch and drive drills"),
        ("row_steady_state_3x10", "threshold", "3×10 min threshold", "Threshold blocks"),
        ("row_paddle_easy", "easy", "Easy paddle", "Recovery row"),
        ("row_race_pace_4x2", "race_pace", "Race pace 4×2 min", "2K race pace practice"),
        ("row_strength_endurance", "tempo", "Strength endurance row", "High-drag steady row"),
        ("row_30_30s", "vo2", "Row 30/30s", "Micro-intervals on erg"),
        ("row_cooldown_only", "easy", "Short recovery row", "Very easy recovery"),
    ]
    for id_, intent, title, summary in specs:
        st = "intervals" if intent == "vo2" else intent if intent != "race_pace" else "race"
        targets = {"rpe": {"low": 6, "high": 8}} if intent in {"vo2", "threshold", "race_pace"} else {"rpe": {"low": 4, "high": 6}}
        if intent == "vo2":
            main = _repeat_main(intensity="Hard", reps=6, on_min=2, off_min=2, on_targets=targets)
        elif intent == "threshold":
            main = _repeat_main(intensity="Threshold", reps=3, on_min=10, off_min=3, on_targets=targets)
        else:
            main = _steady_main(intensity="Moderate", detail=f"{title}.", targets=targets)
        items.append(_base(id_, ["rowing"], [st], intent, title, summary, ["rowing", "endurance"], main))
    return items


def walking_pack() -> list[dict]:
    items = []
    specs = [
        ("walk_easy_recovery", "easy", "Easy recovery walk", "Active recovery walking"),
        ("walk_brisk_aerobic", "easy", "Brisk aerobic walk", "Moderate walking aerobic"),
        ("walk_hike_long", "long", "Long hike", "Hiking endurance"),
        ("walk_hill_repeats", "hills", "Hill walk repeats", "Uphill walking power"),
        ("walk_ruck_light", "tempo", "Light ruck walk", "Loaded walking"),
        ("walk_nordic_poles", "easy", "Nordic walking", "Pole walking aerobic"),
        ("walk_treadmill_incline", "tempo", "Incline treadmill walk", "Incline walking aerobic"),
        ("walk_post_meal", "easy", "Post-meal walk", "Glycemic recovery walk"),
        ("walk_ultra_hike", "long", "Ultra hike", "Ultra hiking time-on-feet"),
        ("walk_snow_shoe", "easy", "Snowshoe easy", "Winter aerobic walking"),
    ]
    for id_, intent, title, summary in specs:
        st = "long" if intent == "long" else "hills" if intent == "hills" else "easy" if intent == "easy" else "tempo"
        main = _steady_main(intensity="Easy-moderate", detail=f"{title} for {{main_min}} min.", targets={"rpe": {"low": 4, "high": 6}})
        items.append(_base(id_, ["walking"], [st], intent, title, summary, ["aerobic_base", "walking"], main))
    return items


def cross_training_pack() -> list[dict]:
    items = []
    specs = [
        ("xt_elliptical_easy", "easy", "Elliptical easy", "Low-impact aerobic"),
        ("xt_stair_climber", "tempo", "Stair climber tempo", "Vertical aerobic load"),
        ("xt_pool_running", "easy", "Pool running", "Deep-water running"),
        ("xt_skate_ski", "tempo", "Skate ski simulation", "Winter cross-training"),
        ("xt_hiking_strength", "hills", "Hike with pack", "Loaded hiking"),
        ("xt_soccer_easy", "cross_training", "Easy football", "Team sport aerobic"),
        ("xt_basketball_shootaround", "cross_training", "Basketball shootaround", "Low-intensity court work"),
        ("xt_ski_erg", "tempo", "SkiErg tempo", "Upper-body aerobic tempo"),
    ]
    for id_, intent, title, summary in specs:
        st = "cross-training" if intent == "cross_training" else intent
        main = _steady_main(intensity="Moderate", detail=f"{title}.", targets={"rpe": {"low": 5, "high": 7}})
        items.append(
            _base(
                id_,
                ["cross_training"],
                [st if st != "cross_training" else "cross-training"],
                intent,
                title,
                summary,
                ["cross-training", "aerobic_base"],
                main,
            )
        )
    return items


def versioned_overrides() -> list[dict]:
    """v2 variants of core templates — same id family, higher version."""
    return [
        {
            **_base(
                "run_threshold_2x10_lthr1",
                ["running"],
                ["threshold"],
                "threshold",
                "Threshold repeats (2×10) v2",
                "Extended recovery variant — 4 min jog between reps",
                ["threshold", "lactate-clearance"],
                _repeat_main(
                    intensity="Threshold (LTHR1)",
                    reps=2,
                    on_min=10,
                    off_min=4,
                    on_targets=THRESHOLD_HR,
                    off_targets={"hr_pct_lthr": {"low": 0.65, "high": 0.75}},
                    detail_intro="v2: longer recovery for better lactate clearance.",
                ),
                version=2,
                priority=22,
            ),
        },
        {
            **_base(
                "bike_sweet_spot_2x20",
                ["cycling"],
                ["threshold", "tempo"],
                "sweet_spot",
                "Sweet spot (2×20) v2",
                "Three-block sweet spot variant for build phase density",
                ["sweet-spot", "ftp"],
                _repeat_main(
                    intensity="Sweet spot",
                    reps=3,
                    on_min=15,
                    off_min=5,
                    on_targets=FTP_SST,
                    detail_intro="v2: three blocks instead of two.",
                ),
                version=2,
                priority=24,
            ),
        },
    ]


def all_packs() -> dict[str, list[dict]]:
    return {
        "running_extended.json": running_pack(),
        "cycling_extended.json": cycling_pack(),
        "swimming_extended.json": swimming_pack(),
        "strength_extended.json": strength_pack(),
        "mobility_extended.json": mobility_pack(),
        "trail_extended.json": trail_pack(),
        "triathlon_extended.json": tri_pack(),
        "rowing.json": rowing_pack(),
        "walking.json": walking_pack(),
        "cross_training.json": cross_training_pack(),
        "versioned_overrides.json": versioned_overrides(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SWL expansion pack JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write files.")
    args = parser.parse_args()

    packs = all_packs()
    all_templates: list[dict] = []
    for name, templates in packs.items():
        report = validate_catalog(templates)
        if not report["valid"]:
            print(f"Validation failed for {name}:")
            for err in report["errors"][:10]:
                print(f"  - {err}")
            return 1
        all_templates.extend(templates)
        print(f"  {name}: {len(templates)} template(s)")

    full_report = validate_catalog(all_templates)
    print(f"\nTotal expansion templates: {full_report['total']}")
    if not full_report["valid"]:
        print("Catalog validation failed.")
        return 1

    if args.dry_run:
        print("Dry run — no files written.")
        return 0

    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    for name, templates in packs.items():
        path = PACKS_DIR / name
        path.write_text(json.dumps({"templates": templates}, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {path}")

    manifest = {
        "library_version": "2.0.0",
        "pack_count": len(packs),
        "expansion_templates": full_report["total"],
        "packs": {name: len(templates) for name, templates in packs.items()},
    }
    (BACKEND_ROOT / "data" / "workout_library" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Wrote manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
