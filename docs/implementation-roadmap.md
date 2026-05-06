# Subscription Intelligence Implementation Roadmap

## Goal

Build the core Subscription Intelligence experience on top of the current Django app so a user can:

- [x] Authenticate securely
- [x] Access the product only after verification
- [x] Import transaction evidence through an API
- [x] Scan inbox content for likely subscription leads
- [x] Detect likely subscriptions
- [x] Confirm or reject detected subscriptions
- [x] Track renewals, spend, and savings opportunities
- [ ] Receive useful alerts and insights over time
- [ ] Use AI-assisted receipt parsing to extract subscription evidence from messy billing emails

---

## Current Foundation

Already implemented in this repo:

- [x] Custom auth with email token verification
- [x] Verified-session gate before accessing the product
- [x] Account settings page
- [x] Username change flow
- [x] Password change flow
- [x] Forgot username flow
- [x] Forgot password flow
- [x] `TransactionEvidence` model for imported billing data
- [x] `TransactionImportRun` model for ingestion batch metadata
- [x] `SubscriptionCandidate` model for proposed recurring charges
- [x] `Subscription` model for confirmed subscriptions
- [x] `EmailScanRun` model for inbox scan metadata
- [x] `EmailSubscriptionLead` model for likely subscription emails
- [x] Transaction ingestion service
- [x] Transaction dedupe logic
- [x] Candidate rebuild logic
- [x] Dashboard summary metrics
- [x] Manual subscription entry
- [x] Confirm/reject candidate workflow
- [x] Candidate review page
- [x] HTMX-enhanced candidate confirm/reject workflow
- [x] Compiled Tailwind CSS runtime setup
- [x] Ruff configuration
- [x] Mypy configuration
- [x] Tailwind npm tooling
- [x] Docker Compose services for PostgreSQL and Redis
- [x] Huey configured with Redis
- [ ] Huey tasks actively used for background processing

Relevant files:

- [subscriptions/models.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/models.py)
- [subscriptions/services.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/services.py)
- [subscriptions/views.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/views.py)
- [templates/subscriptions/candidates.html](c:/Users/rayma/projects/Subscription-Manager/templates/subscriptions/candidates.html)
- [templates/subscriptions/_candidate_list.html](c:/Users/rayma/projects/Subscription-Manager/templates/subscriptions/_candidate_list.html)
- [templates/subscriptions/dashboard.html](c:/Users/rayma/projects/Subscription-Manager/templates/subscriptions/dashboard.html)
- [pyproject.toml](c:/Users/rayma/projects/Subscription-Manager/pyproject.toml)
- [tailwind.config.js](c:/Users/rayma/projects/Subscription-Manager/tailwind.config.js)

---

# Phase 1: Make The Core Reliable

## Epic 1: Harden Transaction Ingestion

### Outcome

The app can accept transaction data from a real or simulated provider and persist clean billing evidence safely.

### Tasks

- [x] Add schema validation for ingestion payloads before saving.
- [x] Reject malformed transactions with useful API errors.
- [x] Add ingestion idempotency safeguards beyond `provider_transaction_id`.
- [x] Track ingestion batches or sync sessions.
- [x] Store sync metadata like provider, imported count, duplicate count, failure count, and timestamp.
- [x] Add user-visible “last sync” and sync status messaging.

### Suggested additions

- [x] New model: `TransactionImportRun`
- [x] Optional fields on `TransactionEvidence`:
  - [x] `raw_payload`
  - [x] `import_run`
  - [x] `normalized_merchant_name`

### Files to touch

- [x] `subscriptions/models.py`
- [x] `subscriptions/services.py`
- [x] `subscriptions/views.py`
- [x] tests under `subscriptions/tests/`

### Done when

- [x] Ingestion can fail gracefully.
- [x] Duplicate imports do not create duplicate evidence.
- [x] Sync results are visible and test-covered.

---

## Epic 2: Improve Detection Quality

### Outcome

Recurring subscriptions are detected more accurately from transaction evidence.

### Tasks

- [x] Extract merchant normalization into a utility.
- [ ] Normalize vendor aliases like:
  - [ ] `NETFLIX.COM`
  - [ ] `Netflix`
  - [ ] `Netflix US`
- [x] Detect monthly cadence.
- [x] Detect yearly cadence.
- [ ] Detect quarterly cadence.
- [ ] Detect weekly cadence.
- [ ] Support small price variance tolerance.
- [x] Avoid false positives from one-off merchants by requiring recurring evidence.
- [ ] Skip low-confidence candidates until enough evidence exists.

### Suggested changes

Add fields to `SubscriptionCandidate`:

- [ ] `confidence_score`
- [ ] `evidence_count`
- [ ] `latest_charge_date`
- [ ] `first_charge_date`
- [ ] `detection_reason`

### Service updates

Split `rebuild_subscription_candidates()` into smaller units:

- [ ] group evidence
- [x] normalize vendor
- [x] infer cadence
- [ ] calculate confidence
- [x] build candidate records

### Files to touch

- [x] `subscriptions/services.py`
- [x] `subscriptions/models.py`
- [x] `subscriptions/tests/test_transaction_ingestion.py`

### Done when

- [ ] Candidate generation is explainable.
- [ ] Common recurring merchants are detected well.
- [ ] Obvious false positives are reduced.
- [ ] Confidence logic is test-covered.

---

## Epic 3: Strengthen Candidate Review UX

### Outcome

Users can understand why something was detected and confidently confirm or reject it.

### Tasks

- [ ] Show candidate confidence and detection reason in the candidate list.
- [ ] Show sample evidence behind each candidate.
- [ ] Let users edit merchant name, category, cadence, and amount before confirming.
- [x] Preserve rejected candidates by marking status instead of deleting them.
- [ ] Prevent the same rejected pattern from reappearing immediately unless new evidence changes confidence.
- [x] Use HTMX to confirm/reject candidates without full-page reload.
- [x] Preserve non-JavaScript form fallback.

### Suggested model additions

- [ ] `rejection_reason`
- [ ] `reviewed_at`
- [ ] `review_notes`

### UI requirements

Candidate cards should show:

- [x] Merchant name
- [x] Amount
- [x] Cadence
- [x] Evidence count through supporting transaction count
- [ ] Last seen charge
- [ ] Confidence
- [ ] Why it was flagged

### Files to touch

- [x] `templates/subscriptions/candidates.html`
- [x] `templates/subscriptions/_candidate_list.html`
- [x] `subscriptions/views.py`
- [ ] `subscriptions/forms.py`
- [x] `subscriptions/models.py`

### Done when

- [ ] Users can review and understand suggestions.
- [x] Confirmations and rejections are test-covered.
- [ ] Rejections are respected across candidate rebuilds.
- [ ] Editable confirmation flow is test-covered.

---

# Phase 2: Deliver Actual Intelligence

## Epic 4: Build Reliable Subscription Records

### Outcome

Confirmed subscriptions become rich, durable records rather than simple merchant rows.

### Tasks

- [x] Track status transitions:
  - [x] active
  - [ ] paused
  - [x] cancelled
- [x] Store basic billing metadata:
  - [ ] billing day
  - [ ] start date
  - [ ] latest billed date
  - [x] next renewal
- [ ] Track price changes over time.
- [ ] Separate user-edited fields from inferred fields.

### Suggested model additions to `Subscription`

- [ ] `billing_anchor_day`
- [ ] `started_on`
- [ ] `last_charged_at`
- [ ] `inferred_next_renewal`
- [ ] `source`
- [ ] `is_user_edited`

### Done when

- [ ] Subscriptions can survive changing evidence over time.
- [ ] The system distinguishes inferred values from user corrections.
- [x] Basic renewal calculations are stable for current monthly/yearly flows.
- [ ] Enriched lifecycle behavior is test-covered.

---

## Epic 5: Renewal Forecasting And Alerts

### Outcome

Users know what is renewing soon and how much upcoming renewals will cost.

### Tasks

- [x] Create basic renewal forecast logic for dashboard display.
- [x] Calculate renewals in 7 days.
- [ ] Calculate renewals in 30 days.
- [x] Calculate total upcoming renewal cost for the current dashboard window.
- [ ] Add background jobs to evaluate upcoming renewals daily.
- [ ] Add alert records so notifications are not duplicated.
- [ ] Add UI for upcoming renewals and alert history.

### Suggested new model

`SubscriptionAlert`

- [ ] `subscription`
- [ ] `alert_type`
- [ ] `scheduled_for`
- [ ] `sent_at`
- [ ] `status`

### Background processing

Use Huey for:

- [ ] Daily renewal forecast refresh
- [ ] Scheduled alert dispatch

### Files to touch

- [x] `subscriptions/services.py`
- [ ] new task module, likely `subscriptions/tasks.py`
- [x] dashboard template
- [ ] tests for forecasting and alert scheduling

### Done when

- [x] Basic renewals are forecasted for dashboard display.
- [ ] Alerts are generated once.
- [ ] Upcoming 30-day cost metrics are stable.
- [ ] Huey handles alert work outside the request-response cycle.

---

## Epic 6: Savings And Overlap Insights

### Outcome

The product begins to act like “subscription intelligence,” not just a tracker.

### Tasks

- [x] Detect simple overlapping subscriptions by category.
- [ ] Flag unusually expensive plans.
- [ ] Highlight recent price increases.
- [ ] Flag long-unused or low-confidence subscriptions for review.
- [x] Generate basic insight cards with plain-language recommendations.

### Initial insight types

- [x] Duplicate streaming services
- [x] Multiple music subscriptions
- [x] Overlapping software tools
- [x] High annual run rate through dashboard metric
- [ ] Renewal-heavy next 30 days
- [ ] Price increase detected

### Suggested implementation

Create an `insights` layer rather than mixing all logic into dashboard assembly.

Possible structure:

- [ ] `build_spend_insights(user)`
- [ ] `build_overlap_insights(user)`
- [ ] `build_renewal_insights(user)`
- [ ] `build_price_change_insights(user)`

### Done when

- [x] Basic dashboard insight cards are shown.
- [ ] Insights are tied to real user actions.
- [ ] Insight logic is separated from dashboard assembly.
- [ ] Insight logic is test-covered beyond basic rendering.

---

# Phase 3: Connect Real Data Sources

## Epic 7: Choose A First Source Strategy

### Outcome

The app gets real subscription evidence from outside the product.

### Recommended decision

Pick one first:

- [x] Email-based discovery prototype through IMAP scan
- [x] Transaction-provider-style JSON import
- [ ] CSV/manual import fallback

### Recommendation for this repo

Current reality:

- [x] Transaction import is already implemented as a JSON ingestion endpoint.
- [x] Email discovery has an IMAP-based MVP.
- [ ] CSV import is still the best next practical user-facing ingestion flow.
- [ ] Gmail OAuth should come later because it has a higher privacy/compliance burden.

---

## Epic 8A: CSV Import MVP

### Outcome

Users can upload bank/export CSVs and get subscription candidates.

### Tasks

- [ ] Add CSV upload UI.
- [ ] Map CSV columns to canonical transaction fields.
- [ ] Validate and preview parsed rows.
- [ ] Import into `TransactionEvidence`.
- [ ] Rebuild candidates automatically.
- [ ] Show import result summary.

### Needed fields

- [ ] Transaction id or derived dedupe hash
- [ ] Merchant
- [ ] Amount
- [ ] Posted date
- [ ] Currency
- [ ] Account id

### Done when

- [ ] A user can upload a CSV and get candidates from it in one session.
- [ ] Import errors are understandable.
- [ ] Duplicate rows are safely ignored.

---

## Epic 8B: Email Discovery MVP

### Outcome

Users can connect or scan an inbox and the system can extract subscription/billing signals from billing emails.

### Important note

This is a bigger privacy and product step than transaction import.

### Tasks

- [ ] Define email provider connection model.
- [ ] Implement OAuth flow for Gmail first.
- [x] Fetch billing-related emails through configured IMAP scan.
- [x] Parse sender, subject, received date, snippet, and subscription confidence keywords.
- [ ] Parse merchant, amount, renewal date, and billing entities with AI-assisted extraction.
- [x] Convert parsed emails into `EmailSubscriptionLead` records.
- [ ] Merge email evidence into candidate generation more deeply.

### Existing model

`EmailScanRun`

- [x] `user`
- [x] `provider`
- [x] `mailbox`
- [x] `status`
- [x] `scanned_message_count`
- [x] `matched_message_count`
- [x] `error_details`

`EmailSubscriptionLead`

- [x] `user`
- [x] `scan_run`
- [x] `message_id`
- [x] `sender`
- [x] `sender_name`
- [x] `subject`
- [x] `merchant_name`
- [x] `snippet`
- [x] `received_at`
- [x] `confidence_score`
- [x] `status`
- [x] `raw_headers`

### Future model ideas

`EmailConnection`

- [ ] `user`
- [ ] `provider`
- [ ] `email_address`
- [ ] `access_token`
- [ ] `refresh_token`
- [ ] `expires_at`
- [ ] `status`
- [ ] `last_synced_at`

`EmailEvidence`

- [ ] `user`
- [ ] `provider_message_id`
- [ ] `merchant_name`
- [ ] `amount`
- [ ] `currency`
- [ ] `sent_at`
- [ ] `source_subject`
- [ ] `source_from`
- [ ] `evidence_type`

### Security requirements

- [ ] Encrypt provider tokens.
- [ ] Minimize stored email content.
- [x] Store limited email metadata and snippets for current IMAP MVP.
- [ ] Store only extracted evidence where possible.
- [ ] Make consent and revocation very clear.

### Done when

- [ ] A user can connect Gmail through OAuth.
- [x] Billing-like emails can be parsed into review leads.
- [ ] Candidates appear from structured inbox evidence.
- [ ] Inbox scanning runs in the background through Huey.

---

## Epic 8C: AI-Assisted Receipt Entity Extraction

### Outcome

Messy billing emails and receipts can be converted into structured subscription evidence without writing provider-specific regex for every vendor.

### Why this fits the architecture

- [x] Django service layer can host a dedicated parser service.
- [x] PostgreSQL can store extracted evidence and confidence metadata.
- [x] Huey is configured and can run parsing in the background.
- [x] Candidate review flow already supports human confirmation.
- [ ] Huey parser task still needs to be implemented.

### Tasks

- [ ] Add dedicated parser service for receipt/email text.
- [ ] Clean email HTML into plain text before parsing.
- [ ] Add lightweight NLP/entity extraction for:
  - [ ] Merchant / organization
  - [ ] Money / price
  - [ ] Billing date
  - [ ] Renewal date
- [ ] Combine NLP output with deterministic heuristics.
- [ ] Assign parser confidence score.
- [ ] Store raw extracted entity metadata for auditability.
- [ ] Create review candidates from high-confidence evidence.
- [ ] Keep low-confidence evidence review-only.
- [ ] Run parsing through Huey, not inside the request-response cycle.

### Suggested model

`ReceiptExtraction`

- [ ] `user`
- [ ] `email_lead`
- [ ] `merchant_name`
- [ ] `amount`
- [ ] `currency`
- [ ] `billing_date`
- [ ] `renewal_date`
- [ ] `confidence_score`
- [ ] `raw_entities`
- [ ] `parser_version`
- [ ] `status`
- [ ] `created_at`

### Done when

- [ ] Messy receipt samples produce structured extracted entities.
- [ ] AI/parser suggestions are visible as evidence, not final truth.
- [ ] No subscription is confirmed without user review.
- [ ] Parser behavior is test-covered with realistic receipt fixtures.

---

# Phase 4: Make It Operational

## Epic 9: Background Jobs And Sync Reliability

### Outcome

Data refreshes happen automatically and safely.

### Tasks

- [ ] Add periodic sync jobs.
- [ ] Add retry logic.
- [ ] Track job failures.
- [x] Make transaction and inbox scan status visible in UI.
- [ ] Prevent overlapping syncs for the same user/provider.
- [ ] Move inbox scanning to Huey.
- [ ] Move AI receipt parsing to Huey.
- [ ] Move renewal alerts to Huey.

### Needed systems

- [x] Huey dependency installed
- [x] Huey configured
- [x] Redis service configured
- [ ] Huey task module
- [ ] Redis-backed queue health visibility
- [ ] job logging

### Done when

- [ ] Syncs can run without manual triggering.
- [ ] Failures are observable.
- [ ] Duplicate jobs are controlled.
- [ ] Long-running work no longer blocks user requests.

---

## Epic 10: Security, Privacy, And Auditability

### Outcome

The product is safe enough to trust with sensitive financial or inbox data.

### Tasks

- [ ] Encrypt provider credentials/tokens.
- [ ] Redact sensitive values from logs.
- [ ] Add explicit consent copy and revoke flow.
- [ ] Document retention policy.
- [ ] Add audit logs for:
  - [ ] connection created
  - [ ] sync started
  - [ ] sync completed
  - [ ] subscription confirmed/rejected
  - [ ] AI/parser extraction generated
- [ ] Ensure admin/debug views do not leak secrets.
- [x] Use CSRF protection on forms.
- [x] Gate product access behind authenticated and verified sessions.
- [x] Avoid auto-confirming AI/parser suggestions.

### Done when

- [ ] Secrets are protected.
- [ ] User data access is traceable.
- [ ] Operational logging is safe.
- [ ] AI-assisted evidence remains auditable.

---

# Phase 5: Frontend Professionalization

## Epic 11: CSS Runtime Modernization

### Outcome

The app uses Tailwind the way a production Django app normally would, without relying on the CDN runtime.

### Tasks

- [x] Add `package.json`.
- [x] Add `package-lock.json`.
- [x] Add `tailwind.config.js`.
- [x] Add Tailwind source input file.
- [x] Remove Tailwind CDN from `base.html`.
- [x] Move Tailwind design tokens from inline config to `tailwind.config.js`.
- [x] Compile Tailwind into `static/css/tailwind.css`.
- [x] Serve compiled Tailwind through Django static files.
- [x] Fold global `app.css` rules into Tailwind source.
- [x] Delete old `static/css/app.css`.
- [x] Add regression test for compiled Tailwind usage.
- [ ] Add CI check that compiled Tailwind CSS is current.
- [ ] Perform visual QA pass across all major pages.

### Done when

- [x] App no longer depends on Tailwind CDN.
- [x] Compiled CSS is committed and served by Django.
- [ ] CI can catch stale compiled CSS.
- [ ] Major pages are visually checked after the migration.

---

## Epic 12: HTMX Professionalization

### Outcome

HTMX is used intentionally for progressive enhancement where it improves UX, while normal Django form fallbacks remain intact.

### Tasks

- [x] Keep HTMX loaded in `base.html`.
- [x] Use HTMX for candidate confirm/reject partial updates.
- [x] Add out-of-band candidate count updates.
- [x] Preserve normal POST fallback for candidate review.
- [x] Add tests for HTMX partial responses.
- [ ] Add candidate action loading states.
- [ ] Add disabled/in-flight behavior for HTMX candidate forms.
- [ ] Consider HTMX feedback for inbox scans.
- [ ] Avoid unnecessary HTMX conversion of sensitive auth/session flows.

### Done when

- [x] Candidate review is progressively enhanced.
- [x] HTMX behavior is test-covered.
- [ ] Loading/error states feel polished.
- [ ] HTMX usage remains selective and understandable.

---

# Ticket-Sized Build Order

## Branch 1: Candidate Intelligence Foundations

### Scope

- [ ] Add confidence scoring.
- [ ] Add evidence count and detection reason.
- [ ] Improve normalization and cadence inference.
- [ ] Update tests.

### Files

- [ ] `subscriptions/models.py`
- [ ] `subscriptions/services.py`
- [ ] tests

### Deliverable

Higher-quality `SubscriptionCandidate` records.

---

## Branch 2: Candidate Review UX

### Scope

- [ ] Display candidate evidence and confidence.
- [ ] Allow editing before confirm.
- [ ] Preserve rejection metadata.
- [x] Add HTMX partial candidate confirm/reject.

### Files

- [x] `subscriptions/views.py`
- [ ] `subscriptions/forms.py`
- [x] `templates/subscriptions/candidates.html`
- [x] `templates/subscriptions/_candidate_list.html`
- [x] tests

### Deliverable

A complete review flow users can trust.

---

## Branch 3: Subscription Lifecycle Enrichment

### Scope

- [ ] Enrich `Subscription`.
- [ ] Improve renewal calculations.
- [ ] Store inferred vs user-edited values.

### Files

- [ ] `subscriptions/models.py`
- [ ] `subscriptions/services.py`
- [ ] dashboard logic/tests

### Deliverable

Stable subscription records with reliable renewals.

---

## Branch 4: CSV Import MVP

### Scope

- [ ] Add upload form.
- [ ] Parse CSV.
- [ ] Import to evidence.
- [ ] Rebuild candidates.
- [ ] Show import results.

### Files

- [ ] new form/view/template
- [ ] ingestion service
- [ ] tests

### Deliverable

First real user-facing ingestion flow.

---

## Branch 5: Alerts And Renewal Engine

### Scope

- [ ] Build renewal forecast.
- [ ] Add alert model.
- [ ] Add daily job.
- [ ] Expose upcoming renewals in UI.

### Deliverable

Actionable renewal reminders.

---

## Branch 6: Insights Engine

### Scope

- [ ] Extract overlap detection.
- [ ] Extract spend insights.
- [ ] Add price-change insights.
- [ ] Improve dashboard cards.

### Deliverable

Actual “intelligence” layer.

---

## Branch 7: Email Integration MVP

### Scope

- [ ] OAuth connection.
- [x] IMAP scan prototype.
- [ ] Email sync through Huey.
- [ ] Parsed structured evidence.
- [ ] Candidate generation from inbox evidence.

### Deliverable

Inbox-based subscription discovery.

---

## Branch 8: AI Receipt Entity Extraction

### Scope

- [ ] Parser service.
- [ ] Receipt text cleaning.
- [ ] Entity extraction.
- [ ] Confidence scoring.
- [ ] Huey parser task.
- [ ] Candidate/evidence integration.

### Deliverable

AI-assisted extraction from messy receipt emails.

---

## Branch 9: Frontend CSS Runtime

### Scope

- [x] Compiled Tailwind setup.
- [x] Remove Tailwind CDN.
- [x] Serve compiled CSS.
- [x] Fold app CSS into Tailwind source.

### Deliverable

Professional Tailwind runtime setup.

---

## Branch 10: HTMX Interaction Polish

### Scope

- [x] Candidate partial update.
- [ ] Candidate loading states.
- [ ] Inbox scan feedback.
- [ ] Optional HTMX filtering/search later.

### Deliverable

Intentional, progressive HTMX interactions.

---

# Suggested Model Evolution

## Keep

- [x] `TransactionEvidence`
- [x] `SubscriptionCandidate`
- [x] `Subscription`
- [x] `TransactionImportRun`
- [x] `EmailScanRun`
- [x] `EmailSubscriptionLead`

## Add next

- [ ] `SubscriptionAlert`
- [ ] Candidate confidence/review metadata fields
- [ ] Subscription lifecycle enrichment fields
- [ ] `ReceiptExtraction`

## Add when email OAuth starts

- [ ] `EmailConnection`
- [ ] `EmailEvidence`

---

# Recommended API / UI Surface

## User-facing screens

- [x] Dashboard
- [x] Candidate review queue
- [x] Add subscription
- [ ] Import history
- [ ] Data source connections
- [ ] Renewal alerts/history
- [ ] AI/parser evidence review

## Backend endpoints

- [x] Transaction ingest
- [ ] CSV upload/import
- [ ] Provider connect callback
- [ ] Sync trigger
- [x] Candidate confirm/reject
- [ ] Candidate update/edit
- [ ] Alerts list/read state
- [ ] Receipt extraction trigger/status

---

# Success Criteria

## MVP Success

A user can:

- [x] Log in
- [x] Verify access with token flow
- [x] Import transaction data through the ingestion API
- [x] Receive subscription candidates
- [x] Confirm or reject candidates
- [x] See monthly spend
- [x] See upcoming renewal forecast
- [x] Add subscriptions manually
- [x] Review likely subscription emails from inbox scan
- [ ] Upload CSV transaction data through the UI
- [ ] Receive renewal alerts

## Subscription Intelligence Success

A user can:

- [x] Discover subscriptions from transaction evidence
- [x] Discover likely subscriptions from inbox evidence
- [ ] Discover subscriptions from AI-parsed receipt entities
- [ ] Trust results through confidence, explanation, and evidence
- [x] Understand upcoming spend
- [x] See basic overlap or waste signals
- [ ] Act before renewals hit through notifications
- [ ] Control connected data sources and revoke access

---

# Immediate Recommendation For Your Next 3 Branches

## 1. Candidate Scoring Branch

Build:

- [ ] Confidence score
- [ ] Detection reason
- [ ] Better vendor normalization
- [ ] Better cadence detection
- [ ] Evidence count/date fields

Why first:

This improves product quality everywhere else.

---

## 2. Candidate Review Trust Branch

Build:

- [ ] Editable confirm flow
- [ ] Evidence display
- [ ] Rejection persistence metadata
- [ ] Candidate loading states for HTMX actions

Why second:

Users need trust and control before automation.

---

## 3. CSV Import Branch

Build:

- [ ] Upload/import pipeline
- [ ] Import results page
- [ ] Automatic candidate generation

Why third:

This gives a practical end-to-end demo of the full product loop.

---

# Suggested Milestone Timeline

## Milestone 1

Reliable candidate generation from imported transactions.

- [x] Basic implementation complete
- [ ] Candidate confidence/explanation still needed

## Milestone 2

Human review flow for confirm/reject/edit.

- [x] Confirm/reject complete
- [x] HTMX partial confirm/reject complete
- [ ] Editable confirm flow still needed
- [ ] Evidence display still needed

## Milestone 3

Renewal forecasting and spend insights.

- [x] Basic renewal forecasting complete
- [x] Basic spend insights complete
- [ ] Alerts still needed
- [ ] Dedicated insights layer still needed

## Milestone 4

Real ingestion source via CSV or provider connection.

- [x] JSON transaction ingestion API complete
- [x] IMAP inbox scan MVP complete
- [ ] CSV upload UI still needed
- [ ] Gmail OAuth still needed

## Milestone 5

Automated alerts and recurring sync.

- [x] Huey configured
- [x] Redis configured
- [ ] Huey tasks still needed
- [ ] Alerts still needed
- [ ] Recurring sync still needed

## Milestone 6

Email-based discovery and richer intelligence.

- [x] Basic inbox lead detection complete
- [ ] AI receipt entity extraction needed
- [ ] Structured email evidence needed
- [ ] Gmail OAuth needed
- [ ] Background parsing needed

## Milestone 7

Professional frontend runtime and interactions.

- [x] Compiled Tailwind runtime complete
- [x] Candidate HTMX partial updates complete
- [ ] Visual QA pass needed
- [ ] HTMX loading states needed
- [ ] Search/filter interactions needed
