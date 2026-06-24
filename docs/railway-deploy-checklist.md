# Railway Deployment Checklist

## Security

- [ ] Rotate Gmail app password (current one is exposed in local `.env`)
- [ ] Rotate Gmail OAuth client secret in Google Cloud Console
- [ ] Generate a new production `SECRET_KEY`

## Code Changes

- [ ] Add `gunicorn` to `requirements.txt`
- [ ] Create `config/wsgi.py` (only `asgi.py` exists currently)
- [ ] Create `Procfile` with web and worker entries
  ```
  web: gunicorn config.wsgi --bind 0.0.0.0:$PORT
  worker: python manage.py run_huey
  ```
- [ ] Update `ALLOWED_HOSTS` in `config/settings.py` to read from env var
  - Currently hardcoded to `['127.0.0.1', 'localhost']`
- [ ] Add `CSRF_TRUSTED_ORIGINS` setting (not set at all currently)
- [ ] Make Huey/Redis config dynamic — replace hardcoded `localhost:6379` with `REDIS_URL` env var
- [ ] Add a build command for Tailwind + collectstatic + migrate
  ```bash
  npm install && npm run tailwind:build && python manage.py collectstatic --noinput && python manage.py migrate
  ```

## Railway Setup

- [ ] Create Railway project
- [ ] Add PostgreSQL plugin (auto-provides `DATABASE_URL`)
- [ ] Add Redis plugin (auto-provides `REDIS_URL`)
- [ ] Deploy web service from GitHub repo (uses `web` Procfile entry)
- [ ] Deploy worker service from same repo (uses `worker` Procfile entry)

## Environment Variables (set in Railway dashboard)

- [ ] `SECRET_KEY` — new production key
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS=.up.railway.app`
- [ ] `CSRF_TRUSTED_ORIGINS=https://<your-app>.up.railway.app`
- [ ] `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- [ ] `DEFAULT_FROM_EMAIL`
- [ ] `EMAIL_HOST=smtp.gmail.com`
- [ ] `EMAIL_PORT=587`
- [ ] `EMAIL_HOST_USER` — your Gmail address
- [ ] `EMAIL_HOST_PASSWORD` — new rotated app password
- [ ] `EMAIL_USE_TLS=True`
- [ ] `EMAIL_USE_SSL=False`
- [ ] `GMAIL_OAUTH_CLIENT_ID`
- [ ] `GMAIL_OAUTH_CLIENT_SECRET` — new rotated secret
- [ ] `GMAIL_OAUTH_REDIRECT_URI=https://<your-app>.up.railway.app/accounts/email/gmail/callback/`

## Post-Deploy Verification

- [ ] Update OAuth redirect URI in Google Cloud Console to match production URL
- [ ] Verify app loads at Railway URL
- [ ] Verify static files (CSS/JS) load correctly
- [ ] Test user login/signup flow
- [ ] Test Gmail OAuth connection flow
- [ ] Verify Huey worker is processing background tasks
