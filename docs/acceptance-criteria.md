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
- [x] Add HTMX loading states for candidate confirm/reject actions.
- [x] Add visual QA pass across all major auth, dashboard, subscription, and candidate pages.

### Issue #6: TDD Notification System (Huey/Redis)
**Acceptance Criteria:**
- [x] **Test:** Query identifies subscriptions renewing in exactly 48 hours.
- [x] **Test:** `mail.outbox` verifies email contains correct subscription name, amount, and renewal date.
- [x] **Code:** Redis service configured in Docker Compose.
- [x] **Code:** Huey installed and configured with Redis.
- [x] **Code:** Huey `periodic_task` scheduled for daily renewal checks.
- [x] **Code:** SMTP backend configured to send renewal emails to the user's email address.
- [x] **Code:** Notification task runs outside the request-response cycle.

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
- [x] Move inbox scanning to Huey so long-running scans do not block the request-response cycle.
- [x] Add HTMX loading feedback for inbox scan requests if scan remains synchronous before Huey migration.

### Issue #9: AI-Assisted Receipt Entity Extraction
**Acceptance Criteria:**
- [x] **Test:** Parser extracts merchant, amount, billing date, and likely renewal date from messy receipt text.
- [x] **Test:** Parser handles missing or ambiguous fields without creating false confirmed subscriptions.
- [x] **Test:** Low-confidence extraction remains review-only.
- [x] **Code:** Dedicated receipt parser service added.
- [x] **Code:** Email HTML is cleaned into plain text before NLP processing.
- [x] **Code:** Parser combines heuristics with lightweight NLP entity extraction.
- [x] **Code:** Extracted entities are stored with source email, confidence score, parser version, and raw entity metadata.
- [x] **Code:** AI/parser output creates review candidates, not confirmed subscriptions.
- [x] **Code:** Huey task runs receipt parsing in the background.
- [x] **Code:** Candidate review UI clearly labels parser output as suggested evidence.

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

### Issue #14: Per-User Email OAuth Integration
**Acceptance Criteria**
- [ ] **Test:** User can start an email connection flow from account settings or integrations.
- [ ] **Test:** OAuth callback links the connected mailbox to the currently authenticated user.
- [ ] **Test:** One user cannot scan or access another user's connected mailbox.
- [ ] **Test:** Inbox scan uses the current user's connected email account instead of global `.env` IMAP credentials.
- [ ] **Test:** Disconnected or expired email connections do not run scans and show clear feedback.
- [ ] **Test:** Existing receipt parser flow still creates review candidates from OAuth-fetched messages.
- [ ] **Code:** `EmailConnection` model added for per-user mailbox connections.
- [ ] **Code:** Email provider, email address, scopes, token expiry, and active/disconnected state are stored.
- [ ] **Code:** OAuth access and refresh tokens are stored securely.
- [ ] **Code:** Gmail OAuth connect and callback views added.
- [ ] **Code:** OAuth `state` parameter is used to protect the callback flow.
- [ ] **Code:** Token refresh service added for expired access tokens.
- [ ] **Code:** Inbox scan task accepts a user/email-connection identifier and validates ownership.
- [ ] **Code:** Gmail API message search/fetch service added.
- [ ] **Code:** Existing email lead and receipt parser pipeline works with Gmail API messages.
- [ ] **Code:** Account settings or integrations UI shows connected mailbox status.
- [ ] **Code:** User can disconnect/revoke a connected mailbox.
- [ ] **Code:** Global IMAP scan remains available only as local/dev fallback or is explicitly deprecated.

### Issue #15: Account Settings Security & Privacy Refinement
**Acceptance Criteria:**
- [x] **Code:** Account overview shows active status and member-since date.
- [x] **Code:** Username and password update flows are available through inline progressive disclosure.
- [x] **Code:** Username-change microcopy explains the 6-digit email token and expected time.
- [x] **Code:** Password change flow includes a live password strength meter.
- [x] **Code:** Account settings shows Gmail API connection status.
- [x] **Code:** Account settings includes a visually separated danger zone.
- [ ] **Test:** Account settings renders account overview, connected services, recent activity, inline edit controls, and danger zone.
- [ ] **Test:** Inline username form preserves validation errors in context without losing the settings page.
- [ ] **Test:** Inline password form preserves validation errors in context without losing the settings page.
- [ ] **Test:** User can log out other active sessions while preserving the current session.
- [ ] **Test:** Account deletion/data deletion flows require password confirmation and explicit typed confirmation.
- [ ] **Test:** One user cannot view, delete, or export another user's account/subscription data.
- [ ] **Code:** Recent activity uses real login/session metadata instead of placeholder copy.
- [ ] **Code:** Add a dedicated "Log out other sessions" action.
- [ ] **Code:** Add account data export before destructive deletion.
- [ ] **Code:** Add delete subscription/imported evidence action with confirmation flow.
- [ ] **Code:** Add close-account/deactivate flow with confirmation flow.
- [ ] **Code:** Gmail re-sync and revoke-access actions are wired to real endpoints.
- [ ] **Code:** Gmail status shows connected email, last sync time, token health, granted scopes, and clear error states.
- [ ] **Code:** Privacy controls allow users to manage scan scope, retention period, automatic scans, and deletion of email-derived evidence.
- [ ] **Code:** Card-level success/error feedback appears after username, password, Gmail, session, and danger-zone actions.
- [ ] **Code:** Account settings keyboard, focus, and screen-reader behavior are covered for disclosure panels and destructive actions.

### Issue #16: Landing Page Refinement
**Acceptance Criteria:**
- [ ] **Test:** Landing page renders for anonymous users without requiring authentication.
- [ ] **Test:** Authenticated users can navigate from landing page to dashboard.
- [ ] **Test:** Landing page uses compiled Tailwind CSS and does not rely on CDN Tailwind.
- [ ] **Test:** Primary CTA routes anonymous users to signup and secondary CTA routes to login.
- [ ] **Test:** Landing page remains responsive across mobile and desktop viewport smoke checks.
- [ ] **Code:** First viewport clearly presents Subscription Intelligence as the product and leaves a hint of the next section visible.
- [ ] **Code:** Hero uses relevant product imagery, generated visual asset, or an immersive product UI scene rather than a generic gradient-only layout.
- [ ] **Code:** Page explains the core promise: detect subscriptions, review candidates, track renewal timing, and surface spend insights.
- [ ] **Code:** Landing page includes privacy/security trust signals for email scanning and account verification.
- [ ] **Code:** Landing page includes a concise feature section for dashboard insights, candidate review, receipt parsing, and renewal alerts.
- [ ] **Code:** Landing page includes clear empty-state/demo visuals that reflect real app workflows.
- [ ] **Code:** Navigation includes signup/login actions and preserves the product brand in the first viewport.
- [ ] **Code:** Landing page copy avoids unsupported claims and keeps Gmail/OAuth language aligned with implemented capabilities.
- [ ] **Code:** Landing page visual QA confirms text does not overlap or overflow on common mobile and desktop viewports.

### Issue #17: Subscription Review Page Full Functionality
**Acceptance Criteria:**
- [x] **Code:** Inbox matches below the review confidence threshold are hidden from the primary review queue.
- [x] **Code:** Newsletter-like senders/content are demoted from the primary review queue.
- [x] **Code:** Visible inbox count reflects reviewable inbox leads, not all raw email matches.
- [x] **Code:** Bulk dismissal exists for low-confidence/newsletter-like inbox noise.
- [x] **Code:** Back-to-dashboard CTA uses higher-contrast brand styling.
- [x] **Code:** Email match cards show merchant, estimated price, and renewal date before full email text.
- [x] **Code:** Full email context is hidden behind a progressive disclosure control.
- [x] **Code:** Renewal calendar and pending candidate sections use intentional empty states.
- [x] **Code:** Source health shows inbox scan status with processed and matched message counts.
- [x] **Code:** Currency and count values use tabular numerals.
- [ ] **Test:** Confidence threshold behavior is configurable and covered for boundary values below, at, and above the threshold.
- [ ] **Test:** Bulk dismiss only affects the current authenticated user's leads.
- [ ] **Test:** Bulk dismiss supports normal form fallback and HTMX-enhanced updates.
- [ ] **Test:** Confirming an email-derived candidate updates the source email lead status to confirmed.
- [ ] **Test:** Rejecting an email-derived candidate updates the source email lead status to dismissed or review-only.
- [ ] **Test:** One user cannot view, dismiss, restore, confirm, reject, or bulk-update another user's candidates or leads.
- [ ] **Test:** Candidate and lead actions require verified login-token sessions.
- [ ] **Test:** Duplicate POSTs for confirm/reject/dismiss are idempotent.
- [ ] **Test:** Dashboard review counts match the filtered review queue counts.
- [ ] **Test:** Confirming, rejecting, or dismissing from the review page updates dashboard counts correctly.
- [ ] **Test:** Source health displays succeeded, failed, queued, and in-progress states.
- [ ] **Test:** Search and filters preserve user data isolation.
- [ ] **Test:** Review page visual regression or smoke coverage verifies no text overflow in candidate cards.
- [ ] **Test:** Disclosure controls are keyboard accessible and preserve readable focus states.
- [ ] **Code:** Store an explicit lead classification such as `billing_signal`, `newsletter`, `marketing`, `low_confidence`, or `unknown`.
- [ ] **Code:** Preserve suppressed leads in a secondary "Filtered out" view so users can recover false negatives.
- [ ] **Code:** Add a user-facing explanation for why a lead was filtered out.
- [ ] **Code:** Use parser/entity metadata to prioritize leads with merchant, price, cadence, and renewal date.
- [ ] **Code:** Add per-lead actions for "Mark as newsletter," "Dismiss," and "Restore."
- [ ] **Code:** Add selectable checkboxes and selected-count summary for batch actions.
- [ ] **Code:** Add bulk actions for selected leads, not only all low-signal leads.
- [ ] **Code:** Add CSRF-protected POST endpoints for per-lead dismiss, newsletter classification, restore, and selected bulk actions.
- [ ] **Code:** Update inbox match counts and suppressed counts out-of-band after HTMX actions.
- [ ] **Code:** Allow users to edit merchant name, amount, cadence, category, and renewal date before confirming.
- [ ] **Code:** Validate edited candidate values before creating a subscription.
- [ ] **Code:** Show parser confidence and extracted fields beside editable values.
- [ ] **Code:** Prevent duplicate confirmed subscriptions from the same candidate or source lead.
- [ ] **Code:** Add loading, success, and error states for every candidate and inbox action.
- [ ] **Code:** Add scan run states for queued/in-progress if Huey has not completed yet.
- [ ] **Code:** Show last scan start time, completion time, duration, messages processed, matches created, and parser candidates created.
- [ ] **Code:** Link source health to latest scan-run details.
- [ ] **Code:** Show retry action for failed scans with clear error feedback.
- [ ] **Code:** Add filters for source type, confidence band, status, category, cadence, and date range.
- [ ] **Code:** Add sorting by confidence, renewal date, amount, newest, and merchant name.
- [ ] **Code:** Persist filter state in query parameters so review URLs are shareable/bookmarkable.
- [ ] **Code:** Empty states explain when filters hide all results and offer a clear reset action.
- [ ] **Code:** Ensure all mutation endpoints use POST-only, CSRF-protected forms.
- [ ] **Code:** Record audit metadata for candidate/lead actions, including action type and timestamp.
- [ ] **Code:** Keep dashboard "found/review/tracked" pipeline metrics aligned with raw leads, reviewable leads, suppressed leads, and confirmed subscriptions.
- [ ] **Code:** Clearly distinguish raw inbox matches from reviewable billing candidates in dashboard copy.
