# Reception Utilization Analysis
### Via Physiotherapy — Case Study | Bilal Ali

---

## What This Does

Combines patient appointment calendar data with admin shift schedules
to calculate reception workload per 20-minute slot across one clinic week
(KW 35: Mon 25 Aug – Fri 29 Aug 2025).

**Output:** Utilization ratio per slot = patients booked ÷ admins available

---

## Project Structure

```
Via_Physio_CaseStudy/
├── analysis.py            ← single script, runs the full pipeline
├── requirements.txt
├── data/
│   ├── Calendar_Data_RAW.csv        ← patient appointment calendar
│   └── Shiftplan - Admins .xlsx     ← weekly admin shift plan
└── output/                          ← generated on run (git-ignored)
    ├── merged_utilization.csv
    ├── heatmap.png
    ├── daily_bar.png
    └── weekly_report.csv
```

---

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python analysis.py
```

---

## Author

**Bilal Ali** — MSc Data Science, University of Europe (Potsdam)
Bilalalidaper@gmail.com | linkedin.com/in/bilalali06
