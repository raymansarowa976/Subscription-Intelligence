# Subscription-Manager
Full-stack subscription tracker with custom auth, relational billing logic, and async alerts.

Stack: Django 5.1, Postgres, HTMX, Tailwind, Huey/Redis, Ruff, Mypy, Pytest, WhiteNoise.

## Local development

If you want to run the app without PostgreSQL, set `USE_SQLITE=True` in `.env` and start Django normally. That will use a local `db.sqlite3` file for development.

If you want PostgreSQL instead, keep `USE_SQLITE=False` and start the database container first:

```powershell
docker compose up -d db redis
```
