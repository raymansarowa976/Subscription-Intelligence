# Subscription Manager

Subscription Manager is a local-first Django app for finding, reviewing, and tracking recurring subscriptions. It combines manual subscription entry, transaction evidence, Gmail receipt scanning, review candidates, renewal alerts, spend analytics, account controls, and multi-currency totals.

The project is currently intended to run locally or in a self-managed environment. It does not require a paid hosted deployment to use during development or demos.

## Features

- Custom user accounts with email-token verification, username changes, password changes, account export, session controls, and account deletion flows.
- Subscription dashboard with monthly spend, annual run-rate, upcoming renewals, active/inactive counts, category mix, and trend data.
- Manual subscription tracking with user-isolated data.
- Candidate review queue for transaction, inbox, and receipt-parser evidence.
- Gmail OAuth connection, mailbox status, re-sync, revoke, scan preferences, and per-user mailbox isolation.
- Receipt parsing that extracts suggested merchant, amount, cadence, renewal date, and confidence metadata.
- Review filters, sorting, suppressed lead recovery, bulk actions, HTMX updates, and normal form fallbacks.
- Multi-currency subscription totals with exchange-rate support and user base currency.
- Analytics views, category distribution, monthly trend data, deeper insights, and exportable monthly reports.
- Renewal notification tasks using Huey and Redis.
- Compiled Tailwind CSS served from Django static files.
- Local quality gates for Pytest, Ruff, Mypy, and Tailwind freshness.

## Stack

- Python 3.13
- Django 5.1
- PostgreSQL or SQLite for local development
- Redis and Huey for background work
- HTMX
- Tailwind CSS
- WhiteNoise for static files when `DEBUG=False`
- Pytest, pytest-django, Ruff, Mypy, django-stubs

## Local Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
npm install
```

Create a local `.env` from the example:

```powershell
Copy-Item .env.example .env
```

This project normally uses Docker Compose for local PostgreSQL and Redis, while Django still runs from your local Python environment with `python manage.py runserver`.

Start the local services:

```powershell
docker compose up -d
```

Keep these database settings in `.env`:

```text
USE_SQLITE=False
DATABASE_URL=postgres://postgres:postgres@127.0.0.1:5678/subscription_db
```

For local development, keep debug mode enabled:

```text
DEBUG=True
```

Then run migrations:

```powershell
python manage.py migrate
```

Build Tailwind:

```powershell
npm run tailwind:build
```

Start Django:

```powershell
python manage.py runserver
```

Open:

```text
http://localhost:8000/
```

If you want a temporary SQLite-only setup without Docker, set `USE_SQLITE=True`. That creates a local `db.sqlite3` file and skips the Compose Postgres database.

## PostgreSQL and Redis

Docker Compose provides the local Postgres and Redis services:

```powershell
docker compose up -d
```

The default database URL in `.env.example` points at the Compose Postgres service:

```text
DATABASE_URL=postgres://postgres:postgres@127.0.0.1:5678/subscription_db
```

Run migrations after the database is available:

```powershell
python manage.py migrate
```

## Background Tasks

Huey handles scheduled renewal checks and Gmail re-sync work. Keep a worker running in a second terminal when testing those flows:

```powershell
python manage.py run_huey
```

Redis must be running for normal Huey operation. During tests, Huey runs in immediate mode.

## Email and Gmail

New signups use a 6-digit email verification token. If SMTP is not configured, Django uses the console email backend and prints email content in the terminal.

For real email delivery, set these in `.env`:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

For Gmail OAuth scanning, configure a Google OAuth client and use this local redirect URI:

```text
GMAIL_OAUTH_CLIENT_ID=your-google-oauth-client-id
GMAIL_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
GMAIL_OAUTH_REDIRECT_URI=http://localhost:8000/accounts/email/gmail/callback/
```

Never commit real `.env` secrets. If real credentials were exposed, rotate them.

## Frontend

Tailwind is compiled into `static/css/tailwind.css`.

Build once:

```powershell
npm run tailwind:build
```

Watch templates and static JavaScript while developing:

```powershell
npm run tailwind:watch
```

The CI workflow checks that committed Tailwind output is fresh after a build.

## Quality Checks

Run the same core checks used by CI:

```powershell
npm run tailwind:build
git diff --exit-code -- static/css/tailwind.css
ruff check .
mypy config users subscriptions
pytest
```

The test suite uses SQLite automatically and does not require a running Postgres container.

## Useful Routes

- `/` - landing page
- `/accounts/signup/` - create account
- `/accounts/login/` - sign in
- `/accounts/account/settings/` - account settings
- `/dashboard/` - dashboard
- `/dashboard/subscriptions/` - subscriptions list and filters
- `/dashboard/analytics/` - analytics
- `/dashboard/data-sources/` - candidate review and source health
- `/dashboard/gmail/` - Gmail integration status

## Local Troubleshooting

If localhost shows a generic server error, confirm local development settings:

```text
DEBUG=True
USE_SQLITE=False
```

If `DEBUG=False`, run `collectstatic` before starting the app because WhiteNoise uses manifest static files:

```powershell
python manage.py collectstatic
```

If using Postgres, make sure Docker is running and the database service is up:

```powershell
docker compose ps
docker compose up -d db redis
```

If background jobs do not run, start Redis and the Huey worker:

```powershell
docker compose up -d redis
python manage.py run_huey
```
