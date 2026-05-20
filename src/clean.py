"""Data cleaning — loads, normalises, and merges calendar + shift plan data."""

import logging
import re

import pandas as pd

from src.config import (
    CALENDAR_FILE,
    OVERLOAD_THRESHOLD,
    SHIFTPLAN_FILE,
    UNDERUTIL_THRESHOLD,
)

logger = logging.getLogger(__name__)

_DATE_KEYS = {
    "25.08": "2025-08-25",
    "26.08": "2025-08-26",
    "27.08": "2025-08-27",
    "28.08": "2025-08-28",
    "29.08": "2025-08-29",
}


def _normalise_time(raw: str) -> str:
    """Extract HH:MM from any time string variant (e.g. '0 days 07:00:00' → '07:00')."""
    match = re.search(r"(\d{1,2}:\d{2})", str(raw))
    if match:
        h, m = match.group(1).split(":")
        return f"{int(h):02d}:{m}"
    return str(raw).strip()


def load_calendar() -> pd.DataFrame:
    """Load booked patient slots, normalise time, and deduplicate by appointment ID.

    Deduplication reason: multi-treatment rows share the same appointment ID
    but each one is still one patient visit at the reception desk.
    """
    df = pd.read_csv(CALENDAR_FILE, low_memory=False)
    df["time"] = df["zeit"].apply(_normalise_time)
    booked = df[df["zellebelegt"] == "J"].drop_duplicates(
        subset=["eindeutige_identnummer_des_termins", "datum", "time"]
    )
    logger.info("Calendar: %d booked rows (%d raw)", len(booked), len(df))
    return booked[["datum", "time"]].rename(columns={"datum": "date"})


def patients_per_slot(calendar: pd.DataFrame) -> pd.DataFrame:
    """Count booked patients per (date, time) slot."""
    return calendar.groupby(["date", "time"]).size().reset_index(name="patients_booked")


def _map_admin_columns(raw: pd.DataFrame) -> dict:
    """Return {col_index: date_string} by scanning the shift plan header rows.

    Row 1 holds day names ('Montag 25.08' …), row 2 holds admin labels.
    """
    col_map, current_date = {}, None
    for col_idx, (day_cell, admin_cell) in enumerate(
        zip(raw.iloc[1].tolist(), raw.iloc[2].tolist())
    ):
        if pd.notna(day_cell) and isinstance(day_cell, str):
            for key, date_val in _DATE_KEYS.items():
                if key in day_cell:
                    current_date = date_val
        if current_date and pd.notna(admin_cell):
            label = str(admin_cell).strip()
            if label not in ("#", "nan", ""):
                col_map[col_idx] = current_date
    return col_map


def load_shiftplan() -> pd.DataFrame:
    """Parse the wide Excel shift plan into long-format (date, time, admins_available).

    A cell counts as active when it is not NaN and not 'Pause'.
    """
    raw = pd.read_excel(SHIFTPLAN_FILE, header=None)
    col_map = _map_admin_columns(raw)
    records = []

    for _, row in raw.iloc[3:].iterrows():
        time = _normalise_time(str(row.iloc[0]))
        if ":" not in time:
            continue
        for col_idx, date_str in col_map.items():
            val = row.iloc[col_idx]
            if pd.notna(val) and str(val).strip().upper() != "PAUSE":
                records.append({"date": date_str, "time": time, "admins_available": 1})

    result = (
        pd.DataFrame(records)
        .groupby(["date", "time"], as_index=False)
        .agg({"admins_available": "sum"})
    )
    logger.info("Shift plan: %d slots parsed", len(result))
    return result


def _classify(ratio) -> str:
    """Label a slot as Overloaded, Normal, Underutilised, or No Coverage."""
    if pd.isna(ratio):
        return "No Coverage"
    if ratio > OVERLOAD_THRESHOLD:
        return "Overloaded"
    if ratio < UNDERUTIL_THRESHOLD:
        return "Underutilised"
    return "Normal"


def build_merged(patients: pd.DataFrame, admins: pd.DataFrame) -> pd.DataFrame:
    """Outer-join patients + admins, compute utilization ratio and status label."""
    merged = patients.merge(admins, on=["date", "time"], how="outer")
    merged["patients_booked"] = merged["patients_booked"].fillna(0).astype(int)
    merged["admins_available"] = merged["admins_available"].fillna(0).astype(int)
    merged["utilization"] = merged.apply(
        lambda r: (
            round(r.patients_booked / r.admins_available, 2)
            if r.admins_available > 0
            else None
        ),
        axis=1,
    )
    merged["status"] = merged["utilization"].apply(_classify)
    logger.info("Merged: %d rows", len(merged))
    return merged.sort_values(["date", "time"]).reset_index(drop=True)
