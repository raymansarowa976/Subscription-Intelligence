# Subscription Intelligence – Quality Assurance & Product Strategy Report
**Document Version:** 1.0.0  
**Date:** May 19, 2026  
**Author:** Rayman Sarowa  
**Status:** Architecture & Implementation Pipeline  

---

##  1. User Interface (UI) & Core Presentation
- [ ] **Enforce UI Consistency:** Unify design systems, component borders, and container spacing across all pages.
- [ ] **Standardize Design Language:** Apply the "Neubrutalist-lite" visual framework from the landing page to all authenticated views (simpler, cleaner, and more professional).
- [ ] **Optimize Spacing & Visual Density:** Enhance padding and layout breathing room to maximize user-friendliness and reduce cognitive load.
- [ ] **Build Contact Page:** Implement a functional `Contact Us` page or view to handle support channels and recruiter inquiries.

---

##  2. Authentication, Authorization & Session Management (Auth)
- [x] **Implement Dual-Identifier Login:** Update backend authentication logic to accept **either** `username` OR `email` in the login form.
- [x] **Configure Transient Session Security:** Set up session termination so the user is automatically logged out when the browser tab or window is closed.
- [x] **Add Intelligent Sign-In Routing:** Implement a middleware check: if an already authenticated user visits the sign-in page, automatically redirect them to the dashboard.

---

##  3. Core Dashboard Ecosystem
- [ ] **Build Guided Onboarding Flow:** Force users to connect their Gmail account *before* accessing scan tools to eliminate initialization confusion.
- [ ] **Decouple Gmail Integration:** Move all Gmail authentication logic, connection state details, and sync controls to a dedicated sidebar page.
- [ ] **Decouple Analytics & Reports:** Extract the 6-month spend curve charts and complex data visualizations to a standalone analytics sidebar page.
- [ ] **Decouple Data Sources Registry:** Move the mailbox health indicators and connection logs into a functional, standalone data sources page on the sidebar.
- [ ] **Consolidate Dashboard Actions:** Remove redundant processing hooks and leave exactly one primary, high-visibility `Review Pending Items` button.

---

##  4. Subscription Management Pipeline
- [ ] **Implement Collapsible UI Components:** Upgrade the `Pending Detections` elements to use collapsible accordion lists to clean up vertical screen real estate.

---

##  5. Account Settings & System Preferences
- [ ] **Redesign Settings Layout:** Build a two-column layout featuring a dedicated **Account Settings Sidebar** that mimics native desktop/laptop settings menus.
- [ ] **Isolate the Danger Zone:** Move high-risk actions away from general settings into an isolated, distinct view linked explicitly from the main settings pane.
- [ ] **Prune Redundant Sessions:** Permanently remove the "Log out other sessions" button from the UI.
- [ ] **Prune Deprecated Account Actions:** Remove the useless "Delete imported evidence" and "Close account" buttons that clutter the layout containers.
- [ ] **Standardize Password Visibility:** Add an eye-icon toggle (mask/unmask) to the password fields inside confirmation boxes to align with the rest of the application's forms.
- [ ] **Refactor Micro-Copy Labels:** Rewrite text strings for user interaction headings (e.g., update `Change Username` and `Change Password` titles for better clarity).
- [ ] **Build Revocation Gatekeeping Logic:** Implement backend validation to ensure that if a user revokes Gmail permissions, the inbox scan engine completely blocks execution and surfaces a warning state.
- [ ] **Build Login-Triggered Automation:** Program the background worker logic (**Huey**) to automatically trigger an inbox scan the moment a user signs into the platform if they have "Automatic Scans" enabled.
- [ ] **Hook Up Scan Preferences:** Make the scanning interval checkboxes and email selection rules fully functional, persisting their configurations directly into PostgreSQL.

### Preferences & Automation Business Logic
* **Revocation Gatekeeping:** Implement a hard validation wall on background actions. If a user revokes their Google Cloud permissions, the `Inbox Scan` engine must automatically disable, block manually forced tasks, and throw a clear alert state.
* **Automated Login Scans:** Build the business logic for real-time background task generation. If a user enables automated scans, a background worker task should trigger via **Huey** immediately upon a successful login callback to process new inbox items.
* **Email Scan Preferences Module:** Make the scan preference configuration checkboxes and inputs fully functional, allowing users to save and edit scanning boundaries directly within PostgreSQL storage.
