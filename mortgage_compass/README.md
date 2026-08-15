# Project Configuration (`mortgage_compass/`) — Developer Guide

The `mortgage_compass/` package houses the Django project configuration, settings modules, WSGI/ASGI entrypoints, and root routing definitions.

---

## Directory Index

```
/Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/
├── [__init__.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/__init__.py)
│   └── Package marker for the Django configuration module.
├── [settings.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/settings.py)
│   └── Django settings configuration containing database engine setup (SQLite WAL), installed apps, static asset configuration, humanize helpers, RateAPI thresholds, cache TTLs, geo defaults, and timezone definitions.
├── [urls.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/urls.py)
│   └── Root URL configuration delegating application routes to [`web.urls`](file:///Users/alejandrodiaz/Documents/projects/loan/web/urls.py) with static asset serving handlers.
└── [wsgi.py](file:///Users/alejandrodiaz/Documents/projects/loan/mortgage_compass/wsgi.py)
    └── WSGI entry point utilized by Gunicorn in production and Docker/Unraid deployments.
```

---

## Key Settings Configuration

1. **SQLite Write-Ahead Logging (WAL)**:
   Configured in `settings.py` with `timeout: 20` and `journal_mode: WAL` on SQLite connections to support high-concurrency read operations during automated test runs and multi-tab browsing.
2. **Static Asset Resolution**:
   Configured with `django.contrib.staticfiles` pointing to `web/static/` for local vendor bundles (`htmx.min.js`, `chart.umd.min.js`) and custom CSS.
3. **Environment Overrides**:
   - `SECRET_KEY` / `DJANGO_SECRET_KEY`: Can be overridden via environment variable (defaults to a development fallback).
   - `DEBUG`: Configurable via `DEBUG=1` or `DEBUG=0`.
   - `FRED_API_KEY`: St. Louis FRED API key for weekly benchmark updates.
   - `RATEAPI_KEY`: RateAPI.dev API key for credit union live market quote enrichment.
   - `RATEAPI_BUCKET_SIZE`: Loan amount bucketing interval in dollars (default: `25000`).
   - `RATEAPI_SAFETY_THRESHOLD`: Monthly safety guard limit before blocking external requests (default: `18` calls/month).
   - `RATEAPI_CACHE_TTL_DAYS`: Cache validity period in days before triggering fresh outbound RateAPI calls (default: `7` days).
   - `DEFAULT_STATE`: Default state code for regional rate discovery (default: `CA`).
   - `DEFAULT_COUNTY`: Default county name for charter filtering (default: `Santa Clara`).
   - `DEFAULT_CITY`: Default municipal city (default: `San Jose`).
   - `DEFAULT_ZIP`: Default postal code (default: `95110`).

---

## Running the Application

```bash
# Apply database schema migrations
.venv/bin/python manage.py migrate

# Seed worked fixture & demo data
.venv/bin/python manage.py seed_demo_data

# Batch ingest live credit union rates into local SQLite cache
.venv/bin/python manage.py fetch_market_rates --all-terms

# Start development server on port 8080
.venv/bin/python manage.py runserver 0.0.0.0:8080
```
