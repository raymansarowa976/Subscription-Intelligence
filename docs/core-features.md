# Feature Roadmap & TDD Tracker

> **Methodology:** Test-Driven Development (TDD) for business logic, with regression tests for frontend integration and progressive enhancement.
> **Status:** MVP (Core) | Refinement (Post-MVP)

---

## Phase 1: Foundation (The "Red-Green" Setup)

- [x] **Issue #1: Testing Suite & Project Init**
  - Installed Django 5.1.
  - Installed `pytest-django`, `ruff`, `mypy`, `django-environ`, Huey, Redis client, and PostgreSQL driver.
  - Configured `pytest.ini` to recognize Django settings.
  - Added `.env`-based settings with `django-environ`.
  - Added Docker Compose services for PostgreSQL and Redis.
  - Added `pyproject.toml` for Ruff, Mypy, and Django stubs configuration.
  - Added Tailwind npm tooling with `package.json`, `package-lock.json`, and `tailwind.config.js`.

- [x] **Issue #2: User Auth (TDD)**
  - **Test:** User registration validates email, username, first name, last name, and password requirements.
  - **Test:** Password complexity rules are enforced.
  - **Test:** Unsupported email domains are rejected.
  - **Test:** Login, verification token, account recovery, username change, and password change flows are covered.
  - **Code:** Custom user model implemented.
  - **Code:** Custom user model registered with `AUTH_USER_MODEL`.
  - **Code:** Signup, login, logout, token verification, forgot username, forgot password, username change, password change, and account settings flows implemented.

---

## Phase 2: Subscription Logic (The "Brain")

- [x] **Issue #3: Subscription Creation & Candidate Review (TDD)**
  - **Test:** Manual subscription creation saves user-scoped subscription data.
  - **Test:** Current user cannot see another user's subscription data.
  - **Test:** Candidate confirmation creates a subscription.
  - **Test:** Candidate rejection dismisses the candidate.
  - **Code:** `Subscription` model implemented.
  - **Code:** `TransactionEvidence`, `TransactionImportRun`, `SubscriptionCandidate`, `EmailScanRun`, and `EmailSubscriptionLead` models implemented.
  - **Code:** Manual add subscription view and form implemented.
  - **Code:** Candidate review page implemented.
  - **Code:** Candidate confirm/reject flows implemented.

- [x] **Issue #4: Billing Math & Dashboard Metrics (TDD)**
  - **Test:** Monthly and yearly subscription amounts are normalized for dashboard totals.
  - **Test:** Upcoming renewal logic identifies subscriptions renewing soon.
  - **Test:** Dashboard metrics are personalized to the current user.
  - **Code:** Monthly spend, annual run-rate, upcoming renewal cost, and renewal count calculated in service layer.
  - **Code:** Next renewal inference implemented from transaction evidence and subscription cadence.
  - **Code:** Dashboard displays subscription metrics, renewal timeline, category mix, and spend trend.

---

## Phase 3: Subscription Intelligence Inputs

- [x] **Issue #5: Transaction Ingestion (TDD)**
  - **Test:** Valid transaction payload creates a successful import run.
  - **Test:** Invalid payload creates a failed import run.
  - **Test:** Duplicate transactions are ignored.
  - **Test:** Recurring transaction evidence creates subscription candidates.
  - **Code:** JSON transaction ingestion endpoint implemented.
  - **Code:** Transaction evidence stored with dedupe key and raw payload.
  - **Code:** Candidate rebuilding logic implemented from recurring transactions.

- [x] **Issue #6: Email Inbox Scan**
  - **Test:** Inbox scan identifies likely subscription emails.
  - **Test:** Inbox scan failure is recorded safely.
  - **Code:** IMAP inbox scanning service implemented.
  - **Code:** Email body parsing, sender parsing, subject parsing, and confidence scoring implemented.
  - **Code:** Email subscription leads stored for review.
  - **Code:** Candidate review page displays likely email-based subscription leads.

- [ ] **Issue #7: AI-Assisted Receipt Entity Extraction**
  - **Test:** Parser extracts merchant, amount, billing date, and likely renewal date from messy receipt text.
  - **Test:** Parser handles ambiguous or missing fields without creating confirmed subscriptions.
  - **Test:** Low-confidence parser results remain review-only.
  - **Code:** Dedicated receipt parser service created.
  - **Code:** Email HTML cleaned into plain text before NLP/entity extraction.
  - **Code:** Parser combines heuristics with lightweight NLP extraction.
  - **Code:** Extracted entities stored with source email, confidence score, parser version, and raw metadata.
  - **Code:** Parser output creates review candidates, not confirmed subscriptions.
  - **Code:** Parsing runs through Huey background tasks.

---

## Phase 4: Modern UI & Background Tasks

- [x] **Issue #8: Professional Tailwind CSS Runtime**
  - Removed Tailwind CDN from runtime templates.
  - Removed inline Tailwind config from `base.html`.
  - Added compiled Tailwind stylesheet served from Django static files.
  - Folded global CSS into Tailwind source via `@layer base`.
  - Added regression test to ensure compiled Tailwind is used instead of CDN Tailwind.
  - Tailwind build verified with `npm run tailwind:build`.

- [x] **Issue #9: Reactive UI (HTMX)**
  - Added HTMX-powered candidate confirm/reject partial updates.
  - Candidate review list refreshes without full-page reload.
  - Candidate count updates through HTMX out-of-band swap.
  - Normal form POST fallback remains intact for non-JavaScript behavior.
  - Tests cover HTMX candidate confirm/reject behavior.

- [ ] **Issue #10: HTMX Interaction Polish**
  - Add loading states for candidate confirm/reject actions.
  - Add disabled/in-flight button behavior for HTMX requests.
  - Consider HTMX feedback for inbox scan requests.
  - Avoid converting auth/session-sensitive flows unless there is a clear UX benefit.

- [ ] **Issue #11: Scheduled Alerts (Huey/Redis)**
  - **Test:** Mock task identifies subscriptions renewing in 48 hours.
  - **Test:** `mail.outbox` verifies notification email includes subscription name, amount, and renewal date.
  - **Code:** Redis connection configured.
  - **Code:** Huey configured with Redis.
  - **Code:** Huey worker task added for renewal checks.
  - **Code:** Daily scheduled task added.
  - **Code:** Django `send_mail` integrated for renewal notifications.

---

## Phase 5: Refinement (Post-Launch)

- [ ] **Issue #12: Currency Conversion**
  - Support USD, EUR, CAD, and other currencies.
  - **Test:** Total spend converts subscriptions into user's base currency.
  - **Test:** Currency conversion handles missing or stale rates safely.
  - UI displays correct currency symbols.

- [x] **Issue #13: Advanced Analytics Foundation**
  - Dashboard shows spending by category.
  - Dashboard shows monthly spend trend.
  - Dashboard shows renewal timeline.
  - Dashboard shows savings/overlap signals.

- [ ] **Issue #14: Advanced Analytics Expansion**
  - Add deeper vendor/category insights.
  - Add monthly report view.
  - Add exportable reports.
  - Add analytics aggregation edge-case tests.

- [ ] **Issue #15: Search & Filter**
  - Add instant subscription search.
  - Add category/status filtering.
  - Use HTMX where it improves responsiveness without sacrificing fallback behavior.
  - Ensure filters remain user-scoped.

- [ ] **Issue #16: CI & Quality Gates**
  - Add CI workflow for `pytest`.
  - Add CI workflow for `ruff check`.
  - Add CI workflow for `mypy`.
  - Add CI workflow for `npm run tailwind:build`.
  - Add check that committed compiled Tailwind CSS is current.
