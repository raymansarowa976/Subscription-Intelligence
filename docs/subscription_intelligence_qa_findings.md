# Subscription Intelligence – Quality Assurance & Product Strategy Report
**Document Version:** 1.0.0  
**Date:** May 19, 2026  
**Author:** Rayman Sarowa  
**Status:** Architecture & Implementation Pipeline  

---

## 1. User Interface (UI) & Core Presentation

### Architectural Guidelines
* **Design Language Alignment:** Enforce consistent UI paradigms, design systems, and components across all application routing levels. 
* **Aesthetic Baseline:** Maintain the "Neubrutalist-lite" visual framework of the landing page as the standard design language across all authenticated views. This design offers a more professional, modern, and uncluttered presentation compared to highly complex dashboards.
* **Cognitive Accessibility:** Maximize user friendliness by optimizing spacing, preserving explicit container groupings, and reducing visual density.

### Component Additions
* **Contact Channels:** Design and build a functional `Contact Us` page or view to serve as a low-friction support channel for external users and potential recruiters.

---

## 2. Authentication, Authorization & Session Management (Auth)

### Credentials Optimization
* **Flexible Identifier Login:** Update the backend login architecture and backend processing strategy to accept **either** the User's `username` **OR** `email` address in a single submission field.

### Session Security Policy
* **Transient Browser Sessions:** Reconfigure the session framework (e.g., via Django session engine settings) to ensure that the user session terminates immediately when the browser tab or window is closed (`SESSION_COOKIE_AGE` modifications or standard storage alterations).
* **Intelligent Routing:** If an authenticated user triggers a call to the `/login` or `/signin` route, catch the session state immediately and redirect them straight to the active dashboard.

---

## 3. Core Dashboard Ecosystem

### System Onboarding
* **Structured Onboarding:** Restructure the workflow so users connect their Gmail accounts *before* accessing scan controls. The interface must guide them through authentication clearly to eliminate any onboarding confusion.

### Module Decoupling (Navigation & Sidebar)
* **Gmail Integration Service:** Relocate all Gmail connection logic, data pipeline health, and configurations away from the main summary page into a dedicated, separate view mapped explicitly to the primary navigation sidebar.
* **Analytics & Reporting:** Spin off the 6-month spend curves, metrics, and complex data models into a separate page accessible directly via the sidebar navigation.
* **Data Sources Registry:** Implement the data sources interface as a distinct, functional view on the sidebar, showing connected mailboxes and service health indicators.

### Action Demobilization & Layout Cleaning
* **Consolidated Item Processing:** Condense redundant execution hooks down to a single, high-visibility `Review Pending Items` button to simplify the main interface layout.

---

## 4. Subscription Management Pipeline

### Interactive Components
* **Collapsible Data Lists:** Upgrade the `Pending Detections` interface with clean, expandable/collapsible accordion elements. This allows users to inspect granular transactional data details without cluttering the screen real estate.

---

## 5. Account Settings & System Preferences

### View Restructuring (Navigation Layout)
* **Hierarchical Settings Navigation:** Replace the traditional flat card layout with a double-column configuration featuring a specialized **Account Settings Sidebar**. This layout should mimic clean, high-end native operating system patterns (e.g., macOS/Windows settings) to enhance clarity on desktop views.
* **Danger Zone Decoupling:** Extract the high-risk account functions from the main settings pane and move them into a dedicated, isolated sub-view linked cleanly from the primary account configuration area.

### Feature Refinement & Code Deletion
* **Session Pruning:** Remove the "Log out other sessions" utility to streamline token management.
* **Button Deprecation:** Permanently delete the redundant or poorly scoped "Delete imported evidence" and "Close account" buttons to avoid platform friction.
* **Credential Masking Overhaul:** Enhance all user confirmation modal fields (specifically security boxes involving secondary confirmation entry) with viewable/unviewable toggle buttons (the classic password mask eye icon) to match application standards.
* **Actionable Labeling Updates:** Rewrite the text headings for user interaction areas (e.g., modify `Change Username` and `Change Password` micro-copy to reflect dynamic action flows).

### Preferences & Automation Business Logic
* **Revocation Gatekeeping:** Implement a hard validation wall on background actions. If a user revokes their Google Cloud permissions, the `Inbox Scan` engine must automatically disable, block manually forced tasks, and throw a clear alert state.
* **Automated Login Scans:** Build the business logic for real-time background task generation. If a user enables automated scans, a background worker task should trigger via **Huey** immediately upon a successful login callback to process new inbox items.
* **Email Scan Preferences Module:** Make the scan preference configuration checkboxes and inputs fully functional, allowing users to save and edit scanning boundaries directly within PostgreSQL storage.
