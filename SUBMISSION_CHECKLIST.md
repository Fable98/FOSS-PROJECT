# Submission Checklist

## Before Recording

- Run a clean rebuild:
  `docker compose down -v`
  `docker compose up --build`
- Wait for the scraper to finish first ingestion:
  `docker compose logs -f scraper`
- Refresh the UI only after logs show:
  `Written to TimescaleDB`
  `Done in ...`
  `Sleeping 900s ...`
- Check at least 4-5 stations from different states
- Check Task 1, Task 2, and Task 3 for at least 2 stations
- Check State Ranking and Alerts tabs
- Keep one strong station selected before recording

## Before Pushing

- `git status` is clean
- README has correct run steps
- Demo/fallback badge is visible in UI
- No local-only secrets are committed
- Latest fixes are pushed to GitHub

## In The Video

- Show homepage overview
- Show one station with Task 1, Task 2, and Task 3
- Mention live-source architecture plus resilient fallback demo mode
- Mention FastAPI + React + TimescaleDB pipeline
- End with impact / decision-support value

## If Something Breaks

- Restart from:
  `docker compose down -v`
  `docker compose up --build`
- Watch:
  `docker compose logs -f scraper`
- Use fallback-demo explanation confidently instead of improvising
