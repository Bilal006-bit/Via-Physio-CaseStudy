"""
Reception Utilization Analysis — Via Physiotherapy
====================================================
Combines patient appointment calendar with admin shift schedules to calculate
reception workload per 20-minute slot across Calendar Week 35.

Usage:
    python run.py

Outputs written to output/:
    merged_utilization.csv   full merged dataset with ratios and status labels
    weekly_report.csv        bonus weekly summary (per-day averages)
    summary_report.html      self-contained interactive report (charts embedded)

Data scope: KW 35 — Mon 25 Aug to Fri 29 Aug 2025 (one week).
Patterns observed should be validated across multiple weeks before
drawing conclusions about recurring behaviour.
"""

import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

from src.analyze import run_analysis
from src.clean import build_merged, load_calendar, load_shiftplan, patients_per_slot
from src.config import DAY_LABELS
from src.export import save_merged, save_weekly_report
from src.report import build_report

W = 60


def _rule(char: str = "─") -> None:
    print(char * W)


def _section(title: str) -> None:
    print(f"\n  {title}")
    _rule()


def print_summary(results: dict) -> None:
    """Print the analysis summary to stdout after the pipeline completes."""
    print()
    print("╔" + "═" * (W - 2) + "╗")
    print("║" + "  RECEPTION UTILIZATION REPORT".center(W - 2) + "║")
    print("║" + "  Via Physiotherapy  ·  KW 35  ·  Aug 2025".center(W - 2) + "║")
    print("╚" + "═" * (W - 2) + "╝")

    # ── Overview ──────────────────────────────────────────────────────────────
    _section("OVERVIEW")
    print(f"    Weekly avg utilization ratio : {results['weekly_avg']}")
    print(f"    Total 20-min slots analysed  : {results['total_slots']}")
    print(f"    Data scope                   : KW 35 only — validate further")
    for status, pct in results["pct"].items():
        print(f"    {status:<26} {pct}%")

    # ── Daily averages ────────────────────────────────────────────────────────
    _section("DAILY AVERAGES")
    for _, row in results["daily_avg"].iterrows():
        flag = "  ← OVERLOADED" if row["utilization"] > 1.0 else ""
        print(f"    {str(row['day']):<16}  {row['utilization']:.2f}{flag}")

    # ── Top-3 busiest ─────────────────────────────────────────────────────────
    _section("TOP-3 BUSIEST SLOTS  (20-min resolution)")
    for _, row in results["top3"].iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        print(
            f"    {day}  {row['time']}  →  "
            f"{int(row['patients_booked'])} patients / "
            f"{int(row['admins_available'])} admin  "
            f"= ratio {row['utilization']:.1f}"
        )

    # ── Free windows ──────────────────────────────────────────────────────────
    _section("FREE WINDOWS  (best candidates for admin task scheduling)")
    for _, row in results["free"].iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        star = "  ★ 2 admins" if int(row["admins_available"]) >= 2 else ""
        print(
            f"    {day}  {row['time']}  →  "
            f"{int(row['patients_booked'])} patients / "
            f"{int(row['admins_available'])} admin  "
            f"= ratio {row['utilization']:.2f}{star}"
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    print()
    _rule("═")
    print("  output/summary_report.html   — open in any browser, charts interactive")
    print("  output/merged_utilization.csv — full dataset, Power BI ready")
    print("  output/weekly_report.csv      — per-day summary")
    _rule("═")
    print()


def main() -> None:
    """Run the full pipeline: clean → analyse → export → build HTML report."""
    _rule()
    print("  RECEPTION UTILIZATION ANALYSIS  |  Starting...")
    _rule()

    logger.info("Step 1 — Loading and cleaning calendar data...")
    calendar = load_calendar()
    patients = patients_per_slot(calendar)

    logger.info("Step 2 — Parsing admin shift plan...")
    admins = load_shiftplan()

    logger.info("Step 3 — Merging and calculating utilization ratios...")
    merged = build_merged(patients, admins)

    logger.info("Step 4 — Running analysis...")
    results = run_analysis(merged)

    logger.info("Step 5 — Exporting CSV outputs...")
    save_merged(merged)
    save_weekly_report(results, results["daily_avg"])

    logger.info("Step 6 — Building interactive HTML report...")
    build_report(merged, results)

    print_summary(results)


if __name__ == "__main__":
    main()
