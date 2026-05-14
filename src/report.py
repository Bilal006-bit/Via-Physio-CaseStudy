"""
HTML report generator.

Builds output/summary_report.html — a fully self-contained file.
Both charts are embedded as base64 data URIs so the file works
with no internet connection, no Python, no extra files.
Anyone with a browser can open it.
"""

import base64
import logging
from pathlib import Path

import pandas as pd

from src.config import DAY_LABELS, OUT_DIR, OVERLOAD_THRESHOLD, UNDERUTIL_THRESHOLD

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _b64_img(path: Path) -> str:
    """Read a PNG and return an inline base64 data URI for <img src=...>."""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{encoded}"


def _badge(status: str) -> str:
    """Return a coloured HTML pill badge for a utilization status label."""
    colours = {
        "Overloaded": ("#e74c3c", "#fff"),
        "Normal": ("#e67e22", "#fff"),
        "Underutilised": ("#27ae60", "#fff"),
        "No Coverage": ("#95a5a6", "#fff"),
    }
    bg, fg = colours.get(status, ("#ccc", "#333"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:600">{status}</span>'
    )


def _rows_to_html(df: pd.DataFrame, cols: list, formatters: dict = None) -> str:
    """Render selected DataFrame columns as HTML <tr> rows."""
    rows = ""
    for _, row in df.iterrows():
        cells = ""
        for col in cols:
            val = row[col]
            if formatters and col in formatters:
                val = formatters[col](val)
            cells += f"<td>{val}</td>"
        rows += f"<tr>{cells}</tr>"
    return rows


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #2c3e50;
    line-height: 1.6;
}
.wrapper { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

/* Header — Via Physio brand colour #23285D */
.report-header {
    background: #23285D;
    color: white;
    padding: 36px 40px;
    border-radius: 12px;
    margin-bottom: 28px;
    border-bottom: 4px solid #F2BD75;
}
.report-header h1 { font-size: 26px; font-weight: 700; margin-bottom: 6px; }
.report-header p  { font-size: 14px; opacity: 0.75; margin-top: 4px; }
.report-header .accent { color: #F2BD75; font-weight: 600; opacity: 1; }

/* Executive summary */
.exec-summary {
    background: #fff;
    border-left: 5px solid #23285D;
    padding: 20px 24px;
    border-radius: 8px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.exec-summary h2 { font-size: 14px; text-transform: uppercase;
                   letter-spacing: .06em; color: #23285D; margin-bottom: 8px; }
.exec-summary p  { font-size: 15px; }

/* KPI cards */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 28px;
}
.kpi-card {
    background: #fff;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.kpi-card .value { font-size: 32px; font-weight: 700; }
.kpi-card .label { font-size: 12px; color: #7f8c8d; margin-top: 4px; text-transform: uppercase; }
.kpi-card.red    { border-top: 4px solid #e74c3c; }
.kpi-card.red .value { color: #e74c3c; }
.kpi-card.amber  { border-top: 4px solid #e67e22; }
.kpi-card.amber .value { color: #e67e22; }
.kpi-card.green  { border-top: 4px solid #27ae60; }
.kpi-card.green .value { color: #27ae60; }
.kpi-card.blue   { border-top: 4px solid #3498db; }
.kpi-card.blue .value { color: #3498db; }

/* Sections */
.section {
    background: #fff;
    border-radius: 10px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.section h2 {
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 6px;
    color: #23285D;
}
.section .subtitle {
    font-size: 13px;
    color: #7f8c8d;
    margin-bottom: 20px;
}
.section img { width: 100%; border-radius: 6px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 12px; }
th {
    background: #f8f9fa;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: #7f8c8d;
    border-bottom: 2px solid #ecf0f1;
}
td { padding: 10px 14px; border-bottom: 1px solid #f0f2f5; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }

/* Daily table color rows */
.row-over td { background: #fdf2f2; }
.row-over:hover td { background: #fae9e9; }
.row-ok td   { background: #f0faf4; }

/* Recommendations */
.rec-list { list-style: none; padding: 0; margin-top: 12px; }
.rec-list li {
    padding: 14px 16px 14px 48px;
    margin-bottom: 10px;
    border-radius: 8px;
    background: #f8f9fa;
    position: relative;
    font-size: 14px;
}
.rec-list li::before {
    content: attr(data-icon);
    position: absolute;
    left: 16px;
    font-size: 18px;
}

/* Scale section — Via gold accent */
.scale-box {
    background: #fffbf2;
    border-left: 4px solid #F2BD75;
    padding: 18px 22px;
    border-radius: 8px;
    font-size: 14px;
    margin-top: 16px;
}
.scale-box strong { color: #23285D; }

/* Footer */
.footer {
    text-align: center;
    font-size: 12px;
    color: #23285D;
    opacity: 0.5;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 2px solid #F2BD75;
}

@media (max-width: 700px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media print {
    body { background: white; }
    .wrapper { padding: 0; }
    .section { box-shadow: none; border: 1px solid #ddd; }
}
"""


# ── HTML builder ──────────────────────────────────────────────────────────────


def build_report(merged: pd.DataFrame, results: dict) -> None:
    """Build and save output/summary_report.html with all charts embedded."""

    # ── Pull key numbers ───────────────────────────────────────────────────────
    valid = merged[merged["utilization"].notna()]
    weekly_avg = round(valid["utilization"].mean(), 2)
    total = len(merged)
    pct_over = round(merged[merged["status"] == "Overloaded"].shape[0] / total * 100, 1)
    pct_free = round(
        merged[merged["status"] == "Underutilised"].shape[0] / total * 100, 1
    )
    no_cover = merged[merged["status"] == "No Coverage"].shape[0]

    daily_avg = results["daily_avg"]
    overloaded = results["overloaded"].head(5)
    free_slots = results["free"].head(5)
    top3 = results["top3"]

    # ── Embed images ───────────────────────────────────────────────────────────
    heatmap_src = _b64_img(OUT_DIR / "heatmap.png")
    hourly_src = _b64_img(OUT_DIR / "hourly_bar.png")

    # ── Daily table rows ───────────────────────────────────────────────────────
    daily_rows = ""
    for _, row in daily_avg.iterrows():
        is_over = row["utilization"] > OVERLOAD_THRESHOLD
        css = "row-over" if is_over else "row-ok"
        flag = _badge("Overloaded") if is_over else _badge("Normal")
        daily_rows += (
            f'<tr class="{css}">'
            f"<td><strong>{row['day']}</strong></td>"
            f"<td>{row['utilization']:.2f}</td>"
            f"<td>{flag}</td>"
            f"</tr>"
        )

    # ── Overloaded slot rows ───────────────────────────────────────────────────
    over_rows = ""
    for _, row in overloaded.iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        over_rows += (
            f"<tr>"
            f"<td>{day}</td><td>{row['time']}</td>"
            f"<td>{int(row['patients_booked'])}</td>"
            f"<td>{int(row['admins_available'])}</td>"
            f"<td><strong>{row['utilization']:.1f}x</strong></td>"
            f"</tr>"
        )

    # ── Free window rows ───────────────────────────────────────────────────────
    free_rows = ""
    for _, row in free_slots.iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        free_rows += (
            f"<tr>"
            f"<td>{day}</td><td>{row['time']}</td>"
            f"<td>{int(row['admins_available'])}</td>"
            f"<td>✅ Schedule admin tasks here</td>"
            f"</tr>"
        )

    # ── Top-3 busiest rows ────────────────────────────────────────────────────
    top3_rows = ""
    for _, row in top3.iterrows():
        day = DAY_LABELS.get(str(row["date"]), row["date"])
        top3_rows += (
            f"<tr>"
            f"<td>{day}</td><td>{row['time']}</td>"
            f"<td>{int(row['patients_booked'])} patients / "
            f"{int(row['admins_available'])} admin</td>"
            f"<td>{_badge('Overloaded')} {row['utilization']:.1f}x</td>"
            f"</tr>"
        )

    # ── Assemble HTML ──────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reception Utilization Report — Via Physiotherapy KW 35</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrapper">

  <!-- HEADER -->
  <div class="report-header">
    <h1>Reception Utilization Analysis</h1>
    <p><span class="accent">Via Physiotherapy</span> &nbsp;·&nbsp; Calendar Week 35 (Mon 25 Aug – Fri 29 Aug 2025)</p>
    <p>Prepared by Bilal Ali</p>
  </div>

  <!-- EXECUTIVE SUMMARY -->
  <div class="exec-summary">
    <h2>Executive Summary</h2>
    <p>
      <strong>{pct_over}% of all 20-minute reception slots are overloaded</strong>
      (more patients arriving than admins can comfortably handle).
      Tuesday is the most critical day, peaking at a ratio of 7.0 during 17:00–18:00,
      meaning a single admin is managing seven concurrent patient interactions.
      The only consistent free windows — where admin capacity is available —
      occur on <strong>Monday 14:20–14:40</strong> (2 admins, 0 patients)
      and <strong>Wednesday 07:40 + 09:40</strong>.
      Immediate action: add a second admin to Tuesday afternoon and
      schedule administrative tasks in the identified free windows.
    </p>
  </div>

  <!-- KPI CARDS -->
  <div class="kpi-grid">
    <div class="kpi-card red">
      <div class="value">{weekly_avg}</div>
      <div class="label">Weekly avg ratio</div>
    </div>
    <div class="kpi-card red">
      <div class="value">{pct_over}%</div>
      <div class="label">Slots overloaded</div>
    </div>
    <div class="kpi-card green">
      <div class="value">{pct_free}%</div>
      <div class="label">Free capacity slots</div>
    </div>
    <div class="kpi-card amber">
      <div class="value">{no_cover}</div>
      <div class="label">No-coverage slots</div>
    </div>
  </div>

  <!-- HEATMAP -->
  <div class="section">
    <h2>Utilization Heatmap — Time Slot × Day</h2>
    <p class="subtitle">
      Each cell = utilization ratio for that 20-minute slot on that day.
      Red = overloaded (ratio &gt; 1.0) &nbsp;|&nbsp;
      Green = free capacity (ratio &lt; 0.5).
    </p>
    <img src="{heatmap_src}" alt="Utilization heatmap">
  </div>

  <!-- HOURLY BAR CHART -->
  <div class="section">
    <h2>Average Utilization by Hour of Day</h2>
    <p class="subtitle">
      Aggregated across all 5 days — shows <em>when during the day</em>
      the clinic is under pressure. Red bars = admin team is stretched;
      green bars = capacity available for extra tasks.
    </p>
    <img src="{hourly_src}" alt="Hourly utilization bar chart">
  </div>

  <!-- DAILY AVERAGES TABLE -->
  <div class="section">
    <h2>Daily Breakdown</h2>
    <p class="subtitle">Average utilization ratio per day with status classification.</p>
    <table>
      <thead>
        <tr><th>Day</th><th>Avg Ratio</th><th>Status</th></tr>
      </thead>
      <tbody>{daily_rows}</tbody>
    </table>
  </div>

  <!-- TOP-3 BUSIEST -->
  <div class="section">
    <h2>Top-3 Busiest Slots</h2>
    <p class="subtitle">
      The highest-load 20-minute windows of the week.
      These are the moments where a second admin would have the most impact.
    </p>
    <table>
      <thead>
        <tr><th>Day</th><th>Time</th><th>Load</th><th>Ratio</th></tr>
      </thead>
      <tbody>{top3_rows}</tbody>
    </table>
  </div>

  <!-- FREE WINDOWS TABLE -->
  <div class="section">
    <h2>Recommended Free Windows</h2>
    <p class="subtitle">
      Slots where admins are present but patient load is low —
      ideal for scheduling administrative tasks (billing, filing, callbacks).
    </p>
    <table>
      <thead>
        <tr><th>Day</th><th>Time</th><th>Admins Available</th><th>Recommendation</th></tr>
      </thead>
      <tbody>{free_rows}</tbody>
    </table>
  </div>

  <!-- OVERLOADED DETAIL -->
  <div class="section">
    <h2>Most Overloaded Slots (Top 5)</h2>
    <p class="subtitle">
      Slots where the ratio is highest — reception is most stretched.
      Consider staggering appointment start times or adding admin cover.
    </p>
    <table>
      <thead>
        <tr><th>Day</th><th>Time</th><th>Patients</th><th>Admins</th><th>Ratio</th></tr>
      </thead>
      <tbody>{over_rows}</tbody>
    </table>
  </div>

  <!-- RECOMMENDATIONS -->
  <div class="section">
    <h2>Recommendations</h2>
    <ul class="rec-list">
      <li data-icon="🔴">
        <strong>Add a second admin on Tuesday afternoons (15:00–19:00).</strong>
        Tuesday has the highest average ratio (3.64) and peaks at 7.0 during 17:00–18:00.
        A single admin cannot manage seven simultaneous arrivals — this is the single
        highest-impact staffing change available.
      </li>
      <li data-icon="📋">
        <strong>Schedule admin tasks in Monday 14:20–14:40 and Wednesday 07:40/09:40.</strong>
        These are the only windows with 2 admins available and zero patient load.
        Billing callbacks, filing, and supply checks should be batched into these windows.
      </li>
      <li data-icon="⏰">
        <strong>Consider staggering appointment start times.</strong>
        The hourly chart shows 09:00–11:00 and 15:00–18:00 as consistently overloaded.
        Offsetting some bookings by 10–20 minutes would flatten the peak load curve.
      </li>
      <li data-icon="📊">
        <strong>Re-run this analysis weekly.</strong>
        The script accepts any date range — running it every Monday morning on the
        prior week's export would surface trends across multiple weeks and catch
        structural staffing gaps before they become chronic.
      </li>
    </ul>
  </div>

  <!-- HOW TO SCALE -->
  <div class="section">
    <h2>Turning This Into a Weekly Ops Routine</h2>
    <div class="scale-box">
      <strong>Right now — no setup needed:</strong> Forward this file to your operations
      manager. It opens in any browser and contains everything: charts, tables,
      recommendations. Nothing to install, nothing to configure.<br><br>
      <strong>Week-by-week tracking:</strong> Export the previous week's calendar data
      every Monday morning and run <code>python run.py</code>. A fresh report is ready
      in seconds. Over time, comparing KW 35 to KW 36 to KW 37 shows whether staffing
      changes are actually working — or whether the overload is structural.<br><br>
      <strong>As Via scales across all four locations:</strong> The pipeline is built to
      extend. Adding a <code>clinic_id</code> field means one run produces a heatmap per
      location. The ops manager can compare Mitte vs. Prenzlauer Berg vs. other sites
      side-by-side — identifying which clinics have the staffing problem and which are
      running efficiently. No code changes required, only data.<br><br>
      <strong>Fully automated (next step):</strong> Once connected to the scheduling
      system's export, the pipeline runs on a timer and emails this report every Monday
      morning automatically. The operations team gets the insights without touching Python.
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    Reception Utilization Analysis &nbsp;·&nbsp; Via Physiotherapy KW 35 &nbsp;·&nbsp;
    Bilal Ali &nbsp;·&nbsp; Bilalalidaper@gmail.com
  </div>

</div>
</body>
</html>"""

    out = OUT_DIR / "summary_report.html"
    out.write_text(html, encoding="utf-8")
    logger.info("HTML report saved → %s  (%.1f KB)", out.name, out.stat().st_size / 1024)
