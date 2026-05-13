"""
Data cleaning module.

Responsibilities:
  - Load and normalise the patient appointment calendar (CSV)
  - Load and parse the weekly admin shift plan (Excel, wide format)
  - Merge both into a single utilization table aligned on date + time slot
"""

import logging

import pandas as pd

from src.config import (
    CALENDAR_FILE,
    SHIFTPLAN_FILE,
    OVERLOAD_THRESHOLD,
    UNDERUTIL_THRESHOLD,
    DAY_LABELS,
)

logger = logging.getLogger(__name__)

# Date string → actual date value used in the shift plan Excel
_DATE_KEYS = {
    "25.08": "2025-08-25",
    "26.08": "2025-08-26",
    "27.08": "2025-08-27",
    "28.08": "2025-08-28",
    "29.08": "2025-08-29",
}


def _normalise_time(raw: str) -> str:
    """Convert any time variant to clean 'HH:MM' string.

    Handles:
      '0 days 07:00:00'  (pandas timedelta export format)
      '07:40:00'         (standard time string)
      '07:40'            (already clean)
    """
    s = str(raw).strip()
    # Extract HH:MM from anywhere in the string
    import re

    match = re.search(r"(\d{1,2}:\d{2})", s)
    if match:
        parts = match.group(1).split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"
    return s


def load_calendar() -> pd.DataFrame:
    """Load patient calendar and return deduplicated booked slots.

    Cleaning applied:
      1. Normalise 'zeit' column to HH:MM
      2. Keep only booked slots (zellebelegt == 'J')
      3. Deduplicate on appointment ID — multi-treatment rows count as one visit
    """
    df = pd.read_csv(CALENDAR_FILE, low_memory=False)
    df["time"] = df["zeit"].apply(_normalise_time)

    booked = df[df["zellebelegt"] == "J"].copy()

    # Same appointment ID at the same time = one patient visit (not two)
    booked = booked.drop_duplicates(
        subset=["eindeutige_identnummer_des_termins", "datum", "time"]
    )

    logger.info(
        "Calendar: %d booked rows after deduplication (%d raw rows read)",
        len(booked),
        len(df),
    )
    return booked[["datum", "time"]].rename(columns={"datum": "date"})


def patients_per_slot(calendar: pd.DataFrame) -> pd.DataFrame:
    """Aggregate calendar to one row per (date, time) with patient count."""
    return calendar.groupby(["date", "time"]).size().reset_index(name="patients_booked")


def _map_admin_columns(raw: pd.DataFrame) -> dict:
    """Scan the shift plan header rows and return {col_index: date_string}.

    Layout:
      row 1 → day names ('Montag 25.08', 'Dienstag 26.08' …)
      row 2 → admin labels ('Admin 1', 'Admin 2', 'Azubi' …)
      row 3+ → time slots with shift codes (A1 / B1 / Pause / NaN)
    """
    day_row = raw.iloc[1].tolist()
    admin_row = raw.iloc[2].tolist()

    col_map = {}
    current_date = None

    for col_idx, (day_cell, admin_cell) in enumerate(zip(day_row, admin_row)):
        # Update current date when we hit a new day header
        if pd.notna(day_cell) and isinstance(day_cell, str):
            for key, date_val in _DATE_KEYS.items():
                if key in day_cell:
                    current_date = date_val
                    break
        # Record this column if it belongs to a day and has an admin label
        if current_date and pd.notna(admin_cell):
            label = str(admin_cell).strip()
            if label not in ("#", "nan", ""):
                col_map[col_idx] = current_date

    return col_map


def load_shiftplan() -> pd.DataFrame:
    """Parse the wide-format Excel shift plan to long-format admin counts.

    An admin is counted as available when their cell is NOT NaN and NOT 'Pause'.
    Returns one row per (date, time) with the number of available admins.
    """
    raw = pd.read_excel(SHIFTPLAN_FILE, header=None)
    col_map = _map_admin_columns(raw)

    records = []
    for _, row in raw.iloc[3:].iterrows():
        raw_time = str(row.iloc[0]).strip()
        time_clean = _normalise_time(raw_time)

        # Skip non-time rows (e.g. empty lines at bottom)
        if ":" not in time_clean:
            continue

        day_counts: dict = {}
        for col_idx, date_str in col_map.items():
            val = row.iloc[col_idx]
            is_active = pd.notna(val) and str(val).strip().upper() != "PAUSE"
            if is_active:
                day_counts[date_str] = day_counts.get(date_str, 0) + 1

        for date_str, count in day_counts.items():
            records.append(
                {"date": date_str, "time": time_clean, "admins_available": count}
            )

    result = (
        pd.DataFrame(records)
        .groupby(["date", "time"], as_index=False)["admins_available"]
        .sum()
    )
    logger.info("Shift plan: %d admin schedule slots parsed", len(result))
    return result


def _classify(ratio) -> str:
    """Label a utilization ratio as Overloaded, Normal, Underutilised, or No Coverage."""
    if pd.isna(ratio):
        return "No Coverage"
    if ratio > OVERLOAD_THRESHOLD:
        return "Overloaded"
    if ratio < UNDERUTIL_THRESHOLD:
        return "Underutilised"
    return "Normal"


def build_merged(patients: pd.DataFrame, admins: pd.DataFrame) -> pd.DataFrame:
    """Outer-join patients and admins; add utilization ratio and status label."""
    merged = patients.merge(admins, on=["date", "time"], how="outer")
    merged["patients_booked"] = merged["patients_booked"].fillna(0).astype(int)
    merged["admins_available"] = merged["admins_available"].fillna(0).astype(int)

    # Guard against divide-by-zero → None signals "no admin coverage"
    merged["utilization"] = merged.apply(
        lambda r: (
            round(r.patients_booked / r.admins_available, 2)
            if r.admins_available > 0
            else None
        ),
        axis=1,
    )
    merged["status"] = merged["utilization"].apply(_classify)

    logger.info("Merged dataset: %d rows", len(merged))
    return merged.sort_values(["date", "time"]).reset_index(drop=True)
