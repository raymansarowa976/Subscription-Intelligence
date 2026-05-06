# Master Backlog & Acceptance Criteria

> **Methodology:** Test-Driven Development (TDD) for business logic and regression coverage for frontend integration.
> **Status:** MVP (Core) | Refinement (Post-MVP)

---

## Phase 1: Foundation (MVP)

### Issue #1: Project Initialization
**Acceptance Criteria:**
- [x] Virtual environment is supported; `.gitignore` excludes `venv/`, `.env`, `node_modules/`, cache files, and generated local artifacts.
- [x] Django 5.1, `pytest-django`, `ruff`, `mypy`, `django-environ`, Huey, Redis client, and PostgreSQL driver installed.
- [x] `pytest` configured in `pytest.ini` and running successfully.
- [x] Secrets such as `SECRET_KEY`, `DEBUG`, and database settings moved to `.env`.
- [x] Docker Compose provides local PostgreSQL and Redis services.
- [x] `pyproject.toml` configures Ruff, Mypy, and Django stubs.
- [x] `package.json`, `package-lock.json`, and `tailwind.config.js` added for compiled Tailwind usage.
- [x] Tailwind build scripts documented in README.

### Issue #2: TDD Custom User Model
**Acceptance Criteria:**
- [x] **Test:** User registration validates required email, username, first name, last name, and password fields.
- [x] **Test:** Registration rejects unsupported email domains.
- [x] **Test:** Password security rules are enforced.
- [x] **Code:** Custom `User` model implemented and registered with `AUTH_USER_MODEL`.
- [x] **Code:** Initial migrations created.
- [x] **Code:** Authentication views support signup, login, logout, verification token, account recovery, username change, and password change.

---

## Phase 2: Core Subscription Logic (MVP)

### Issue #3: TDD Subscription & Candidate Review
**Acceptance Criteria:**
- [x] **Test:** Multi-tenant check verifies one user cannot see another user's subscription data.
- [x] **Test:** Manual subscription form validates required fields and positive amount.
- [x] **Code:** `Subscription` model defined with `ForeignKey` to User.
- [x] **Code:** Manual add subscription flow functional.
- [x] **Code:** Transaction ingestion creates subscription candidates from recurring evidence.
- [x] **Code:** Candidate confirm creates a subscription.
- [x] **Code:** Candidate reject dismisses the candidate.
- [x] **Code:** Candidate review page supports progressive enhancement with HTMX partial updates.

### Issue #4: TDD Billing Calculations & Dashboard
**Acceptance Criteria:**
- [x] **Test:** Monthly and yearly subscription amounts are normalized for monthly and annual dashboard totals.
- [x] **Test:** Next renewal calculation handles monthly and yearly cadences.
- [x] **Code:** Dashboard displays total monthly spend, annual run-rate, upcoming renewals, active/inactive counts, category mix, and trend data.
- [x] **Code:** Dashboard uses Tailwind CSS styling.
- [x] **Code:** Dashboard only displays data for the current authenticated user.

---

## Phase 3: Modern Interaction & Background (MVP)

### Issue #5: CSS & HTMX Frontend Cleanup
**Acceptance Criteria:**
- [x] Tailwind CDN removed from runtime templates.
- [x] Inline Tailwind CDN config removed from `base.html`.
- [x] Compiled Tailwind stylesheet served from Django static files.
- [x] Global CSS folded into Tailwind source under `@layer base`.
- [x] Regression test verifies compiled Tailwind CSS is used instead of CDN Tailwind.
- [x] Candidate confirm/reject forms use HTMX partial swaps.
- [x] Candidate count updates with HTMX out-of-band swap.
- [x] Candidate confirm/reject still works without JavaScript through normal form POST fallback.
- [ ] Add HTMX loading states for candidate confirm/reject actions.
- [ ] Add visual QA pass across all major auth, dashboard, subscription, and candidate pages.

### Issue #6: TDD Notification System (Huey/Redis)
**Acceptance Criteria:**
- [ ] **Test:** Query identifies subscriptions renewing in exactly 48 hours.
- [ ] **Test:** `mail.outbox` verifies email contains correct subscription name, amount, and renewal date.
- [x] **Code:** Redis service configured in Docker Compose.
- [x] **Code:** Huey installed and configured with Redis.
- [ ] **Code:** Huey `periodic_task` scheduled for daily renewal checks.
- [ ] **Code:** SMTP backend configured to send renewal emails to the user's email address.
- [ ] **Code:** Notification task runs outside the request-response cycle.

---

## Phase 4: Subscription Intelligence Inputs (MVP / Refinement)

### Issue #7: Transaction Ingestion
**Acceptance Criteria:**
- [x] **Test:** Valid transaction payload creates a successful import run.
- [x] **Test:** Invalid transaction payload creates a failed import run.
- [x] **Test:** Duplicate transaction evidence is ignored.
- [x] **Code:** Transaction evidence stored with dedupe key and raw payload.
- [x] **Code:** Recurring transaction patterns produce subscription candidates.
- [x] **Code:** Ingestion endpoint returns structured JSON responses.

### Issue #8: Email Inbox Scan
**Acceptance Criteria:**
- [x] **Test:** Inbox scan identifies likely subscription emails.
- [x] **Test:** Inbox scan failure records failed scan state.
- [x] **Code:** IMAP scan service extracts sender, subject, body snippet, received date, and confidence score.
- [x] **Code:** Email subscription leads are stored for review.
- [x] **Code:** Candidate review page displays likely subscription email leads.
- [ ] Move inbox scanning to Huey so long-running scans do not block the request-response cycle.
- [ ] Add HTMX loading feedback for inbox scan requests if scan remains synchronous before Huey migration.

### Issue #9: AI-Assisted Receipt Entity Extraction
**Acceptance Criteria:**
- [ ] **Test:** Parser extracts merchant, amount, billing date, and likely renewal date from messy receipt text.
- [ ] **Test:** Parser handles missing or ambiguous fields without creating false confirmed subscriptions.
- [ ] **Test:** Low-confidence extraction remains review-only.
- [ ] **Code:** Dedicated receipt parser service added.
- [ ] **Code:** Email HTML is cleaned into plain text before NLP processing.
- [ ] **Code:** Parser combines heuristics with lightweight NLP entity extraction.
- [ ] **Code:** Extracted entities are stored with source email, confidence score, parser version, and raw entity metadata.
- [ ] **Code:** AI/parser output creates review candidates, not confirmed subscriptions.
- [ ] **Code:** Huey task runs receipt parsing in the background.
- [ ] **Code:** Candidate review UI clearly labels parser output as suggested evidence.

---

## Phase 5: Post-MVP & Refinement

### Issue #10: Search & Advanced Filtering
**Acceptance Criteria:**
- [ ] Search bar filters subscription results via HTMX `keyup` trigger.
- [ ] Category filter updates the UI without full page refresh.
- [ ] Empty states remain clear when filters return no results.
- [ ] Filtering preserves user data isolation.

### Issue #11: Multi-Currency Support
**Acceptance Criteria:**
- [ ] **Test:** Total spend converts different currencies to user's base currency.
- [ ] **Test:** Historical exchange-rate behavior is defined and covered.
- [ ] UI displays appropriate currency symbols based on model data.
- [ ] Subscription and transaction models support currency-aware calculations.

### Issue #12: Advanced Analytics
**Acceptance Criteria:**
- [x] Dashboard includes category distribution chart.
- [x] Dashboard includes monthly spend trend chart.
- [ ] Add deeper spending insights across vendors, categories, and renewal windows.
- [ ] Add exportable monthly report view.
- [ ] Add tests for analytics aggregation edge cases.

### Issue #13: Tooling & Quality Gates
**Acceptance Criteria:**
- [x] Ruff configured in `pyproject.toml`.
- [x] Mypy configured in `pyproject.toml`.
- [x] Django stubs configured in `pyproject.toml`.
- [x] Mypy passes for `config`, `users`, and `subscriptions`.
- [x] Ruff passes for the current configured baseline.
- [x] Pytest suite passes.
- [ ] Add CI workflow to run pytest, Ruff, Mypy, and Tailwind build.
- [ ] Add Tailwind build freshness check if generated CSS is committed.
