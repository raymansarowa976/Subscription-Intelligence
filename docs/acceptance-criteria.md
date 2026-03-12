# Acceptance Criteria

## Phase 1: Foundation ( MVP)

### Issue #1: Project Initialization
**Acceptance Criteria:**
- [ ] Virtual environment is active and `.gitignore` prevents `venv/` from being tracked.
- [ ] `django-admin startproject` and `startapp core` executed.
- [ ] Running `pytest` in the terminal returns "no tests collected" (showing it's configured).
- [ ] Environment variables (`DEBUG`, `SECRET_KEY`) are moved to a `.env` file.

### Issue #2: TDD Custom User Model
**Acceptance Criteria:**
- [ ] **Test:** `test_create_user` fails if email is missing.
- [ ] **Test:** `test_superuser_creation` verifies `is_staff` and `is_superuser` are True.
- [ ] Custom user model is registered in `settings.py`.
- [ ] Database migrations are applied successfully to PostgreSQL.

---

##  Phase 2: Core Subscription Logic ( MVP)

### Issue #3: TDD Subscription CRUD
**Acceptance Criteria:**
- [ ] **Test:** A user can only see/edit their own subscriptions (Multi-tenant check).
- [ ] Forms include validation (e.g., price cannot be negative).
- [ ] User can successfully Create, Read, Update, and Delete a subscription via Django views.

### Issue #4: TDD Billing Calculations
**Acceptance Criteria:**
- [ ] **Test:** `get_annual_cost()` returns correct sum for monthly/weekly/yearly inputs.
- [ ] **Test:** `get_next_billing_date()` correctly handles the 28th/30th/31st of the month.
- [ ] Dashboard displays the correct "Monthly Burn Rate" sum across all active subscriptions.

---

##  Phase 3: Modern Interaction & Background ( MVP)

### Issue #5: HTMX Refactor
**Acceptance Criteria:**
- [ ] Deleting a subscription removes the table row without a full page reload.
- [ ] Inline editing allows price updates directly from the list view.
- [ ] Tailwind "Toast" notifications appear on successful save/delete.

### Issue #6: TDD Notification System (Huey/Redis)
**Acceptance Criteria:**
- [ ] **Test:** A background task can be triggered and completed in the Huey test console.
- [ ] **Test:** Email sending logic is "mocked" to verify the correct recipient and subject line.
- [ ] Huey worker successfully processes a "Reminder" task when a date is within 48 hours.

---

## Phase 4: Post-MVP & Refinement (Refinement)

### Issue #7: Search & Advanced Filtering
**Acceptance Criteria:**
- [ ] Search bar filters results as the user types (HTMX `keyup` trigger).
- [ ] Filter by "Category" (e.g., Entertainment, SaaS) updates the list instantly.

### Issue #8: Multi-Currency Support
**Acceptance Criteria:**
- [ ] Database stores currency type (USD, EUR, etc.).
- [ ] User can select a "Primary Currency" in their profile.
- [ ] Dashboard converts all costs to the Primary Currency for the total sum.