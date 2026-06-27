# Railway Deployment Checklist

## Security

- [x] Rotate Gmail app password (current one is exposed in local `.env`)
- [x] Rotate Gmail OAuth client secret in Google Cloud Console
- [x] Generate a new production `SECRET_KEY`

## Code Changes

- [x] Add `gunicorn` to `requirements.txt`
- [x] Create `config/wsgi.py` (only `asgi.py` exists currently)
- [x] Create `Procfile` with web and worker entries
  ```
  web: gunicorn config.wsgi --bind 0.0.0.0:$PORT
  worker: python manage.py run_huey
  ```
- [x] Update `ALLOWED_HOSTS` in `config/settings.py` to read from env var
  - Currently hardcoded to `['127.0.0.1', 'localhost']`
- [x] Add `CSRF_TRUSTED_ORIGINS` setting (not set at all currently)
- [x] Make Huey/Redis config dynamic — replace hardcoded `localhost:6379` with `REDIS_URL` env var
- [x] Add a build command for Tailwind + collectstatic + migrate
  ```bash
  npm install && npm run tailwind:build && python manage.py collectstatic --noinput && python manage.py migrate
  ```

## Railway Setup

- [x] Create Railway project
- [x] Add PostgreSQL plugin (auto-provides `DATABASE_URL`)
- [x] Add Redis plugin (auto-provides `REDIS_URL`)
- [x] Deploy web service from GitHub repo (uses `web` Procfile entry)
- [x] Deploy worker service from same repo (uses `worker` Procfile entry)

## Environment Variables (set in Railway dashboard)

- [x] `SECRET_KEY` — new production key
- [x] `DEBUG=False`
- [x] `ALLOWED_HOSTS=.up.railway.app`
- [x] `CSRF_TRUSTED_ORIGINS=https://<your-app>.up.railway.app`
- [x] `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- [x] `DEFAULT_FROM_EMAIL`
- [x] `EMAIL_HOST=smtp.gmail.com`
- [x] `EMAIL_PORT=587`
- [x] `EMAIL_HOST_USER` — your Gmail address
- [x] `EMAIL_HOST_PASSWORD` — new rotated app password
- [x] `EMAIL_USE_TLS=True`
- [x] `EMAIL_USE_SSL=False`
- [x] `GMAIL_OAUTH_CLIENT_ID`
- [x] `GMAIL_OAUTH_CLIENT_SECRET` — new rotated secret
- [x] `GMAIL_OAUTH_REDIRECT_URI=https://<your-app>.up.railway.app/accounts/email/gmail/callback/`

## Post-Deploy Verification

- [] Update OAuth redirect URI in Google Cloud Console to match production URL
- [] Verify app loads at Railway URL
- [] Verify static files (CSS/JS) load correctly
- [] Test user login/signup flow
- [] Test Gmail OAuth connection flow
- [] Verify Huey worker is processing background tasks
