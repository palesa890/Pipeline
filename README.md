# Event Ticketing API

A Django REST Framework API for event discovery and ticket reservations. It supports venues, tags, events, ticket types, JWT authentication, and reservation management.

## Tech stack

- Python 3.12 (Docker image)
- Django 4.2 and Django REST Framework
- PostgreSQL 16 in Docker Compose; SQLite is used by default for local development
- JWT authentication with `djangorestframework-simplejwt`
- OpenAPI schema and Swagger UI with `drf-spectacular`
- Pytest, pytest-django, pytest-cov, and Flake8

## Quick start with Docker Compose

### Prerequisites

- Docker Desktop (or Docker Engine with the Compose plugin)
- Git

Clone this repository and change into its directory. Then start the services:

```bash
docker compose up -d --build
```

Compose starts PostgreSQL and the API. The application container waits for the database and applies migrations automatically before starting the server.
The API container's health check uses the readiness endpoint. Application logs are emitted as JSON to container stdout/stderr; requests accept or receive an `X-Request-ID`, which is also included in the Gunicorn access log.

Create a staff account for managing the catalog:

```bash
docker compose exec app python manage.py createsuperuser
```

The API is available at `http://localhost:8000`. Compose provides local-development defaults for its database password and Django secret key. Set `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` in the environment before starting the stack anywhere other than a local development environment.

To stop the services:

```bash
docker compose down
```

To stop the services and delete the database volume as well:

```bash
docker compose down -v
```

## Local development and tests

Use Python 3.12 and install the development dependencies:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Then install dependencies, apply migrations, and start Django:

```bash
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

When `POSTGRES_HOST` is not set, local development uses SQLite. Run the tests and coverage check with:

```bash
pytest --cov=apps.core --cov-report=term-missing --cov-fail-under=90
```

Run the linter with:

```bash
flake8 .
```

## API overview

All API routes are under `/api/` (there is no `/api/v1/` prefix). JWT authentication is required for catalog reads and reservation operations. Any authenticated user can read venues, tags, events, and ticket types; only staff users can create, update, or delete catalog entries. Users can manage their own reservations, while staff can manage all reservations.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/register/` | Register a customer account |
| `POST` | `/api/token/` | Obtain access and refresh JWTs |
| `POST` | `/api/token/refresh/` | Refresh an access JWT |
| `GET` | `/api/venues/`, `/api/tags/`, `/api/events/`, `/api/ticket-types/` | Browse the catalog |
| `POST` | `/api/reservations/` | Reserve ticket quantities |
| `GET` | `/api/reservations/` | List the signed-in user's reservations |
| `POST` | `/api/reservations/{id}/cancel/` | Cancel a reservation |
| `GET` | `/health/live/` | Liveness check (does not query the database) |
| `GET` | `/health/ready/`, `/health/` | Readiness check (includes database connectivity) |
| `GET` | `/api/schema/` | Download the OpenAPI schema |
| `GET` | `/api/docs/` | Open Swagger UI |
| — | `/admin/` | Django administration |

This project reserves quantities of ticket types; it does not currently implement individual seats or seat UUIDs.
The API echoes a valid `X-Request-ID` request header or generates one, and includes it in JSON application logs and the Gunicorn access log.

## Database indexes

The models define indexes for common lookup and ordering patterns:

| Model | Index | Purpose |
| --- | --- | --- |
| `Event` | `starts_at` | Supports event date filtering and chronological ordering |
| `Event` | `(venue, starts_at)` | Supports event lookups for a venue ordered by start time |
| `Reservation` | `(user, created_at)` | Supports a user's reservation history, newest first |
| `Reservation` | `(event, status)` | Supports reservation lookups by event and status |

The schema also enforces constraints such as positive capacities and reservation quantities, non-negative ticket prices, and one line per ticket type in a reservation.

## cURL examples

The examples use the Bash shell. Replace placeholder IDs and token values with values from your environment. For protected endpoints, set `ACCESS_TOKEN` to a valid access token:

```bash
export ACCESS_TOKEN="your_access_token"
AUTH_SCHEME="Bearer"
```

### 1. Register a customer and obtain a JWT

Register a customer account:

```bash
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alex",
    "email": "alex@example.com",
    "password": "Use-A-Strong-Password-42"
  }'
```

Obtain access and refresh tokens:

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alex",
    "password": "Use-A-Strong-Password-42"
  }'
```

Use the returned `access` token as `ACCESS_TOKEN`. To create catalog entries, obtain a token by authenticating a staff account (created with `createsuperuser`) at the same token endpoint, then use that staff token as `ACCESS_TOKEN`.

### 2. Create catalog entries (staff only)

Create a venue and note its returned `id`:

```bash
curl -X POST http://localhost:8000/api/venues/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Grand Hall",
    "address": "1 Main Street",
    "capacity": 500
  }'
```

Create an event using the venue ID, and note the event ID:

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "venue": VENUE_ID,
    "title": "Annual Tech Summit 2026",
    "description": "A technology conference.",
    "starts_at": "2026-11-15T09:00:00Z",
    "capacity": 500
  }'
```

Create a ticket type for that event and note its ID:

```bash
curl -X POST http://localhost:8000/api/ticket-types/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "event": EVENT_ID,
    "name": "General Admission",
    "price": "50.00",
    "capacity": 500
  }'
```

### 3. Browse events and ticket types

Catalog requests require authentication:

```bash
curl http://localhost:8000/api/events/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}"

curl http://localhost:8000/api/ticket-types/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}"
```

### 4. Reserve tickets

Create a reservation by supplying an event ID and one or more ticket type/quantity pairs:

```bash
curl -X POST http://localhost:8000/api/reservations/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "event": EVENT_ID,
    "items": [
      {
        "ticket_type": TICKET_TYPE_ID,
        "quantity": 2
      }
    ]
  }'
```

### 5. View and cancel reservations

Customers see their own reservations:

```bash
curl http://localhost:8000/api/reservations/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}"
```

Cancel a reservation by its returned ID:

```bash
curl -X POST http://localhost:8000/api/reservations/RESERVATION_ID/cancel/ \
  -H "Authorization: ${AUTH_SCHEME} ${ACCESS_TOKEN}"
```

## Project checklist

- [x] Django app with 3+ related models
- [x] CRUD endpoints with authentication and permissions
- [x] Custom error handling with a consistent JSON schema
- [x] Multi-stage Dockerfile
- [x] Docker Compose with PostgreSQL
- [x] Unit tests with at least 90% coverage (CI test suite runs against PostgreSQL)
- [x] GitHub Actions CI pipeline (lint, test, build)
- [x] `/health/` endpoint
- [x] Swagger/OpenAPI documentation
- [x] README with setup, cURL samples, and index reasoning
