# Subscription-Manager
Full-stack subscription tracker with custom auth, relational billing logic, and async alerts.

Stack: Django 5.1, Postgres, HTMX, Tailwind, Huey/Redis, Ruff, Mypy, Pytest, WhiteNoise.

## Local development

If you want to run the app without PostgreSQL, set `USE_SQLITE=True` in `.env` and start Django normally. That will use a local `db.sqlite3` file for development.

If you want PostgreSQL instead, keep `USE_SQLITE=False` and start the database container first:

```powershell
docker compose up -d db redis
```

## Frontend tooling

Install the Node dependencies before working on compiled Tailwind styles:

```powershell
npm install
```

Build Tailwind once:

```powershell
npm run tailwind:build
```

Watch template and static JavaScript files while developing:

```powershell
npm run tailwind:watch
```

## Email verification

New accounts use a 6-digit email verification token instead of a clickable activation link.

For real email delivery, configure SMTP in `.env`:

```powershell
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@subscriptionintelligence.com
```

If SMTP is not configured, Django falls back to the console email backend and prints the token in the terminal.
