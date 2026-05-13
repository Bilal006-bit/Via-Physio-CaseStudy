"""
Central configuration — thresholds, paths, and constants.
Change values here; nothing else in the codebase needs to change.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUT_DIR = ROOT_DIR / "output"

CALENDAR_FILE = DATA_DIR / "Calendar_Data_RAW.csv"
SHIFTPLAN_FILE = DATA_DIR / "Shiftplan - Admins .xlsx"

# ── Utilization thresholds ─────────────────────────────────────────────────────
# Based on clinical context: 1 patient per admin per slot = comfortable capacity
OVERLOAD_THRESHOLD = 1.0  # ratio > 1.0  → overloaded
UNDERUTIL_THRESHOLD = 0.5  # ratio < 0.5  → underutilised / free

# ── Day labels (date string → readable label) ──────────────────────────────────
DAY_LABELS = {
    "2025-08-25": "Mon 25.08",
    "2025-08-26": "Tue 26.08",
    "2025-08-27": "Wed 27.08",
    "2025-08-28": "Thu 28.08",
    "2025-08-29": "Fri 29.08",
}
