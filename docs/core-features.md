#  Feature Roadmap & TDD Tracker

> **Methodology:** Test-Driven Development (TDD) for Business Logic.
> **Status:**  MVP (Core) |  Refinement (Post-MVP)

---

##  Phase 1: Foundation (The "Red-Green" Setup)
- [ ] **Issue #1: Testing Suite & Init**
  - Install `pytest-django`, `ruff`, and `django-environ`.
  - Configure `pytest.ini` to recognize the Django settings.
- [ ] **Issue #2: User Auth (TDD)**
  - **Test:** Verify `CustomUser` can be created with email as username.
  - **Code:** Implement Custom User model and migrations.

##  Phase 2: Subscription Logic (The "Brain")
- [ ] **Issue #3: CRUD Operations (TDD)**
  - **Test:** Create a subscription and verify it saves to Postgres.
  - **Code:** Build models, basic views, and HTML forms.
- [ ] **Issue #4: Billing Math (TDD)**
  - **Test:** Input a monthly price and verify "Total Annual Cost" calculation.
  - **Test:** Verify "Next Billing Date" logic (e.g., handles Feb 29th).
  - **Code:** Implement logic in `models.py` or `services.py`.

##  Phase 3: Modern UI & Background Tasks
- [ ] **Issue #5: Reactive UI (HTMX)**
  - Implement partial page refreshes for adding/deleting subscriptions.
  - Add Tailwind CSS "Empty State" dashboards.
- [ ] **Issue #6: Scheduled Alerts (Huey/Redis)**
  - **Test:** Mock a task that identifies subscriptions renewing in 48 hours.
  - **Code:** Set up Huey worker and Redis connection.
  - **Code:** Integrate Django `send_mail` for renewal notifications.

---

##  Phase 5: Refinement (Post-Launch)
- [ ] **Issue #7: Currency Conversion** (Support USD, EUR, etc.)
- [ ] **Issue #8: Advanced Analytics** (Charts showing spending by category)
- [ ] **Issue #9: Search/Filter** (Instant filtering via HTMX)