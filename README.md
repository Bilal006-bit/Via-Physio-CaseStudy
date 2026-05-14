# Reception Utilization Analysis
### Via Physiotherapy — Case Study | Bilal Ali

Combines patient appointment calendar data with admin shift schedules
to calculate reception workload per 20-minute slot across one clinic week
(KW 35: Mon 25 Aug – Fri 29 Aug 2025).

**Core metric:** Utilization ratio = patients booked ÷ admins available

---

## Project Structure

```text
Via_Physio_CaseStudy/
├── run.py                           ← entry point: python run.py
├── requirements.txt
├── src/
│   ├── config.py                    ← thresholds and paths
│   ├── clean.py                     ← data loading and normalisation
│   ├── analyze.py                   ← utilization calculations
│   ├── visualize.py                 ← heatmap + hourly bar chart
│   └── export.py                    ← CSV exports
├── data/
│   ├── Calendar_Data_RAW.csv        ← patient appointment calendar
│   └── Shiftplan - Admins .xlsx     ← weekly admin shift plan
└── output/                          ← generated on run (git-ignored)
    ├── heatmap.png
    ├── hourly_bar.png
    ├── merged_utilization.csv
    └── weekly_report.csv
```

---

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

All four output files are written to `output/` in one command.

---

## What the Code Does

| Module | Responsibility |
|---|---|
| `clean.py` | Normalise time formats, filter booked slots, deduplicate, parse shift plan, merge |
| `analyze.py` | Daily/hourly averages, overloaded/free slot detection, weekly summary |
| `visualize.py` | Heatmap (RdYlGn_r), hourly bar chart |
| `export.py` | Write merged CSV and weekly report CSV |

---

## Key Findings (KW 35)

- **71.6 % of slots are overloaded** (ratio > 1.0)
- **Tuesday is the busiest day** — avg ratio 3.64, peaks at 7.0 during 17:00–18:00
- **Best windows for admin tasks:** Monday 14:20–14:40 (2 admins, 0 patients), Thursday 13:40

---

## Author

**Bilal Ali** — MSc Data Science, University of Europe (Potsdam)
`Bilalalidaper@gmail.com` | [linkedin.com/in/bilalali06](https://linkedin.com/in/bilalali06)
