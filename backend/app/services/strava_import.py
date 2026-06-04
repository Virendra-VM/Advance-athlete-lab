from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.config import ACTIVITY_POINTS_DIR, STRAVA_EXPORT_DIR, STRAVA_UPLOAD_DIR
from app.models import Activity, AthleteProfile


def _ensure_fit2gpx_available() -> None:
    try:
        from fit2gpx import StravaConverter  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "fit2gpx is not installed. Use Python 3.11, recreate backend/.venv, "
            "and run: pip install -r requirements.txt"
        ) from exc


def _get_strava_converter():
    from fit2gpx import StravaConverter

    return StravaConverter


def _fit_file_to_dataframes(fit_path: str):
    from app.utils.fit_converter import fit_file_to_dataframes

    return fit_file_to_dataframes(fit_path)

import_status: dict = {
    "running": False,
    "total": 0,
    "processed": 0,
    "imported": 0,
    "skipped": 0,
    "errors": [],
}


def get_import_status() -> dict:
    return dict(import_status)


def _reset_status() -> None:
    import_status.update(
        {
            "running": False,
            "total": 0,
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [],
        }
    )


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {col.lower().replace(" ", "_"): col for col in df.columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _parse_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_elapsed_time(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    try:
        parts = [int(part) for part in parts]
    except ValueError:
        return None
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    return None


def _parse_activity_date(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _normalize_csv_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    renamed.columns = [
        col.strip().lower().replace(" ", "_") for col in renamed.columns
    ]
    return renamed


def _parse_filename_activity_id(filename_value) -> int | None:
    if filename_value is None or (isinstance(filename_value, float) and pd.isna(filename_value)):
        return None
    match = re.search(r"(\d+)\.fit", str(filename_value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _parse_distance_meters(row, df: pd.DataFrame) -> float | None:
    """Parse activity distance in meters from Strava export CSV rows."""
    meters_col = _pick_column(
        df,
        [
            "distance.1",
            "distance_m",
            "total_distance_m",
            "total_distance",
        ],
    )
    if meters_col and pd.notna(row[meters_col]):
        meters = _parse_float(row[meters_col])
        if meters is not None:
            return meters

    distance_col = _pick_column(df, ["distance"])
    if distance_col and pd.notna(row[distance_col]):
        value = _parse_float(row[distance_col])
        if value is None:
            return None
        # Strava bulk export uses kilometers in the primary "Distance" column.
        if value < 500:
            return value * 1000
        return value

    return None


def _build_csv_row_metadata(row, df: pd.DataFrame) -> dict:
    name_col = _pick_column(df, ["activity_name", "name"])
    date_col = _pick_column(df, ["activity_date", "date"])
    elapsed_col = _pick_column(
        df, ["elapsed_time", "moving_time", "activity_time"]
    )
    avg_hr_col = _pick_column(df, ["average_heart_rate", "avg_heart_rate"])
    max_hr_col = _pick_column(df, ["max_heart_rate"])
    sport_col = _pick_column(df, ["activity_type", "sport_type", "type"])

    return {
        "name": str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else None,
        "activity_date": _parse_activity_date(row[date_col]) if date_col else None,
        "distance_m": _parse_distance_meters(row, df),
        "moving_time_s": _parse_elapsed_time(row[elapsed_col])
        if elapsed_col
        else None,
        "average_heartrate": _parse_float(row[avg_hr_col])
        if avg_hr_col and pd.notna(row[avg_hr_col])
        else None,
        "max_heartrate": _parse_float(row[max_hr_col])
        if max_hr_col and pd.notna(row[max_hr_col])
        else None,
        "sport_type": str(row[sport_col]).strip()
        if sport_col and pd.notna(row[sport_col])
        else None,
    }


def load_activities_csv(export_dir: Path) -> dict[int, dict]:
    csv_path = export_dir / "activities.csv"
    if not csv_path.exists():
        return {}

    df = _normalize_csv_columns(pd.read_csv(csv_path))
    id_col = _pick_column(df, ["activity_id", "id"])
    filename_col = _pick_column(df, ["filename"])

    metadata: dict[int, dict] = {}
    for _, row in df.iterrows():
        row_metadata = _build_csv_row_metadata(row, df)

        lookup_ids: set[int] = set()
        if id_col is not None and pd.notna(row[id_col]):
            try:
                lookup_ids.add(int(row[id_col]))
            except (TypeError, ValueError):
                pass

        if filename_col is not None:
            filename_id = _parse_filename_activity_id(row[filename_col])
            if filename_id is not None:
                lookup_ids.add(filename_id)

        for lookup_id in lookup_ids:
            metadata[lookup_id] = row_metadata

    return metadata


def unzip_export_files(export_dir: Path) -> None:
    StravaConverter = _get_strava_converter()
    converter = StravaConverter(dir_in=str(export_dir))
    converter.unzip_activities()


def discover_fit_files(export_dir: Path) -> list[Path]:
    activities_dir = export_dir / "activities"
    if not activities_dir.exists():
        return []
    return sorted(activities_dir.rglob("*.fit"))


def parse_strava_activity_id(fit_path: Path) -> int | None:
    match = re.match(r"^(\d+)", fit_path.stem)
    if not match:
        return None
    return int(match.group(1))


def extract_lap_summary(lap_df: pd.DataFrame) -> dict:
    if lap_df.empty:
        return {
            "distance_m": 0.0,
            "moving_time_s": 0,
            "average_heartrate": None,
            "max_heartrate": None,
            "activity_date": None,
        }

    distance_col = _pick_column(
        lap_df, ["total_distance", "distance", "total_distance_m"]
    )
    elapsed_col = _pick_column(
        lap_df, ["total_elapsed_time", "elapsed_time", "moving_time"]
    )
    avg_hr_col = _pick_column(lap_df, ["average_heart_rate", "avg_heart_rate"])
    max_hr_col = _pick_column(lap_df, ["max_heart_rate"])
    start_col = _pick_column(lap_df, ["start_time", "timestamp"])

    distance_m = (
        _parse_float(lap_df[distance_col].fillna(0).sum()) if distance_col else 0.0
    ) or 0.0
    moving_time_s = (
        int(lap_df[elapsed_col].fillna(0).sum()) if elapsed_col else 0
    )
    max_heartrate = None
    if max_hr_col and lap_df[max_hr_col].notna().any():
        max_heartrate = _parse_float(lap_df[max_hr_col].max())

    average_heartrate = None
    if avg_hr_col and lap_df[avg_hr_col].notna().any():
        if distance_col and distance_m > 0:
            weights = lap_df[distance_col].fillna(0).apply(_parse_float).fillna(0)
            if weights.sum() > 0:
                avg_values = lap_df[avg_hr_col].apply(_parse_float).fillna(0)
                average_heartrate = float((avg_values * weights).sum() / weights.sum())
            else:
                average_heartrate = _parse_float(lap_df[avg_hr_col].dropna().mean())
        else:
            average_heartrate = _parse_float(lap_df[avg_hr_col].dropna().mean())

    activity_date = None
    if start_col:
        parsed = pd.to_datetime(lap_df[start_col], errors="coerce").dropna()
        if not parsed.empty:
            activity_date = parsed.min().to_pydatetime()

    return {
        "distance_m": distance_m,
        "moving_time_s": moving_time_s,
        "average_heartrate": average_heartrate,
        "max_heartrate": max_heartrate,
        "activity_date": activity_date,
    }


def normalize_point_dataframe(point_df: pd.DataFrame) -> pd.DataFrame:
    if point_df.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "heart_rate",
                "cadence",
                "speed",
                "power",
                "altitude",
            ]
        )

    timestamp_col = _pick_column(point_df, ["timestamp", "time", "datetime"])
    heart_rate_col = _pick_column(point_df, ["heart_rate", "heartrate"])
    cadence_col = _pick_column(point_df, ["cadence"])
    speed_col = _pick_column(point_df, ["enhanced_speed", "speed"])
    power_col = _pick_column(point_df, ["power"])
    altitude_col = _pick_column(point_df, ["altitude", "enhanced_altitude"])

    normalized = pd.DataFrame()
    if timestamp_col:
        normalized["timestamp"] = pd.to_datetime(
            point_df[timestamp_col], errors="coerce"
        )
    else:
        normalized["timestamp"] = pd.NaT

    for target, source in [
        ("heart_rate", heart_rate_col),
        ("cadence", cadence_col),
        ("speed", speed_col),
        ("power", power_col),
        ("altitude", altitude_col),
    ]:
        normalized[target] = point_df[source] if source else None

    return normalized.dropna(subset=["timestamp"], how="all")


def write_points_parquet(
    points_df: pd.DataFrame,
    athlete_profile_id: int,
    strava_activity_id: int,
    points_root: Path,
) -> str:
    athlete_dir = points_root / str(athlete_profile_id)
    athlete_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = athlete_dir / f"{strava_activity_id}.parquet"
    points_df.to_parquet(parquet_path, index=False)
    return str(parquet_path.relative_to(points_root.parent))


def merge_summary(
    lap_summary: dict,
    csv_metadata: dict | None,
    strava_activity_id: int,
) -> dict:
    csv_metadata = csv_metadata or {}
    name = csv_metadata.get("name") or f"Activity {strava_activity_id}"
    activity_date = csv_metadata.get("activity_date") or lap_summary.get(
        "activity_date"
    )
    if activity_date is None:
        activity_date = datetime.utcnow()

    return {
        "name": name,
        "activity_date": activity_date,
        "distance_m": csv_metadata.get("distance_m")
        if csv_metadata.get("distance_m") is not None
        else lap_summary["distance_m"],
        "moving_time_s": csv_metadata.get("moving_time_s")
        if csv_metadata.get("moving_time_s") is not None
        else lap_summary["moving_time_s"],
        "average_heartrate": csv_metadata.get("average_heartrate")
        if csv_metadata.get("average_heartrate") is not None
        else lap_summary["average_heartrate"],
        "max_heartrate": csv_metadata.get("max_heartrate")
        if csv_metadata.get("max_heartrate") is not None
        else lap_summary["max_heartrate"],
        "sport_type": csv_metadata.get("sport_type"),
    }


def find_latest_export_dir() -> Path | None:
    upload_root = Path(STRAVA_UPLOAD_DIR).expanduser().resolve()
    if not upload_root.exists():
        return None

    csv_files = list(upload_root.glob("*/extracted/activities.csv"))
    if not csv_files:
        return None

    latest_csv = max(csv_files, key=lambda path: path.stat().st_mtime)
    return latest_csv.parent


def backfill_activity_metadata(
    db: Session,
    athlete_profile_id: int,
    export_dir: Path | None = None,
) -> dict:
    resolved_export_dir = export_dir or find_latest_export_dir()
    if resolved_export_dir is None:
        return {"updated": 0, "message": "No Strava export CSV found to backfill metadata."}

    csv_index = load_activities_csv(resolved_export_dir)
    if not csv_index:
        return {"updated": 0, "message": "activities.csv contained no usable metadata."}

    activities = (
        db.query(Activity)
        .filter(Activity.athlete_profile_id == athlete_profile_id)
        .all()
    )

    updated = 0
    for activity in activities:
        metadata = csv_index.get(activity.strava_activity_id)
        if metadata is None:
            continue

        changed = False
        if metadata.get("name") and activity.name != metadata["name"]:
            activity.name = metadata["name"]
            changed = True
        if metadata.get("sport_type") and activity.sport_type != metadata["sport_type"]:
            activity.sport_type = metadata["sport_type"]
            changed = True
        if metadata.get("distance_m") is not None and activity.distance_m != metadata["distance_m"]:
            activity.distance_m = metadata["distance_m"]
            changed = True

        if changed:
            updated += 1

    if updated:
        db.commit()

    return {
        "updated": updated,
        "message": f"Updated metadata for {updated} activities.",
    }


def validate_export_dir(export_dir: Path) -> None:
    if not export_dir.exists():
        raise FileNotFoundError(f"Export directory does not exist: {export_dir}")
    if not (export_dir / "activities").exists():
        raise FileNotFoundError(
            f"Expected 'activities/' folder inside export directory: {export_dir}"
        )


def find_export_root(base: Path) -> Path:
    if (base / "activities").is_dir():
        return base

    for candidate in sorted(base.rglob("activities")):
        if not candidate.is_dir():
            continue
        parent = candidate.parent
        has_csv = (parent / "activities.csv").exists()
        has_fit_files = any(candidate.glob("*.fit")) or any(candidate.glob("*.fit.gz"))
        if has_csv or has_fit_files or any(candidate.iterdir()):
            return parent

    raise FileNotFoundError(
        "Uploaded zip does not contain a valid Strava export (missing activities/ folder)."
    )


def save_uploaded_zip(file_bytes: bytes, original_filename: str) -> Path:
    from app.config import MAX_STRAVA_UPLOAD_MB, STRAVA_UPLOAD_DIR

    max_bytes = MAX_STRAVA_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(
            f"Upload exceeds {MAX_STRAVA_UPLOAD_MB} MB limit. "
            "Increase MAX_STRAVA_UPLOAD_MB in backend/.env if needed."
        )

    if not original_filename.lower().endswith(".zip"):
        raise ValueError("Upload must be a .zip file from Strava bulk export.")

    upload_root = Path(STRAVA_UPLOAD_DIR).expanduser().resolve()
    upload_root.mkdir(parents=True, exist_ok=True)

    upload_dir = upload_root / uuid.uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = upload_dir / "export.zip"
    zip_path.write_bytes(file_bytes)
    return zip_path


def extract_uploaded_zip(zip_path: Path) -> Path:
    extract_dir = zip_path.parent / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)

    return find_export_root(extract_dir)


def import_single_fit_file(
    db: Session,
    athlete_profile_id: int,
    fit_path: Path,
    strava_activity_id: int,
    csv_metadata: dict | None = None,
    source_fit_file: str | None = None,
) -> Activity | None:
    """Import one FIT file into the database. Returns None if already imported."""
    existing = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.strava_activity_id == strava_activity_id,
        )
        .first()
    )
    if existing is not None:
        return None

    points_root = Path(ACTIVITY_POINTS_DIR).expanduser().resolve()
    points_root.mkdir(parents=True, exist_ok=True)

    lap_df, point_df = _fit_file_to_dataframes(str(fit_path))
    lap_summary = extract_lap_summary(lap_df)
    summary = merge_summary(lap_summary, csv_metadata, strava_activity_id)
    normalized_points = normalize_point_dataframe(point_df)
    points_file_path = None
    if not normalized_points.empty:
        points_file_path = write_points_parquet(
            normalized_points,
            athlete_profile_id,
            strava_activity_id,
            points_root,
        )

    activity = Activity(
        athlete_profile_id=athlete_profile_id,
        strava_activity_id=strava_activity_id,
        name=summary["name"],
        activity_date=summary["activity_date"],
        distance_m=float(summary["distance_m"] or 0.0),
        moving_time_s=int(summary["moving_time_s"] or 0),
        average_heartrate=summary["average_heartrate"],
        max_heartrate=summary["max_heartrate"],
        sport_type=summary["sport_type"],
        points_file_path=points_file_path,
        source_fit_file=source_fit_file or fit_path.name,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def run_import(
    db: Session,
    athlete_profile_id: int,
    export_dir: Path | None = None,
) -> None:
    profile = (
        db.query(AthleteProfile).filter(AthleteProfile.id == athlete_profile_id).first()
    )
    if profile is None:
        raise ValueError(f"Athlete profile {athlete_profile_id} not found.")

    if export_dir is None:
        if not STRAVA_EXPORT_DIR:
            raise ValueError(
                "No export directory provided and STRAVA_EXPORT_DIR is not configured."
            )
        resolved_export_dir = Path(STRAVA_EXPORT_DIR).expanduser().resolve()
    else:
        resolved_export_dir = Path(export_dir).expanduser().resolve()
    points_root = Path(ACTIVITY_POINTS_DIR).expanduser().resolve()
    points_root.mkdir(parents=True, exist_ok=True)

    validate_export_dir(resolved_export_dir)
    _ensure_fit2gpx_available()

    import_status.update(
        {
            "running": True,
            "total": 0,
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": [],
        }
    )

    try:
        unzip_export_files(resolved_export_dir)
        csv_index = load_activities_csv(resolved_export_dir)
        fit_files = discover_fit_files(resolved_export_dir)
        import_status["total"] = len(fit_files)

        existing_ids = {
            row.strava_activity_id
            for row in db.query(Activity.strava_activity_id)
            .filter(Activity.athlete_profile_id == athlete_profile_id)
            .all()
        }

        for fit_path in fit_files:
            import_status["processed"] += 1
            strava_activity_id = parse_strava_activity_id(fit_path)
            if strava_activity_id is None:
                import_status["errors"].append(
                    f"Could not parse activity id from {fit_path.name}"
                )
                continue

            if strava_activity_id in existing_ids:
                import_status["skipped"] += 1
                continue

            try:
                activity = import_single_fit_file(
                    db,
                    athlete_profile_id,
                    fit_path,
                    strava_activity_id,
                    csv_metadata=csv_index.get(strava_activity_id),
                    source_fit_file=fit_path.name,
                )
                if activity is None:
                    import_status["skipped"] += 1
                    continue
                existing_ids.add(strava_activity_id)
                import_status["imported"] += 1
            except Exception as exc:
                db.rollback()
                import_status["errors"].append(
                    f"{fit_path.name}: {exc}"
                )

        backfill_activity_metadata(db, athlete_profile_id, export_dir=resolved_export_dir)
    finally:
        import_status["running"] = False


def run_import_in_background(
    athlete_profile_id: int,
    export_dir: Path | None = None,
) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        run_import(db, athlete_profile_id, export_dir=export_dir)
    except Exception as exc:
        import_status["errors"].append(str(exc))
        import_status["running"] = False
    finally:
        db.close()


def run_upload_and_import_in_background(
    athlete_profile_id: int,
    zip_path: Path,
) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        export_dir = extract_uploaded_zip(zip_path)
        run_import(db, athlete_profile_id, export_dir=export_dir)
    except Exception as exc:
        import_status["errors"].append(str(exc))
    finally:
        import_status["running"] = False
        db.close()
