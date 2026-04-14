# Subscription Intelligence Implementation Roadmap (generated using chatGPT)

## Goal
Build the core Subscription Intelligence experience on top of the current Django app so a user can:
- authenticate securely
- connect or import a data source
- detect likely subscriptions
- confirm or reject detected subscriptions
- track renewals, spend, and savings opportunities
- receive useful alerts and insights over time

## Current Foundation
Already implemented in this repo:
- custom auth with email token verification
- verified-session gate before accessing the product
- `TransactionEvidence` model for imported billing data
- `SubscriptionCandidate` model for proposed recurring charges
- `Subscription` model for confirmed subscriptions
- transaction ingestion service
- candidate rebuild logic
- dashboard summary metrics
- manual subscription entry
- confirm/reject candidate workflow

Relevant files:
- [subscriptions/models.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/models.py)
- [subscriptions/services.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/services.py)
- [subscriptions/views.py](c:/Users/rayma/projects/Subscription-Manager/subscriptions/views.py)

---

# Phase 1: Make The Core Reliable

## Epic 1: Harden Transaction Ingestion
### Outcome
The app can accept transaction data from a real or simulated provider and persist clean billing evidence safely.

### Tasks
- Add schema validation for ingestion payloads before saving.
- Reject malformed transactions with useful API errors.
- Add ingestion idempotency safeguards beyond `provider_transaction_id`.
- Track ingestion batches or sync sessions.
- Store sync metadata like provider, imported count, duplicate count, failure count, and timestamp.
- Add user-visible “last sync” and sync status messaging.

### Suggested additions
- New model: `TransactionImportRun`
- Optional fields on `TransactionEvidence`:
  - `raw_payload`
  - `import_run`
  - `normalized_merchant_name`

### Files to touch
- `subscriptions/models.py`
- `subscriptions/services.py`
- `subscriptions/views.py`
- tests under `subscriptions/tests/`

### Done when
- ingestion can fail gracefully
- duplicate imports do not create duplicate evidence
- sync results are visible and test-covered

---

## Epic 2: Improve Detection Quality
### Outcome
Recurring subscriptions are detected more accurately from transaction evidence.

### Tasks
- Extract merchant normalization into a more robust utility.
- Normalize vendor aliases like:
  - `NETFLIX.COM`
  - `Netflix`
  - `Netflix US`
- Detect more cadences:
  - monthly
  - yearly
  - quarterly
  - weekly
- Support small price variance tolerance.
- Avoid false positives from one-off merchants.
- Skip low-confidence candidates until enough evidence exists.

### Suggested changes
Add fields to `SubscriptionCandidate`:
- `confidence_score`
- `evidence_count`
- `latest_charge_date`
- `first_charge_date`
- `detection_reason`

### Service updates
Split `rebuild_subscription_candidates()` into smaller units:
- group evidence
- normalize vendor
- infer cadence
- calculate confidence
- build candidate records

### Files to touch
- `subscriptions/services.py`
- `subscriptions/models.py`
- `subscriptions/tests/test_transaction_ingestion.py`

### Done when
- candidate generation is explainable
- common recurring merchants are detected well
- obvious false positives are reduced
- confidence logic is test-covered

---

## Epic 3: Strengthen Candidate Review UX
### Outcome
Users can understand why something was detected and confidently confirm or reject it.

### Tasks
- Show candidate confidence and detection reason in the candidate list.
- Show sample evidence behind each candidate.
- Let users edit merchant name, category, cadence, and amount before confirming.
- Preserve rejected candidates without deleting history.
- Prevent the same rejected pattern from reappearing immediately unless new evidence changes confidence.

### Suggested model additions
- `rejection_reason`
- `reviewed_at`
- `review_notes`

### UI requirements
Candidate cards should show:
- merchant name
- amount
- cadence
- evidence count
- last seen charge
- confidence
- why it was flagged

### Files to touch
- `templates/subscriptions/candidates.html`
- `subscriptions/views.py`
- `subscriptions/forms.py`
- `subscriptions/models.py`

### Done when
- users can review and understand suggestions
- confirmations feel trustworthy
- rejections are respected
- workflow is fully test-covered

---

# Phase 2: Deliver Actual Intelligence

## Epic 4: Build Reliable Subscription Records
### Outcome
Confirmed subscriptions become rich, durable records rather than simple merchant rows.

### Tasks
- Track status transitions:
  - active
  - paused
  - cancelled
- Store billing metadata:
  - billing day
  - start date
  - latest billed date
  - next renewal
- Track price changes over time.
- Separate user-edited fields from inferred fields.

### Suggested model additions to `Subscription`
- `billing_anchor_day`
- `started_on`
- `last_charged_at`
- `inferred_next_renewal`
- `source`
- `is_user_edited`

### Done when
- subscriptions can survive changing evidence over time
- the system distinguishes inferred values from user corrections
- renewal calculations stay stable

---

## Epic 5: Renewal Forecasting And Alerts
### Outcome
Users know what is renewing soon and how much upcoming renewals will cost.

### Tasks
- Create a renewal forecast engine.
- Calculate:
  - renewals in 7 days
  - renewals in 30 days
  - total upcoming renewal cost
- Add background jobs to evaluate upcoming renewals daily.
- Add alert records so notifications are not duplicated.
- Add UI for upcoming renewals and alert history.

### Suggested new model
`SubscriptionAlert`
- `subscription`
- `alert_type`
- `scheduled_for`
- `sent_at`
- `status`

### Background processing
Use Huey for:
- daily renewal forecast refresh
- scheduled alert dispatch

### Files to touch
- `subscriptions/services.py`
- new task module, likely `subscriptions/tasks.py`
- dashboard template
- tests for forecasting and alert scheduling

### Done when
- renewals are forecasted accurately
- alerts are generated once
- upcoming cost metrics are stable

---

## Epic 6: Savings And Overlap Insights
### Outcome
The product begins to act like “subscription intelligence,” not just a tracker.

### Tasks
- Detect overlapping subscriptions by category.
- Flag unusually expensive plans.
- Highlight recent price increases.
- Flag long-unused or low-confidence subscriptions for review.
- Generate insight cards with plain-language recommendations.

### Initial insight types
- duplicate streaming services
- multiple music subscriptions
- overlapping software tools
- high annual run rate
- renewal-heavy next 30 days
- price increase detected

### Suggested implementation
Create an `insights` layer rather than mixing all logic into dashboard assembly.

Possible structure:
- `build_spend_insights(user)`
- `build_overlap_insights(user)`
- `build_renewal_insights(user)`
- `build_price_change_insights(user)`

### Done when
- dashboard insight cards are explainable
- insights are tied to real user actions
- logic is test-covered and not just hardcoded copy

---

# Phase 3: Connect A Real Data Source

## Epic 7: Choose A First Source Strategy
### Outcome
The app gets real subscription evidence from outside the product.

## Recommended decision
Pick one first:
1. email-based discovery
2. transaction-provider import
3. CSV/manual import fallback

## Recommendation for this repo
Start with transaction import or CSV import first.
Why:
- lower privacy/compliance burden than email scanning
- easier to test
- fits your current `TransactionEvidence` model directly

If email discovery is the product vision, build it second once the detection engine is solid.

---

## Epic 8A: CSV Import MVP
### Outcome
Users can upload bank/export CSVs and get subscription candidates.

### Tasks
- Add CSV upload UI
- Map CSV columns to canonical transaction fields
- Validate and preview parsed rows
- Import into `TransactionEvidence`
- Rebuild candidates automatically

### Needed fields
- transaction id or derived dedupe hash
- merchant
- amount
- posted date
- currency
- account id

### Done when
- a user can upload a CSV and get candidates from it in one session

---

## Epic 8B: Email Discovery MVP
### Outcome
Users can connect an inbox and the system can extract subscription/billing signals from billing emails.

### Important note
This is a bigger privacy and product step than transaction import.

### Tasks
- Define email provider connection model
- implement OAuth flow for Gmail first
- fetch billing-related emails only
- parse merchant, amount, renewal date, and billing keywords
- convert parsed emails into `TransactionEvidence`-like or parallel evidence records
- merge email evidence into candidate generation

### New model ideas
`EmailConnection`
- `user`
- `provider`
- `email_address`
- `access_token`
- `refresh_token`
- `expires_at`
- `status`
- `last_synced_at`

`EmailEvidence`
- `user`
- `provider_message_id`
- `merchant_name`
- `amount`
- `currency`
- `sent_at`
- `source_subject`
- `source_from`
- `evidence_type`

### Security requirements
- encrypt provider tokens
- minimize stored email content
- store only extracted evidence where possible
- make consent and revocation very clear

### Done when
- a user can connect Gmail
- billing emails are parsed into evidence
- candidates appear from inbox data

---

# Phase 4: Make It Operational

## Epic 9: Background Jobs And Sync Reliability
### Outcome
Data refreshes happen automatically and safely.

### Tasks
- add periodic sync jobs
- add retry logic
- track job failures
- make sync status visible in UI
- prevent overlapping syncs for the same user/provider

### Needed systems
- Huey tasks
- Redis-backed queue health
- job logging

### Done when
- syncs can run without manual triggering
- failures are observable
- duplicate jobs are controlled

---

## Epic 10: Security, Privacy, And Auditability
### Outcome
The product is safe enough to trust with sensitive financial or inbox data.

### Tasks
- encrypt provider credentials/tokens
- redact sensitive values from logs
- add explicit consent copy and revoke flow
- document retention policy
- add audit logs for:
  - connection created
  - sync started
  - sync completed
  - subscription confirmed/rejected
- ensure admin/debug views do not leak secrets

### Done when
- secrets are protected
- user data access is traceable
- operational logging is safe

---

# Ticket-Sized Build Order

## Branch 1: Candidate Intelligence Foundations
### Scope
- add confidence scoring
- add evidence count and detection reason
- improve normalization and cadence inference
- update tests

### Files
- `subscriptions/models.py`
- `subscriptions/services.py`
- tests

### Deliverable
Higher-quality `SubscriptionCandidate` records.

---

## Branch 2: Candidate Review UX
### Scope
- display candidate evidence and confidence
- allow editing before confirm
- preserve rejection metadata

### Files
- `subscriptions/views.py`
- `subscriptions/forms.py`
- `templates/subscriptions/candidates.html`
- tests

### Deliverable
A complete review flow users can trust.

---

## Branch 3: Subscription Lifecycle Enrichment
### Scope
- enrich `Subscription`
- improve renewal calculations
- store inferred vs user-edited values

### Files
- `subscriptions/models.py`
- `subscriptions/services.py`
- dashboard logic/tests

### Deliverable
Stable subscription records with reliable renewals.

---

## Branch 4: CSV Import MVP
### Scope
- add upload form
- parse CSV
- import to evidence
- rebuild candidates
- show import results

### Files
- new form/view/template
- ingestion service
- tests

### Deliverable
First real user-facing ingestion flow.

---

## Branch 5: Alerts And Renewal Engine
### Scope
- build renewal forecast
- add alert model
- add daily job
- expose upcoming renewals in UI

### Deliverable
Actionable renewal reminders.

---

## Branch 6: Insights Engine
### Scope
- overlap detection
- spend insights
- price-change insights
- dashboard cards

### Deliverable
Actual “intelligence” layer.

---

## Branch 7: Email Integration MVP
### Scope
- OAuth connection
- email sync
- parsed evidence
- candidate generation from inbox

### Deliverable
Inbox-based subscription discovery.

---

# Suggested Model Evolution

## Keep
- `TransactionEvidence`
- `SubscriptionCandidate`
- `Subscription`

## Add next
- `TransactionImportRun`
- `SubscriptionAlert`

## Add when email starts
- `EmailConnection`
- `EmailEvidence`

---

# Recommended API / UI Surface

## User-facing screens
- dashboard
- candidate review queue
- add subscription
- import history
- data source connections
- renewal alerts/history

## Backend endpoints
- transaction ingest
- csv upload/import
- provider connect callback
- sync trigger
- candidate confirm/reject/update
- alerts list/read state

---

# Success Criteria

## MVP Success
A user can:
- log in
- import transaction data
- receive good subscription candidates
- confirm or reject them
- see monthly spend and renewal forecast

## Subscription Intelligence Success
A user can:
- discover subscriptions automatically
- trust the results
- understand upcoming spend
- see overlap or waste
- act before renewals hit

---

# Immediate Recommendation For Your Next 3 Branches

## 1. Candidate Scoring Branch
Build:
- confidence score
- detection reason
- better vendor normalization
- better cadence detection

Why first:
This improves product quality everywhere else.

## 2. Candidate Review Branch
Build:
- editable confirm flow
- evidence display
- rejection persistence

Why second:
Users need trust and control before automation.

## 3. CSV Import Branch
Build:
- upload/import pipeline
- import results page
- automatic candidate generation

Why third:
This gives you a practical end-to-end demo of the full product loop.

---

# Suggested Milestone Timeline

## Milestone 1
Reliable candidate generation from imported transactions.

## Milestone 2
Human review flow for confirm/reject/edit.

## Milestone 3
Renewal forecasting and spend insights.

## Milestone 4
Real ingestion source via CSV or provider connection.

## Milestone 5
Automated alerts and recurring sync.

## Milestone 6
Email-based discovery and richer intelligence.

