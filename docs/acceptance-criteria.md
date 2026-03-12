# Master Backlog & Acceptance Criteria

> **Methodology:** Test-Driven Development (TDD) for Business Logic.
> **Status:**  MVP (Core) |  Refinement (Post-MVP)

---

##  Phase 1: Foundation ( MVP)

### Issue #1: Project Initialization
**Acceptance Criteria:**
- [ ] Virtual environment is active; `.gitignore` excludes `venv/` and `.env`.
- [ ] Django 5.1, `pytest-django`, `ruff`, and `django-environ` installed.
- [ ] `pytest` configured in `pytest.ini` and running successfully.
- [ ] Secrets (Secret Key, Debug) moved to `.env` file.

### Issue #2: TDD Custom User Model
**Acceptance Criteria:**
- [ ] **Test:** `test_create_user` fails if email is missing (Email is the unique ID).
- [ ] **Test:** `test_superuser_creation` verifies `is_staff` and `is_superuser` are True.
- [ ] **Code:** `CustomUser` implemented and registered in `settings.py`.
- [ ] **Code:** Initial migrations applied to PostgreSQL.

---

##  Phase 2: Core Subscription Logic ( MVP)

### Issue #3: TDD Subscription CRUD
**Acceptance Criteria:**
- [ ] **Test:** Multi-tenant check—Verify User A cannot access or edit User B's data.
- [ ] **Test:** Form validation fails if price is negative or name is empty.
- [ ] **Code:** Subscription model defined with `ForeignKey` to User.
- [ ] **Code:** Full CRUD views (List, Create, Update, Delete) functional.

### Issue #4: TDD Billing Calculations
**Acceptance Criteria:**
- [ ] **Test:** `get_annual_cost()` logic handles weekly vs. monthly inputs.
- [ ] **Test:** `get_next_billing_date()` handles Feb 29th and 31st-of-month edge cases.
- [ ] **Code:** Implementation of `@property` methods on the Subscription model.
- [ ] **Code:** Dashboard UI built with Tailwind CSS displaying total monthly burn.

---

##  Phase 3: Modern Interaction & Background ( MVP)

### Issue #5: HTMX Refactor (Reactive UI)
**Acceptance Criteria:**
- [ ] Row removal on Delete occurs via `hx-delete` without page reload.
- [ ] Inline price editing uses HTMX partial swaps.
- [ ] Tailwind CSS loading states and "Toast" notifications implemented.

### Issue #6: TDD Notification System (Huey/Redis)
**Acceptance Criteria:**
- [ ] **Test:** Query identifies subscriptions renewing in exactly 48 hours.
- [ ] **Test:** `mail.outbox` verifies email contains correct Subscription Name and Price.
- [ ] **Code:** Redis connected; Huey `periodic_task` scheduled for daily execution.
- [ ] **Code:** SMTP backend configured to send emails to the User's email address.

---

##  Phase 4: Post-MVP & Refinement (Refinement)

### Issue #7: Search & Advanced Filtering
- [ ] **AC:** Search bar filters results via HTMX `keyup` trigger.
- [ ] **AC:** Category filter updates the UI instantly without refresh.

### Issue #8: Multi-Currency Support
- [ ] **AC:** **Test:** Verify "Total Spend" logic converts different currencies to User's Base Currency.
- [ ] **AC:** UI displays appropriate currency symbols based on model data.

### Issue #9: Advanced Analytics
- [ ] **AC:** Charts/Graphs showing spending distribution across categories.