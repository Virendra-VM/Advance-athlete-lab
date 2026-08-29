from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.config import ACTIVITY_POINTS_DIR
from app.models import Activity

FIELD_MAP = {
    "speed_mps": "speed",
    "altitude_m": "altitude",
    "heart_rate": "heart_rate",
    "cadence": "cadence",
    "power": "power",
}

MAX_POINTS = 3000


def _resolve_parquet_path(activity: Activity) -> Path | None:
    if activity.points_file_path:
        candidate = Path(ACTIVITY_POINTS_DIR).parent / activity.points_file_path
        if candidate.exists():
            return candidate

    external_id = activity.external_activity_id or (
        str(activity.strava_activity_id) if activity.strava_activity_id is not None else None
    )
    provider = activity.provider or "strava"
    if external_id:
        provider_path = (
            Path(ACTIVITY_POINTS_DIR)
            / str(activity.athlete_profile_id)
            / provider
            / f"{external_id}.parquet"
        )
        if provider_path.exists():
            return provider_path

        legacy = (
            Path(ACTIVITY_POINTS_DIR)
            / str(activity.athlete_profile_id)
            / f"{external_id}.parquet"
        )
        if legacy.exists():
            return legacy

    return None


def _build_points_dataframe(parquet_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()

    df = df.sort_values("timestamp").reset_index(drop=True)
    start = df["timestamp"].iloc[0]
    df["elapsed_s"] = (df["timestamp"] - start).dt.total_seconds()

    distance_values = [0.0]
    for index in range(1, len(df)):
        delta_t = df["elapsed_s"].iloc[index] - df["elapsed_s"].iloc[index - 1]
        speed = df["speed"].iloc[index - 1] if "speed" in df.columns else 0.0
        speed = float(speed) if pd.notna(speed) else 0.0
        distance_values.append(distance_values[-1] + max(speed, 0.0) * max(delta_t, 0.0))
    df["distance_m"] = distance_values
    return df


def load_activity_points(db: Session, activity_id: int) -> dict:
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if activity is None:
        return {"found": False}

    empty_payload = {
        "found": True,
        "activity_id": activity.id,
        "has_points": False,
        "metrics": [],
        "points": [],
    }

    parquet_path = _resolve_parquet_path(activity)
    if parquet_path is None:
        return empty_payload

    df = _build_points_dataframe(parquet_path)
    if df.empty:
        return empty_payload

    metrics = [
        api_key
        for api_key, column in FIELD_MAP.items()
        if column in df.columns and df[column].notna().any()
    ]

    step = max(1, len(df) // MAX_POINTS)
    sampled = df.iloc[::step]
    points: list[dict] = []

    for _, row in sampled.iterrows():
        point = {
            "elapsed_s": round(float(row["elapsed_s"]), 1),
            "distance_m": round(float(row["distance_m"]), 1),
        }
        for api_key, column in FIELD_MAP.items():
            value = row.get(column)
            if pd.notna(value):
                point[api_key] = round(float(value), 3)

        speed = point.get("speed_mps")
        if speed and speed > 0:
            point["pace_min_per_km"] = round(1000 / (speed * 60), 2)

        points.append(point)

    if any(point.get("pace_min_per_km") for point in points):
        metrics.append("pace_min_per_km")

    return {
        "found": True,
        "activity_id": activity.id,
        "has_points": len(points) > 0,
        "metrics": metrics,
        "points": points,
    }
