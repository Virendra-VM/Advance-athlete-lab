"""Parse free-text planning notes into coach/season hints."""

from __future__ import annotations

TRAVEL_KEYWORDS = ("travel", "trip", "vacation", "away", "flight", "flying")
MORNING_KEYWORDS = ("morning only", "mornings only", "before work", "early only", "am only")
EVENING_KEYWORDS = ("evening only", "after work", "night only", "pm only")
RECOVERY_KEYWORDS = ("recovery week", "need recovery", "deload", "easy week", "back off")
RACE_KEYWORDS = ("race week", "taper", "a-race", "marathon week")
LIMITED_TIME_KEYWORDS = ("limited time", "busy week", "short on time", "only have")


def parse_planning_notes(notes: str | None) -> dict:
    """Return flags, coach hints, and season-preview warnings from planning notes."""
    text = (notes or "").strip().lower()
    flags: list[str] = []
    hints: list[str] = []
    warnings: list[str] = []

    if not text:
        return {"flags": flags, "hints": hints, "warnings": warnings}

    if any(keyword in text for keyword in TRAVEL_KEYWORDS):
        flags.append("travel")
        hints.append("Athlete flagged travel — keep sessions flexible and bias easy when jet-lagged.")
        warnings.append(
            "Planning notes mention travel — consider lighter volume or movable sessions that week."
        )
    if any(keyword in text for keyword in MORNING_KEYWORDS):
        flags.append("morning_only")
        hints.append("Prefer morning sessions; avoid stacking hard work late in the day.")
    if any(keyword in text for keyword in EVENING_KEYWORDS):
        flags.append("evening_only")
        hints.append("Prefer evening sessions; protect sleep if quality work lands late.")
    if any(keyword in text for keyword in RECOVERY_KEYWORDS):
        flags.append("recovery_requested")
        hints.append("Athlete asked for recovery — cap intensity and trim volume this week.")
        warnings.append("Planning notes request recovery — review upcoming build weeks for a deload.")
    if any(keyword in text for keyword in RACE_KEYWORDS):
        flags.append("race_focus")
        hints.append("Race timing noted — respect taper and do not add surprise load.")
    if any(keyword in text for keyword in LIMITED_TIME_KEYWORDS):
        flags.append("limited_time")
        hints.append("Time is tight — fewer but purposeful sessions beat spreading thin volume.")

    return {"flags": flags, "hints": hints, "warnings": warnings}
