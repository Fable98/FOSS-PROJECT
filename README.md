# 💧 SubTerra
### Real-Time Groundwater Resource Evaluation Using DWLR Data

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

**A full-stack open-source platform for real-time groundwater monitoring and evaluation using live DWLR sensor data from 5,260 stations across India.**

[🚀 Live Demo](#) · [📖 Docs](./docs/) · [🐛 Report Bug](.github/ISSUE_TEMPLATE/bug_report.md) · [✨ Request Feature](.github/ISSUE_TEMPLATE/feature_request.md)

</div>

---

## 📌 Problem Statement

> **Problem Statement ID:** 25068  
> **Organization:** Ministry of Jal Shakti (MoJS)  
> **Department:** Central Ground Water Board (CGWB)  
> **Category:** Software

Groundwater accounts for **63% of all irrigation water** and **85% of rural drinking water** in India. Despite 5,260 Digital Water Level Recorder (DWLR) stations deployed across the country — transmitting readings every 15 minutes — this high-frequency data remains largely inaccessible to the people who need it most.

SubTerra bridges this gap.

---

## 🎯 What SubTerra Does

SubTerra performs **three core evaluation tasks** using live DWLR data:

### Task 1 — Analyze Real-Time Water Level Fluctuations
- Fetches live sensor readings from all 5,260 DWLR stations
- Calculates hourly/daily rise and fall rates
- Detects anomalies — sudden drops indicating over-extraction
- Visualizes trends on an interactive India map

### Task 2 — Estimate Recharge Dynamically
- Correlates water level data with IMD rainfall data
- Computes pre-monsoon vs post-monsoon net recharge
- Estimates recharge rate (meters/day) per station
- Identifies zones with zero or negative recharge

### Task 3 — Evaluate Groundwater Resources in Real Time
- Classifies every station as Safe / Semi-Critical / Critical / Over-Exploited
- Calculates years-to-depletion using 10-year historical trends
- Generates district and state-level groundwater health scorecards
- Triggers early warning alerts for critical zones

---

## 🖥️ Screenshots

> _Add screenshots here once UI is ready_

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Data Sources                        │
│  India-WRIS (DWLR)  ·  IMD (Rainfall)  ·  CGWB Reports │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │  Fetch   │  │  Clean   │  │   3 Algorithms        │  │
│  │  Layer   │→ │  Layer   │→ │ Task1 Task2 Task3     │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
│                         │                                │
│              PostgreSQL + TimescaleDB                    │
└────────────────────────┬────────────────────────────────┘
                         │ REST API
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Frontend (React)                        │
│   Map  ·  Dashboard  ·  Charts  ·  Alerts  ·  Reports   │
└─────────────────────────────────────────────────────────┘
```

For detailed architecture docs, see [docs/architecture.md](./docs/architecture.md).

---

## 🗂️ Project Structure

```
FOSS-PROJECT/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── docker-compose.yml
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml                  # GitHub Actions CI/CD
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── docs/
│   ├── architecture.md             # System design
│   ├── api-reference.md            # All API endpoints
│   ├── setup-guide.md              # Local dev setup
│   └── data-sources.md             # Data origin & schema
│
├── data/
│   ├── raw/                        # Raw DWLR / IMD datasets
│   ├── processed/                  # Cleaned, ready-to-use data
│   ├── sample/                     # Small test dataset
│   └── scripts/
│       ├── scraper.py              # Fetch from India-WRIS
│       └── clean_data.py           # Clean & validate data
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── main.py                 # FastAPI entry point
│       ├── config.py               # Environment config
│       ├── models/                 # DB models (Station, Reading)
│       ├── routes/                 # API endpoints
│       ├── services/
│       │   ├── analytics.py        # Task 1 — Fluctuation analysis
│       │   ├── recharge.py         # Task 2 — Recharge estimation
│       │   ├── evaluation.py       # Task 3 — Resource evaluation
│       │   └── alerts.py           # Alert engine
│       └── utils/
│
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   └── src/
│       ├── components/
│       │   ├── Map/                # Interactive India map
│       │   ├── Dashboard/          # Main overview
│       │   ├── Charts/             # Trend & recharge charts
│       │   └── Alerts/             # Alert feed
│       ├── pages/
│       ├── services/               # API calls to backend
│       └── utils/
│
└── docker-compose.yml              # One-command full stack
```

---

## ⚡ Quick Start

### Option 1 — Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/subterra.git
cd subterra

# Start everything with one command
docker-compose up --build
```

Then open `http://localhost:3000` in your browser.

---

### Option 2 — Manual Setup

#### Prerequisites
Make sure you have these installed:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 15+ | [postgresql.org](https://postgresql.org) |
| Git | Latest | [git-scm.com](https://git-scm.com) |

#### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run the server
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`  
API docs at `http://localhost:8000/docs`

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at `http://localhost:3000`

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stations` | All DWLR stations with current status |
| GET | `/api/stations/{id}` | Single station details |
| GET | `/api/task1/{id}` | Fluctuation analysis for a station |
| GET | `/api/task2/{id}` | Recharge estimation for a station |
| GET | `/api/task3/{id}` | Full resource evaluation |
| GET | `/api/alerts` | All active critical alerts |
| GET | `/api/summary/{state}` | State-level groundwater summary |
| GET | `/api/summary/{state}/{district}` | District-level summary |

Full API reference: [docs/api-reference.md](./docs/api-reference.md)

---

## 📊 Data Sources

| Data | Source | URL |
|------|--------|-----|
| DWLR Live Readings | CGWB / India-WRIS | [indiawris.gov.in](https://indiawris.gov.in) |
| Historical Water Levels | India-WRIS Archive | [indiawris.gov.in](https://indiawris.gov.in) |
| Station Master Data | CGWB | [cgwb.gov.in](https://cgwb.gov.in) |
| Rainfall Data | IMD | [imd.gov.in](https://imd.gov.in) |
| GW Block Assessment | CGWB Dynamic Report | [cgwb.gov.in](https://cgwb.gov.in) |
| Open Datasets | India Data Portal | [data.gov.in](https://data.gov.in) |

Full data documentation: [docs/data-sources.md](./docs/data-sources.md)

---

## 🌡️ Groundwater Status Classification

| Status | Water Level | Stage of Development | Action |
|--------|-------------|----------------------|--------|
| 🟢 Safe | < 8 m | < 70% | Monitor regularly |
| 🟡 Semi-Critical | 8 – 15 m | 70% – 90% | Reduce extraction |
| 🔴 Critical | 15 – 25 m | 90% – 100% | Regulate strictly |
| ⚫ Over-Exploited | > 25 m | > 100% | Immediate intervention |

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — Python web framework
- [PostgreSQL](https://postgresql.org) + [TimescaleDB](https://timescale.com) — time-series database
- [Pandas](https://pandas.pydata.org/) — data processing
- [Scikit-learn](https://scikit-learn.org/) — trend analysis & ML
- [SQLAlchemy](https://sqlalchemy.org/) — ORM

**Frontend**
- [React 18](https://react.dev/) — UI framework
- [Chart.js](https://chartjs.org/) — data visualization
- [Leaflet.js](https://leafletjs.com/) — interactive maps
- [Tailwind CSS](https://tailwindcss.com/) — styling

**DevOps**
- [Docker](https://docker.com/) — containerization
- [GitHub Actions](https://github.com/features/actions) — CI/CD
- [Docker Compose](https://docs.docker.com/compose/) — local orchestration

---

## 🤝 Contributing

Contributions are what make open source amazing! See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to get started.

**Ways to contribute:**
- 🐛 Report bugs
- ✨ Suggest features
- 📖 Improve documentation
- 🔧 Submit pull requests

Please read our [Code of Conduct](./CODE_OF_CONDUCT.md) before contributing.

---

## 📄 License

Distributed under the MIT License. See [LICENSE](./LICENSE) for more information.

---

## 🙏 Acknowledgements

- [Central Ground Water Board (CGWB)](https://cgwb.gov.in) — for DWLR station data
- [Ministry of Jal Shakti](https://jalshakti-dowr.gov.in) — for the problem statement
- [India-WRIS](https://indiawris.gov.in) — for the water resource data platform
- [IMD](https://imd.gov.in) — for rainfall datasets

---

<div align="center">
Made with 💧 for India's groundwater future
<br/>
Problem Statement #25068 · CGWB · Ministry of Jal Shakti
</div>
# FOSS-PROJECT