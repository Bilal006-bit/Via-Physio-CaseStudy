"""
Reception Utilization Analysis — Via Physiotherapy
====================================================
Entry point.  Run with:

    python run.py

Outputs written to output/:
    heatmap.png              required visualisation
    hourly_bar.png           optional hourly pattern chart
    merged_utilization.csv   full merged dataset
    weekly_report.csv        bonus weekly summary
    summary_report.html      self-contained HTML report (charts embedded)
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

from src.clean import load_calendar, patients_per_slot, load_shiftplan, build_merged
from src.analyze import run_analysis
from src.visualize import plot_heatmap, plot_hourly_bar
from src.export import save_merged, save_weekly_report
from src.report import build_report
from src.config import DAY_LABELS


def _rule(char="─", width=60) -> None:
    print(char * width)


def print_summary(results: dict) -> None:
    """Print a formatted summary report to stdout."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + "  RECEPTION UTILIZATION REPORT".center(58) + "║")
    print("║" + "  Via Physiotherapy · KW 35 · Aug 2025".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    print("\n  OVERVIEW")
    _rule()
    print(f"    Weekly avg utilization : {results['weekly_avg']}")
    print(f"    Total 20-min slots     : {results['total_slots']}")
    for status, pct in results["pct"].items():
        print(f"    {status:<22}  {pct}%")

    print("\n  DAILY AVERAGES")
    _rule()
    for _, row in results["daily_avg"].iterrows():
        flag = "  ← OVERLOADED" if row["utilization"] > 1.0 else ""
        print(f"    {str(row['day']):<16}  {row['utilization']:.2f}{flag}")

    print("\n  TOP-3 BUSIEST SLOTS")
    _rule()
    for _, row in results["top3"].iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        print(
            f"    {day}  {row['time']}  → "
            f"{int(row['patients_booked'])} patients / "
            f"{int(row['admins_available'])} admin = ratio {row['utilization']:.1f}"
        )

    print("\n  RECOMMENDED FREE WINDOWS (assign admin tasks here)")
    _rule()
    for _, row in results["free"].iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        print(
            f"    {day}  {row['time']}  → "
            f"{int(row['patients_booked'])} patients / "
            f"{int(row['admins_available'])} admin = ratio {row['utilization']:.2f}"
        )

    print()
    _rule("═")
    print(
        "  Outputs: output/heatmap.png · hourly_bar.png · "
        "merged_utilization.csv · weekly_report.csv"
    )
    _rule("═")
    print()


def main() -> None:
    """Orchestrate the full pipeline end to end."""
    _rule()
    print("  RECEPTION UTILIZATION ANALYSIS  |  Starting...")
    _rule()

    logger.info("Step 1 — Loading and cleaning calendar data...")
    calendar = load_calendar()
    patients = patients_per_slot(calendar)

    logger.info("Step 2 — Parsing admin shift plan...")
    admins = load_shiftplan()

    logger.info("Step 3 — Merging datasets and calculating utilization...")
    merged = build_merged(patients, admins)

    logger.info("Step 4 — Running analysis...")
    results = run_analysis(merged)
    results["daily_avg"] = results.pop("daily_avg")  # ensure key exists

    logger.info("Step 5 — Generating visualizations...")
    plot_heatmap(merged)
    plot_hourly_bar(results["hourly_avg"])

    logger.info("Step 6 — Exporting outputs...")
    save_merged(merged)
    save_weekly_report(results, results["daily_avg"])

    logger.info("Step 7 — Building HTML report...")
    build_report(merged, results)

    print_summary(results)


if __name__ == "__main__":
    main()
