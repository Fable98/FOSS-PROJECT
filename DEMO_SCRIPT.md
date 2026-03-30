# Demo Script

## 60-90 Second Version

SubTerra is a groundwater intelligence platform built for the Ministry of Jal Shakti problem statement. It combines DWLR water-level analysis, recharge estimation, and real-time groundwater evaluation in one full-stack system.

On the homepage, we can see the station network, alerts, and state ranking. The app is designed to ingest live-source data, but for hackathon reliability it also supports a resilient fallback demo mode when public source APIs are unstable.

If I open a station, Task 1 shows fluctuation analysis, including water-level trends and anomalies. Task 2 estimates recharge by correlating rainfall and groundwater response, including lag time, net recharge, and recharge status. Task 3 evaluates groundwater resource health with CGWB-style status, depletion rate, and resource availability index.

The backend is built with FastAPI, PostgreSQL with TimescaleDB, and a scraper pipeline that ingests, cleans, and analyzes the data. The frontend is built in React and presents the data through an interactive dashboard for stations, rankings, and alerts.

The key value of SubTerra is that it turns raw groundwater observations into actionable, easy-to-understand monitoring for decision-makers.

## Slightly Longer Version

SubTerra is our solution for real-time groundwater resource evaluation using DWLR data. The problem we’re solving is that groundwater readings exist at scale, but they’re not easily usable for monitoring, recharge assessment, or early warning.

This dashboard brings that together in three major tasks.

First, fluctuation analysis: we track water-level movement over time, compute hourly, daily, and weekly changes, and identify anomalous behavior that may indicate over-extraction or unusual groundwater response.

Second, recharge estimation: we combine water-level behavior with rainfall signals to estimate recharge rate, lag time, and seasonal recharge performance for each station.

Third, resource evaluation: we classify stations into safe, semi-critical, critical, or over-exploited style categories, estimate depletion patterns, and compute a resource availability index for fast interpretation.

The stack uses FastAPI, React, PostgreSQL/TimescaleDB, and a scraper pipeline for ingestion and cleaning. For deployment and judging reliability, the product also supports a fallback demo path when upstream public APIs are unstable, so the full workflow remains testable end-to-end.

The outcome is a practical groundwater intelligence platform that can help move from raw observations to usable decisions.
