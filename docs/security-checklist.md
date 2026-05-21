# Subscription Intelligence Security Hardening Guide

## 1. Authentication & Session Security

- [ ] **Use Django’s ORM for login lookups**
  - Avoid raw SQL for username/email authentication.
  - Normalize username/email input before lookup.
  - Return the same error message for “unknown user” and “wrong password.”

- [ ] **Rate-limit login and recovery flows**
  - Limit attempts by normalized username/email.
  - Limit attempts by IP address.
  - Apply rate limits to:
    - Login
    - Login token verification
    - Password reset
    - Username recovery
    - Token resend

- [ ] **Secure session cookies in production**

```python
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
```

- [ ] **Rotate sessions after login**
  - Confirm Django rotates the session key after successful login.
  - Clear sensitive session state on logout.
  - Ensure logged-out users cannot access pages through browser back cache.

---

## 2. HTTPS, CSRF, and Browser Security

- [ ] **Force HTTPS in production**

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

- [ ] **Harden CSRF settings**

```python
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "https://your-production-domain.com",
]
```

- [ ] **Add security headers**
  - Use `django-csp` or custom middleware for Content Security Policy.
  - Add protections against clickjacking, MIME sniffing, and referrer leakage.

```python
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
```

---

## 3. Passwords and Account Recovery

- [ ] **Use strong password validation**
  - Minimum length.
  - Common password blocking.
  - Similarity checks.
  - Numeric-only password blocking.

- [ ] **Protect password reset flows**
  - Tokens must expire.
  - Reset links should be single-use.
  - Do not reveal whether an email exists.
  - Notify the user after password changes.

- [ ] **Require password confirmation for dangerous actions**
  - Closing account.
  - Deleting imported data.
  - Revoking integrations.
  - Exporting sensitive account data, if appropriate.

---

## 4. Gmail OAuth and Inbox Scan Safety

- [ ] **Store OAuth tokens securely**
  - Never store plaintext tokens if avoidable.
  - Encrypt access and refresh tokens at rest.
  - Do not log tokens.

- [ ] **Block revoked Gmail connections**
  - If Gmail access is revoked, prevent manual and background scans.
  - Surface a clear warning state.
  - Disable automatic scans for revoked accounts.

- [ ] **Use least-privilege OAuth scopes**
  - Request only Gmail read-only permissions if scanning receipts.
  - Avoid broad account or mailbox permissions.

- [ ] **Validate ownership of integrations**
  - Users must not scan, revoke, disconnect, or inspect another user’s Gmail connection.

---

## 5. Database and Data Protection

- [ ] **Use PostgreSQL with least-privilege credentials**
  - App user should not be a database superuser.
  - Restrict database access to the app server only.

- [ ] **Back up data securely**
  - Encrypt backups.
  - Test restore procedures.
  - Limit backup access.

- [ ] **Protect sensitive exports**
  - Account exports should include only the current user’s data.
  - Do not expose internal IDs or secrets unnecessarily.
  - Consider requiring password confirmation before export.

- [ ] **Avoid leaking raw provider payloads**
  - Scrub tokens, account numbers, message metadata, and headers where possible.

---

## 6. Authorization Checks

- [ ] **Filter every user-owned object by `request.user`**
  - Subscriptions
  - Email connections
  - Scan runs
  - Candidates
  - Transaction evidence
  - Account exports

- [ ] **Reject cross-user access**
  - Return `403` or `404` when a user tries to access another user’s data.
  - Add tests for cross-user access attempts.

- [ ] **Do not rely on frontend hiding**
  - Every destructive or sensitive backend endpoint must enforce authorization server-side.

---

## 7. Input Validation and Output Escaping

- [ ] **Validate all form inputs**
  - Scan preferences
  - Email rules
  - Subscription edits
  - Uploaded/imported transaction data

- [ ] **Avoid unsafe HTML rendering**
  - Do not mark user-controlled content as safe.
  - Sanitize email bodies before rendering.
  - Escape merchant names, email subjects, senders, and notes.

- [ ] **Limit payload sizes**
  - Cap inbox scan message counts.
  - Cap import sizes.
  - Cap text field lengths for notes, rules, and provider payloads.

---

## 8. Background Jobs and Automation

- [ ] **Guard background tasks**
  - Re-check user ownership inside Huey tasks.
  - Re-check Gmail connection status before scans.
  - Handle revoked tokens safely.

- [ ] **Make tasks idempotent**
  - Avoid duplicate leads, scan runs, and candidates.
  - Use dedupe keys where possible.

- [ ] **Log failures safely**
  - Log enough to debug.
  - Never log access tokens, refresh tokens, passwords, or full email bodies.

---

## 9. Dependency and Supply Chain Security

- [ ] **Pin dependencies**
  - Keep `requirements.txt` pinned.
  - Keep `package-lock.json` committed.

- [ ] **Scan dependencies regularly**

```powershell
pip-audit
npm audit
```

- [ ] **Update security patches quickly**
  - Django
  - psycopg
  - Huey
  - HTMX
  - Tailwind/build tools

---

## 10. Deployment and Secrets

- [ ] **Never commit secrets**
  - `.env`
  - OAuth client secrets
  - Django `SECRET_KEY`
  - Database passwords
  - Email credentials

- [ ] **Use production environment variables**
  - `DEBUG=False`
  - Strong `SECRET_KEY`
  - Proper `ALLOWED_HOSTS`
  - Production database URL
  - Production OAuth credentials

```python
DEBUG = False
ALLOWED_HOSTS = ["your-production-domain.com"]
```

- [ ] **Restrict admin access**
  - Use a strong admin password.
  - Consider changing the admin URL.
  - Require MFA if available through hosting/provider controls.
  - Limit staff accounts.

---

## 11. Monitoring and Incident Response

- [ ] **Log security-relevant events**
  - Failed logins
  - Rate-limit triggers
  - Password resets
  - Gmail revocations
  - Account exports
  - Dangerous actions

- [ ] **Set up error monitoring**
  - Sentry, Rollbar, or equivalent.
  - Scrub sensitive data before sending events.

- [ ] **Create an incident checklist**
  - Rotate secrets.
  - Revoke OAuth tokens.
  - Force user logout.
  - Restore from backup if needed.
  - Notify affected users if sensitive data is exposed.

---

## 12. Pre-Launch Security Checklist

- [ ] `DEBUG=False`
- [ ] HTTPS enforced
- [ ] HSTS enabled
- [ ] Secure cookies enabled
- [ ] CSRF protection verified
- [ ] Login rate limiting tested
- [ ] Password reset flow tested
- [ ] Cross-user access tests passing
- [ ] OAuth revocation tests passing
- [ ] Secrets removed from repo
- [ ] Database user is least-privilege
- [ ] Backups configured and encrypted
- [ ] Dependency audit completed
- [ ] Error monitoring configured
