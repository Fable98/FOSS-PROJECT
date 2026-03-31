# 💧 SubTerra
### Real-Time Groundwater Resource Evaluation Using DWLR Data

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

**A full-stack groundwater intelligence platform for live-source ingestion, analytics, and a resilient demo fallback when upstream public APIs are unavailable.**

[🚀 Live Demo](https://foss-project-beryl.vercel.app) · [🔌 Live API](https://foss-project.onrender.com/docs) · [📖 Docs](./docs/) · [🐛 Report Bug](.github/ISSUE_TEMPLATE/bug_report.md) · [✨ Request Feature](.github/ISSUE_TEMPLATE/feature_request.md)

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

> _Add screenshots for later_

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

## Demo Note

For hackathon reliability, SubTerra supports two runtime behaviors:

- `Live-source mode` when India-WRIS / IMD endpoints respond correctly
- `Fallback demo mode` when those public endpoints fail or rate-limit, so judges can still run the full product flow end-to-end

The UI will explicitly show when fallback demo data is active.

## 🌐 Deployments

- Frontend: `https://foss-project-beryl.vercel.app`
- Backend API: `https://foss-project.onrender.com`
- API docs: `https://foss-project.onrender.com/docs`

Current hosted demo notes:

- The hosted app uses `demo_fallback` data mode for reliability.
- Backend is deployed on Render.
- Frontend is deployed on Vercel.
- Production data is stored in Supabase PostgreSQL.
- A one-time scraper seed was run against Supabase to populate demo data.
- The local `docker compose` stack remains the recommended and most reliable end-to-end demo path.

### Option 1 — Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/Fable98/FOSS-PROJECT.git
cd FOSS-PROJECT

# Create local env file
cp .env.example .env

# Start everything with one command
docker compose up --build
```

Wait for the first scraper run to finish, then open `http://localhost:3000` in your browser.

This remains the primary fallback/demo method if hosted deployment is slow or unavailable during judging.

You can watch ingestion progress with:

```bash
docker compose logs -f scraper
```

The first run is ready when you see lines similar to:

```bash
Written to TimescaleDB
Done in ...
Sleeping 900s …
```

---

### Option 2 — Hosted Demo

Open the deployed frontend directly:

`https://foss-project-beryl.vercel.app`

Hosted demo notes:

- Backend API: `https://foss-project.onrender.com`
- API docs: `https://foss-project.onrender.com/docs`
- Current hosted mode uses resilient fallback demo data for reliability.

## ☁️ Deployment Guide

Hosted deployment is optional. For the most reliable hackathon demo, prefer the Docker Compose flow above and treat cloud deployment as a bonus path.
```bash
# from the repo root
# Render can use the included render.yaml blueprint, or you can create a Web Service manually
```

Recommended Render settings:

- Service type: `Web Service`
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Required environment variables:

- `APP_ENV=production`
- `DEBUG=false`
- `SECRET_KEY=<strong-random-secret>`
- `DATABASE_URL=<your-supabase-postgres-url>`
- `ALLOWED_ORIGINS=https://your-frontend.vercel.app`

Optional environment variables:

- `REDIS_URL=<your-render-redis-url>`
- `DATA_GOV_API_KEY=<if you use it>`

Notes:

- `ALLOWED_ORIGINS` can now be either a JSON array or a comma-separated string.
- The app attempts TimescaleDB setup on startup, but safely falls back to plain PostgreSQL if the extension is unavailable.
- After deploy, your API base will be `https://<your-render-service>.onrender.com`.
- For Supabase-backed deploys, the working connection used in production is the session-pooler style URL.

#### Frontend on Vercel

Recommended Vercel settings:

- Framework preset: `Create React App`
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `build`
- Environment variable: `REACT_APP_API_URL=https://<your-render-service>.onrender.com`

#### Scraper / Production Seeding

The hosted backend does not ingest data by itself. In local Docker this is handled by the dedicated `scraper` service in [docker-compose.yml](./docker-compose.yml). In hosted environments you should run the scraper separately against the same database.

Recommended one-time seed command for hackathon/demo reliability:

```bash
python scripts/scraper.py --once --source sample
```

This command:

- creates the schema if needed
- writes station master data
- writes sample groundwater readings
- writes sample rainfall data

If you deploy the scraper on Render, use:

- Root directory: `data`
- Dockerfile: `data/Dockerfile.scraper`
- Docker command:

```bash
python scripts/scraper.py --once --source sample
```

Note: Render will mark that one-time scraper web service as failed after it exits, but that is expected if the seed completed successfully.

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
- [Render](https://render.com/) — hosted backend/API
- [Vercel](https://vercel.com/) — hosted frontend
- [Supabase](https://supabase.com/) — hosted PostgreSQL

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
