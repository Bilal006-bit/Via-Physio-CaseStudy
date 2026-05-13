"""
Reception Utilization Analysis
================================
Via Physiotherapy — Case Study | Bilal Ali

Pipeline:
  1. Load & clean calendar data    (patient appointments)
  2. Load & parse shift plan       (admin schedules)
  3. Merge on date + time slot
  4. Calculate utilization ratio   = patients / admins
  5. Identify overloaded / free slots
  6. Visualise: heatmap + bar chart
  7. Export: merged CSV + weekly report CSV

Run:
    python analysis.py
"""

import sys
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from pathlib import Path

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR   = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

CALENDAR_FILE  = DATA_DIR / "Calendar_Data_RAW.csv"
SHIFTPLAN_FILE = DATA_DIR / "Shiftplan - Admins .xlsx"

# ── Thresholds ─────────────────────────────────────────────────────────────────
OVERLOAD_THRESHOLD    = 2.0   # ratio >= this → overloaded
UNDERUTIL_THRESHOLD   = 0.5   # ratio <= this → free / underutilised

# Day label mapping (date → short name)
DAY_LABELS = {
    "2025-08-25": "Mon 25.08",
    "2025-08-26": "Tue 26.08",
    "2025-08-27": "Wed 27.08",
    "2025-08-28": "Thu 28.08",
    "2025-08-29": "Fri 29.08",
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CLEAN CALENDAR DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_calendar(path: Path) -> pd.DataFrame:
    """
    Load patient appointment calendar and return one clean row per
    booked appointment slot (zellebelegt == 'J').

    Cleaning steps applied:
      - Normalise time format from "0 days 07:00:00" → "07:00"
      - Keep only booked slots (zellebelegt == 'J')
      - Deduplicate on appointment ID + date + time
        (same appointment can appear twice for multi-treatment slots)
    """
    df = pd.read_csv(path, low_memory=False)

    # ── Fix time format: "0 days 07:00:00" → "07:00" ──────────────────────────
    df["time_clean"] = (
        df["zeit"]
        .astype(str)
        .str.extract(r"(\d+:\d+):\d+")[0]   # grab HH:MM, drop seconds
        .str.strip()
    )

    # ── Keep only booked patient slots ────────────────────────────────────────
    booked = df[df["zellebelegt"] == "J"].copy()

    # ── Deduplicate: same appointment ID + same date + same time = 1 patient ──
    # (Multi-treatment rows share the same eindeutige_identnummer_des_termins)
    booked = booked.drop_duplicates(
        subset=["eindeutige_identnummer_des_termins", "datum", "time_clean"]
    )

    # ── Keep only the columns we need ─────────────────────────────────────────
    result = booked[["datum", "time_clean"]].copy()
    result.columns = ["date", "time"]

    return result


def patients_per_slot(calendar_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate to: one row per (date, time) with count of booked patients.
    """
    agg = (
        calendar_df
        .groupby(["date", "time"])
        .size()
        .reset_index(name="patients_booked")
    )
    return agg


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PARSE SHIFT PLAN
# ══════════════════════════════════════════════════════════════════════════════

def load_shiftplan(path: Path) -> pd.DataFrame:
    """
    Parse the wide-format Excel shift plan into a long-format DataFrame:
        date | time | admins_available

    The raw file layout:
        Row 0: KW header + day names (e.g. "Montag 25.08")
        Row 1: column labels (Admin 1, Admin 2, Azubi …)
        Row 2+: time slots (07:40:00 … 20:20:00) with codes A1 / B1 / Pause / NaN

    Active codes: any non-null value that is NOT "Pause" → admin is available.
    """
    raw = pd.read_excel(path, header=None)

    # ── Extract day names and their column positions ───────────────────────────
    # Row 1: "Montag 25.08", "Dienstag 26.08", etc. (row 0 is the "P1" label row)
    # Row 2: "Admin 1", "Admin 2", "Azubi", etc.
    # Row 3+: time slots with shift codes
    day_row   = raw.iloc[1].tolist()
    admin_row = raw.iloc[2].tolist()

    # Map each admin column → (date_str, admin_label)
    # We scan row 0 for day headers; each day block spans 3-4 columns
    col_map = {}           # col_index → date string "2025-08-25"
    current_date = None

    date_lookup = {
        "25.08": "2025-08-25",
        "26.08": "2025-08-26",
        "27.08": "2025-08-27",
        "28.08": "2025-08-28",
        "29.08": "2025-08-29",
    }

    for col_idx, cell in enumerate(day_row):
        if pd.notna(cell) and isinstance(cell, str):
            for key, val in date_lookup.items():
                if key in cell:
                    current_date = val
                    break
        if current_date and pd.notna(admin_row[col_idx]):
            label = str(admin_row[col_idx]).strip()
            if label not in ("#", "nan", ""):
                col_map[col_idx] = current_date

    # ── Extract time slots (rows 3 onwards, column 0) ─────────────────────────
    time_rows = raw.iloc[3:].copy()
    time_rows = time_rows[time_rows.iloc[:, 0].notna()]    # drop empty rows

    records = []
    for _, row in time_rows.iterrows():
        raw_time = str(row.iloc[0]).strip()

        # Normalise time to HH:MM
        if len(raw_time) == 8 and raw_time[2] == ":":     # "07:40:00"
            time_clean = raw_time[:5]
        elif len(raw_time) == 5 and raw_time[2] == ":":   # "07:40"
            time_clean = raw_time
        else:
            continue   # skip malformed rows

        # Count active admins for each day at this time
        day_counts = {}
        for col_idx, date_str in col_map.items():
            val = row.iloc[col_idx]
            if pd.notna(val) and str(val).strip().upper() != "PAUSE":
                day_counts[date_str] = day_counts.get(date_str, 0) + 1

        for date_str, count in day_counts.items():
            records.append({
                "date":              date_str,
                "time":              time_clean,
                "admins_available":  count,
            })

    result = pd.DataFrame(records)

    # Sum per (date, time) in case of overlapping column groups
    result = (
        result
        .groupby(["date", "time"], as_index=False)["admins_available"]
        .sum()
    )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — MERGE + CALCULATE UTILIZATION
# ══════════════════════════════════════════════════════════════════════════════

def build_merged(patients: pd.DataFrame, admins: pd.DataFrame) -> pd.DataFrame:
    """
    Outer-join patients and admins on (date, time).
    Calculate utilization ratio and classify each slot.
    """
    merged = patients.merge(admins, on=["date", "time"], how="outer")

    merged["patients_booked"]  = merged["patients_booked"].fillna(0).astype(int)
    merged["admins_available"] = merged["admins_available"].fillna(0).astype(int)

    # Utilization ratio — guard against divide-by-zero
    def safe_ratio(row):
        if row["admins_available"] == 0:
            return None    # no coverage — flagged separately
        return round(row["patients_booked"] / row["admins_available"], 2)

    merged["utilization"] = merged.apply(safe_ratio, axis=1)

    # Classification
    def classify(row):
        if pd.isna(row["utilization"]):
            return "No Coverage"
        elif row["utilization"] >= OVERLOAD_THRESHOLD:
            return "Overloaded"
        elif row["utilization"] <= UNDERUTIL_THRESHOLD:
            return "Underutilised"
        else:
            return "Balanced"

    merged["status"] = merged.apply(classify, axis=1)
    merged = merged.sort_values(["date", "time"]).reset_index(drop=True)

    return merged


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — ANALYSIS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(merged: pd.DataFrame) -> dict:
    """
    Compute daily averages, weekly summary, overloaded + underutilised slots.
    Returns a dict of results for printing and reporting.
    """
    valid = merged[merged["utilization"].notna()].copy()

    # Daily averages
    daily_avg = (
        valid.groupby("date")["utilization"]
        .mean()
        .round(2)
        .reset_index()
    )
    daily_avg["day"] = daily_avg["date"].map(DAY_LABELS)

    # Weekly average
    weekly_avg = round(valid["utilization"].mean(), 2)

    # Overloaded slots
    overloaded = (
        valid[valid["status"] == "Overloaded"]
        [["date", "time", "patients_booked", "admins_available", "utilization"]]
        .sort_values("utilization", ascending=False)
    )

    # Underutilised slots (admins present, few patients)
    free = (
        valid[
            (valid["status"] == "Underutilised") &
            (valid["admins_available"] > 0)
        ]
        [["date", "time", "patients_booked", "admins_available", "utilization"]]
        .sort_values("utilization")
    )

    # No-coverage slots
    no_cover = merged[merged["status"] == "No Coverage"][["date", "time"]]

    # Status distribution
    status_counts = merged["status"].value_counts()

    # Top-3 busiest periods (highest utilization)
    top3 = valid.nlargest(3, "utilization")[
        ["date", "time", "patients_booked", "admins_available", "utilization"]
    ]

    # % of slots by status
    total_slots = len(merged)
    pct = {
        k: f"{round(v/total_slots*100, 1)}%"
        for k, v in status_counts.items()
    }

    return {
        "daily_avg":    daily_avg,
        "weekly_avg":   weekly_avg,
        "overloaded":   overloaded,
        "free":         free,
        "no_cover":     no_cover,
        "status_counts": status_counts,
        "top3":         top3,
        "pct":          pct,
        "total_slots":  total_slots,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — VISUALIZATIONS
# ══════════════════════════════════════════════════════════════════════════════

def plot_heatmap(merged: pd.DataFrame) -> None:
    """
    Heatmap: time slots (rows) × days (columns), coloured by utilization ratio.
    Red = overloaded, white = balanced, blue = underutilised.
    """
    pivot = merged.pivot_table(
        index="time",
        columns="date",
        values="utilization",
        aggfunc="mean"
    )

    # Rename columns to readable day labels
    pivot.columns = [DAY_LABELS.get(c, c) for c in pivot.columns]

    # Sort time index chronologically
    pivot = pivot.sort_index()

    fig, ax = plt.subplots(figsize=(10, 12))

    # Diverging colour map: blue=low, white=1.0, red=high
    cmap = sns.diverging_palette(220, 10, as_cmap=True)

    sns.heatmap(
        pivot,
        ax=ax,
        cmap=cmap,
        center=1.0,
        vmin=0,
        vmax=3,
        annot=True,
        fmt=".1f",
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "Utilization Ratio (patients ÷ admins)"},
    )

    ax.set_title(
        "Reception Utilization Heatmap\nVia Physiotherapy — KW 35 (25–29 Aug 2025)",
        fontsize=14,
        fontweight="bold",
        pad=16,
    )
    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("Time Slot", fontsize=11)
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)

    plt.tight_layout()
    out = OUTPUT_DIR / "heatmap.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Heatmap saved → {out.name}")


def plot_daily_bar(results: dict) -> None:
    """
    Bar chart: average utilization ratio per day.
    Bars coloured by level (green=ok, orange=watch, red=high).
    """
    daily = results["daily_avg"].copy()
    daily = daily[daily["day"].notna()].sort_values("date")

    def bar_colour(val):
        if val >= OVERLOAD_THRESHOLD:   return "#e74c3c"
        elif val >= 1.2:                return "#e67e22"
        elif val <= UNDERUTIL_THRESHOLD: return "#3498db"
        else:                           return "#2ecc71"

    colours = [bar_colour(v) for v in daily["utilization"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(daily["day"], daily["utilization"], color=colours, width=0.5, edgecolor="white")

    # Add value labels on bars
    for bar, val in zip(bars, daily["utilization"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.03,
            f"{val:.2f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold"
        )

    ax.axhline(y=OVERLOAD_THRESHOLD,  color="#e74c3c", linestyle="--",
               linewidth=1.2, label=f"Overload threshold ({OVERLOAD_THRESHOLD})")
    ax.axhline(y=UNDERUTIL_THRESHOLD, color="#3498db", linestyle="--",
               linewidth=1.2, label=f"Underutil. threshold ({UNDERUTIL_THRESHOLD})")

    ax.set_title(
        "Average Daily Utilization Ratio\nVia Physiotherapy — KW 35",
        fontsize=13, fontweight="bold"
    )
    ax.set_ylabel("Avg Utilization (patients ÷ admins)", fontsize=10)
    ax.set_ylim(0, max(daily["utilization"].max() * 1.25, OVERLOAD_THRESHOLD * 1.2))
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out = OUTPUT_DIR / "daily_bar.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Bar chart saved → {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def export_outputs(merged: pd.DataFrame, results: dict) -> None:
    """Save merged dataset and weekly report CSV."""

    # Merged utilization data
    merged_out = OUTPUT_DIR / "merged_utilization.csv"
    merged.to_csv(merged_out, index=False)
    print(f"  ✓ Merged data saved → {merged_out.name}")

    # Weekly report
    report_rows = []
    for _, row in results["daily_avg"].iterrows():
        report_rows.append({
            "day":                  row["day"],
            "date":                 row["date"],
            "avg_utilization":      row["utilization"],
            "status":               (
                "Overloaded" if row["utilization"] >= OVERLOAD_THRESHOLD
                else "Watch" if row["utilization"] >= 1.2
                else "Balanced"
            ),
        })

    # Add bonus summary rows
    report_df = pd.DataFrame(report_rows)
    report_out = OUTPUT_DIR / "weekly_report.csv"
    report_df.to_csv(report_out, index=False)
    print(f"  ✓ Weekly report saved → {report_out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — PRINT REPORT TO TERMINAL
# ══════════════════════════════════════════════════════════════════════════════

W = 60

def _rule(c="─"): print(c * W)

def print_report(results: dict) -> None:
    print("\n" + "╔" + "═"*(W-2) + "╗")
    print("║" + "  RECEPTION UTILIZATION REPORT".center(W-2) + "║")
    print("║" + "  Via Physiotherapy · KW 35 · Aug 2025".center(W-2) + "║")
    print("╚" + "═"*(W-2) + "╝")

    # ── Overview ──────────────────────────────────────────────────────────────
    print("\n  OVERVIEW")
    _rule()
    print(f"    Weekly avg utilization:    {results['weekly_avg']}")
    print(f"    Total 20-min slots:        {results['total_slots']}")
    for status, pct in results["pct"].items():
        print(f"    {status:<25} {pct}")

    # ── Daily averages ────────────────────────────────────────────────────────
    print("\n  DAILY AVERAGES")
    _rule()
    for _, row in results["daily_avg"].iterrows():
        flag = "  ← HIGH" if row["utilization"] >= OVERLOAD_THRESHOLD else ""
        print(f"    {str(row['day']):<16}  {row['utilization']:.2f}{flag}")

    # ── Top-3 overloaded ──────────────────────────────────────────────────────
    print("\n  TOP-3 BUSIEST SLOTS (overloaded)")
    _rule()
    for _, row in results["top3"].iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        print(f"    {day}  {row['time']}  →  "
              f"{int(row['patients_booked'])} patients / "
              f"{int(row['admins_available'])} admin  "
              f"= ratio {row['utilization']:.1f}")

    # ── Free windows ──────────────────────────────────────────────────────────
    print("\n  TOP FREE WINDOWS (admin tasks recommended)")
    _rule()
    for _, row in results["free"].head(5).iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        print(f"    {day}  {row['time']}  →  "
              f"{int(row['patients_booked'])} patients / "
              f"{int(row['admins_available'])} admin  "
              f"= ratio {row['utilization']:.2f}")

    print()
    _rule("═")
    print("  Output files: output/heatmap.png · daily_bar.png · "
          "merged_utilization.csv · weekly_report.csv")
    _rule("═")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "─"*W)
    print("  RECEPTION UTILIZATION ANALYSIS  |  Starting...")
    print("─"*W)

    print("\n  STEP 1 — Loading & cleaning calendar data...")
    calendar_df = load_calendar(CALENDAR_FILE)
    patients    = patients_per_slot(calendar_df)
    print(f"  ✓ {len(calendar_df):,} booked appointment rows (after dedup)")
    print(f"  ✓ {len(patients):,} unique date+time slots with patients")

    print("\n  STEP 2 — Parsing shift plan...")
    admins = load_shiftplan(SHIFTPLAN_FILE)
    print(f"  ✓ {len(admins):,} admin schedule slots parsed")

    print("\n  STEP 3 — Merging & calculating utilization...")
    merged = build_merged(patients, admins)
    print(f"  ✓ Merged dataset: {len(merged):,} rows")

    print("\n  STEP 4 — Running analysis...")
    results = run_analysis(merged)

    print("\n  STEP 5 — Generating visualizations...")
    plot_heatmap(merged)
    plot_daily_bar(results)

    print("\n  STEP 6 — Exporting outputs...")
    export_outputs(merged, results)

    print_report(results)


if __name__ == "__main__":
    main()
