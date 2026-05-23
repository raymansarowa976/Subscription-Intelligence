## 1. Authentication & Session Security

- [x] **Use Django’s ORM for login lookups**
  - [x] Avoid raw SQL for username/email authentication.
  - [x] Normalize username/email input before lookup.
  - [x] Return the same error message for “unknown user” and “wrong password.”

- [ ] **Rate-limit login and recovery flows**
  - [ ] Limit attempts by normalized username/email.
  - [ ] Limit attempts by IP address.
  - [x] Apply rate limits to:
    - [x] Login
    - [x] Login token verification
    - [x] Password reset
    - [x] Username recovery
    - [x] Token resend

- [ ] **Secure session cookies in production**

    ```python
    SESSION_COOKIE_AGE = 1800
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    ```

- [ ] **Rotate sessions after login**
  - [x] Confirm Django rotates the session key after successful login.
  - [x] Clear sensitive session state on logout.
  - [ ] Ensure logged-out users cannot access pages through browser back cache.

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
  - [ ] Use `django-csp` or custom middleware for Content Security Policy.
  - [x] Add protections against clickjacking, MIME sniffing, and referrer leakage.

    ```python
    X_FRAME_OPTIONS = "DENY"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    ```

---

## 3. Passwords and Account Recovery

- [ ] **Use strong password validation**
  - [x] Minimum length.
  - [ ] Common password blocking.
  - [ ] Similarity checks.
  - [x] Numeric-only password blocking.

- [ ] **Protect password reset flows**
  - [x] Tokens must expire.
  - [x] Reset links should be single-use.
  - [ ] Do not reveal whether an email exists.
  - [ ] Notify the user after password changes.

- [ ] **Require password confirmation for dangerous actions**
  - [x] Closing account.
  - [x] Deleting imported data.
  - [ ] Revoking integrations.
  - [ ] Exporting sensitive account data, if appropriate.

---

## 4. Gmail OAuth and Inbox Scan Safety

- [ ] **Store OAuth tokens securely**
  - [ ] Never store plaintext tokens if avoidable.
  - [ ] Encrypt access and refresh tokens at rest.
  - [x] Do not log tokens.

- [x] **Block revoked Gmail connections**
  - [x] If Gmail access is revoked, prevent manual and background scans.
  - [x] Surface a clear warning state.
  - [x] Disable automatic scans for revoked accounts.

- [x] **Use least-privilege OAuth scopes**
  - [x] Request only Gmail read-only permissions if scanning receipts.
  - [x] Avoid broad account or mailbox permissions.

- [x] **Validate ownership of integrations**
  - [x] Users must not scan, revoke, disconnect, or inspect another user’s Gmail connection.

---

## 5. Database and Data Protection

- [ ] **Use PostgreSQL with least-privilege credentials**
  - [ ] App user should not be a database superuser.
  - [ ] Restrict database access to the app server only.

- [ ] **Back up data securely**
  - [ ] Encrypt backups.
  - [ ] Test restore procedures.
  - [ ] Limit backup access.

- [ ] **Protect sensitive exports**
  - [x] Account exports should include only the current user’s data.
  - [ ] Do not expose internal IDs or secrets unnecessarily.
  - [ ] Consider requiring password confirmation before export.

- [ ] **Avoid leaking raw provider payloads**
  - [ ] Scrub tokens, account numbers, message metadata, and headers where possible.

---

## 6. Authorization Checks

- [x] **Filter every user-owned object by `request.user`**
  - [x] Subscriptions
  - [x] Email connections
  - [x] Scan runs
  - [x] Candidates
  - [x] Transaction evidence
  - [x] Account exports

- [x] **Reject cross-user access**
  - [x] Return `403` or `404` when a user tries to access another user’s data.
  - [x] Add tests for cross-user access attempts.

- [x] **Do not rely on frontend hiding**
  - [x] Every destructive or sensitive backend endpoint must enforce authorization server-side.

---

## 7. Input Validation and Output Escaping

- [ ] **Validate all form inputs**
  - [x] Scan preferences
  - [ ] Email rules
  - [x] Subscription edits
  - [x] Uploaded/imported transaction data

- [ ] **Avoid unsafe HTML rendering**
  - [x] Do not mark user-controlled content as safe.
  - [ ] Sanitize email bodies before rendering.
  - [x] Escape merchant names, email subjects, senders, and notes.

- [ ] **Limit payload sizes**
  - [x] Cap inbox scan message counts.
  - [ ] Cap import sizes.
  - [ ] Cap text field lengths for notes, rules, and provider payloads.

---

## 8. Background Jobs and Automation

- [x] **Guard background tasks**
  - [x] Re-check user ownership inside Huey tasks.
  - [x] Re-check Gmail connection status before scans.
  - [x] Handle revoked tokens safely.

- [x] **Make tasks idempotent**
  - [x] Avoid duplicate leads, scan runs, and candidates.
  - [x] Use dedupe keys where possible.

- [x] **Log failures safely**
  - [x] Log enough to debug.
  - [x] Never log access tokens, refresh tokens, passwords, or full email bodies.

---

## 9. Dependency and Supply Chain Security

- [x] **Pin dependencies**
  - [x] Keep `requirements.txt` pinned.
  - [x] Keep `package-lock.json` committed.

- [ ] **Scan dependencies regularly**

    ```powershell
    pip-audit
    npm audit
    ```

- [ ] **Update security patches quickly**
  - [ ] Django
  - [ ] psycopg
  - [ ] Huey
  - [ ] HTMX
  - [ ] Tailwind/build tools

---

## 10. Deployment and Secrets

- [x] **Never commit secrets**
  - [x] `.env`
  - [x] OAuth client secrets
  - [x] Django `SECRET_KEY`
  - [x] Database passwords
  - [x] Email credentials

- [ ] **Use production environment variables**
  - [ ] `DEBUG=False`
  - [x] Strong `SECRET_KEY`
  - [ ] Proper `ALLOWED_HOSTS`
  - [x] Production database URL
  - [x] Production OAuth credentials

    ```python
    DEBUG = False
    ALLOWED_HOSTS = ["your-production-domain.com"]
    ```

- [ ] **Restrict admin access**
  - [ ] Use a strong admin password.
  - [ ] Consider changing the admin URL.
  - [ ] Require MFA if available through hosting/provider controls.
  - [ ] Limit staff accounts.

---

## 11. Monitoring and Incident Response

- [ ] **Log security-relevant events**
  - [ ] Failed logins
  - [ ] Rate-limit triggers
  - [ ] Password resets
  - [ ] Gmail revocations
  - [ ] Account exports
  - [ ] Dangerous actions

- [ ] **Set up error monitoring**
  - [ ] Sentry, Rollbar, or equivalent.
  - [ ] Scrub sensitive data before sending events.

- [ ] **Create an incident checklist**
  - [ ] Rotate secrets.
  - [ ] Revoke OAuth tokens.
  - [ ] Force user logout.
  - [ ] Restore from backup if needed.
  - [ ] Notify affected users if sensitive data is exposed.

---

## 12. Pre-Launch Security Checklist

- [ ] `DEBUG=False`
- [ ] HTTPS enforced
- [ ] HSTS enabled
- [ ] Secure cookies enabled
- [x] CSRF protection verified
- [ ] Login rate limiting tested
- [ ] Password reset flow tested
- [x] Cross-user access tests passing
- [x] OAuth revocation tests passing
- [x] Secrets removed from repo
- [ ] Database user is least-privilege
- [ ] Backups configured and encrypted
- [ ] Dependency audit completed
- [ ] Error monitoring configured
