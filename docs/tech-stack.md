# Tech Stack Rationale

## Core Framework
- **Django 5.1**: Chosen for its "batteries-included" approach to security (CSRF protection, SQL injection defense) and its powerful ORM which is critical for handling complex subscription billing logic.

## Frontend & Interaction
- **HTMX**: Used to provide a reactive, SPA-like user experience without the complexity of a JavaScript framework. It allows for "Locality of Behavior" by keeping logic within HTML.
- **Tailwind CSS**: Provides a utility-first styling system that ensures a modern, responsive UI with a minimal CSS footprint.

## Data & State
- **PostgreSQL**: The primary relational database, ensuring ACID compliance for user financial and subscription data.
- **Redis**: Acts as the high-speed message broker between the Django application and the background workers.

## Asynchronous Processing
- **Huey**: A lightweight alternative to Celery. It manages scheduled tasks (like daily renewal checks) and sends notifications without blocking the main request-response cycle.

## Development & Quality Assurance
- **Ruff**: A lightning-fast Python linter and formatter to maintain high code standards.
- **Mypy**: Provides static type checking to catch "type errors" before they reach production.
- **Pytest-Django**: Modern testing suite for ensuring billing logic remains accurate through development.