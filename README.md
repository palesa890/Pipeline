# Event Ticketing API

A Django REST Framework API for managing venues, events, ticket types, and ticket reservations. Customers can browse the catalog and reserve tickets; staff users manage catalog records.

> **This API reserves ticket quantities, not individual seats.** It does not have seat UUIDs or seat-selection endpoints.

## Technology

- Python 3.12, Django 4.2, and Django REST Framework
- PostgreSQL 16 with Docker Compose; SQLite for local development without PostgreSQL
- JWT authentication and OpenAPI/Swagger documentation
- Pytest with a 90% coverage gate, Flake8, and GitHub Actions CI

## Get started with Docker

### 1. Install and start Docker

Install Docker Desktop (or Docker Engine with the Compose plugin) and make sure it is running.

### 2. Clone the project

In Command Prompt, PowerShell, or a terminal:

```console
git clone https://github.com/palesa890/Pipeline.git
cd Pipeline
```

### 3. Start the API and database

```console
docker compose up -d --build
```

Compose starts PostgreSQL and the API. The API container runs database migrations automatically before starting the server. Open the API documentation at <http://localhost:8000/api/docs/>.

Check service status:

```console
docker compose ps
```

The `app` service should become healthy. Its readiness check confirms that the API can connect to PostgreSQL.

### 4. Create a staff account

The API starts with an empty catalog. Create a staff account so you can add venues, events, and ticket types:

```console
docker compose exec app python manage.py createsuperuser
```

Follow the prompts to set a username and password. You will use these credentials to sign in and create catalog entries below.

Compose has local-development defaults for the Django secret key and database password, so a `.env` file is not required for a local quick start. For anything beyond local development, set your own `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` through a private environment or secrets manager. Do not commit secret values.

## First API walkthrough (Windows Command Prompt)

The examples below use `curl.exe` and Command Prompt syntax. Run each command on a single line. Replace sample credentials and IDs with your own. The IDs returned by the API are integers.

### 1. Register a customer account

Choose a strong password that passes Django's password checks:

```cmd
curl.exe -X POST http://localhost:8000/api/register/ -H "Content-Type: application/json" -d "{\"username\":\"alex\",\"email\":\"alex@example.com\",\"password\":\"Choose-A-Strong-Unique-Password-42!\"}"
```

A successful response includes the new user's `id` and `username`. Registration creates a regular customer account, not a staff account.

### 2. Sign in and save the access token

For customer actions, sign in with the account you just registered:

```cmd
curl.exe -X POST http://localhost:8000/api/token/ -H "Content-Type: application/json" -d "{\"username\":\"alex\",\"password\":\"Choose-A-Strong-Unique-Password-42!\"}"
```

The response contains two values: `access` and `refresh`. Copy the **`access`** value (not `refresh`) into this Command Prompt window:

```cmd
set "ACCESS_TOKEN=paste-the-access-value-here"
```

Use the token in later requests like this:

```cmd
curl.exe http://localhost:8000/api/events/ -H "Authorization: Bearer %ACCESS_TOKEN%"
```

If you see `token_not_valid`, request a fresh pair at `/api/token/` and make sure you copied `access`. Access tokens expire; a refresh token can be exchanged for a new access token:

```cmd
curl.exe -X POST http://localhost:8000/api/token/refresh/ -H "Content-Type: application/json" -d "{\"refresh\":\"paste-the-refresh-value-here\"}"
```

Copy the returned `access` value into `ACCESS_TOKEN` again. Keep both tokens private.

### 3. Sign in as staff to create the catalog

Only staff accounts can create or edit venues, events, tags, and ticket types. Use the staff username and password created in the Docker setup to request a token:

```cmd
curl.exe -X POST http://localhost:8000/api/token/ -H "Content-Type: application/json" -d "{\"username\":\"YOUR_STAFF_USERNAME\",\"password\":\"YOUR_STAFF_PASSWORD\"}"
```

Set `ACCESS_TOKEN` to the response's **`access`** value. Use that staff token for the following catalog requests.

Create a venue and note its returned `id`:

```cmd
curl.exe -X POST http://localhost:8000/api/venues/ -H "Authorization: Bearer %ACCESS_TOKEN%" -H "Content-Type: application/json" -d "{\"name\":\"Grand Hall\",\"address\":\"1 Main Street\",\"capacity\":500}"
```

Create an event. Replace `1` with the venue's `id` if it is different, then note the event's returned `id`:

```cmd
curl.exe -X POST http://localhost:8000/api/events/ -H "Authorization: Bearer %ACCESS_TOKEN%" -H "Content-Type: application/json" -d "{\"venue\":1,\"title\":\"Annual Tech Summit\",\"description\":\"A technology conference.\",\"starts_at\":\"2027-11-15T09:00:00Z\",\"capacity\":500}"
```

Create a ticket type. Replace `1` with the event's actual `id`, then note the ticket type's returned `id`:

```cmd
curl.exe -X POST http://localhost:8000/api/ticket-types/ -H "Authorization: Bearer %ACCESS_TOKEN%" -H "Content-Type: application/json" -d "{\"event\":1,\"name\":\"General Admission\",\"price\":\"50.00\",\"capacity\":500}"
```

### 4. Browse the catalog as a customer

Sign in as the customer again by repeating step 2 and resetting `ACCESS_TOKEN` to the customer's access token. Then list events and ticket types:

```cmd
curl.exe http://localhost:8000/api/events/ -H "Authorization: Bearer %ACCESS_TOKEN%"
curl.exe http://localhost:8000/api/ticket-types/ -H "Authorization: Bearer %ACCESS_TOKEN%"
```

Use the event and ticket type `id` values from these responses when creating a reservation.

### 5. Reserve tickets

Replace the example IDs with the IDs from the catalog responses. `event` and `ticket_type` are integer IDs; `quantity` is the number of tickets requested.

```cmd
curl.exe -X POST http://localhost:8000/api/reservations/ -H "Authorization: Bearer %ACCESS_TOKEN%" -H "Content-Type: application/json" -d "{\"event\":1,\"items\":[{\"ticket_type\":1,\"quantity\":2}]}"
```

The response includes the reservation `id` and its ticket lines. Save the reservation ID if you want to cancel it later.

### 6. View or cancel your reservations

List your reservations:

```cmd
curl.exe http://localhost:8000/api/reservations/ -H "Authorization: Bearer %ACCESS_TOKEN%"
```

Cancel a reservation by replacing `1` with its reservation ID:

```cmd
curl.exe -X POST http://localhost:8000/api/reservations/1/cancel/ -H "Authorization: Bearer %ACCESS_TOKEN%"
```

## Linux and macOS shell examples

The API requests are the same in Bash, but use `$ACCESS_TOKEN` rather than `%ACCESS_TOKEN%`:

```bash
export ACCESS_TOKEN="paste-the-access-value-here"
curl http://localhost:8000/api/events/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

For the full endpoint list and request schemas, use Swagger UI at <http://localhost:8000/api/docs/>.

## API reference

All API routes are under `/api/`; there is no `/api/v1/` prefix. Catalog reads require authentication. Authenticated customers can manage only their own reservations; staff can manage all reservations. Only staff can create, update, or delete catalog records.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/register/` | Register a customer |
| `POST` | `/api/token/` | Obtain access and refresh JWTs |
| `POST` | `/api/token/refresh/` | Exchange a refresh JWT for an access JWT |
| `GET`, `POST` | `/api/venues/`, `/api/tags/`, `/api/events/`, `/api/ticket-types/` | Browse or (staff only) create catalog records |
| `GET`, `PUT`, `PATCH`, `DELETE` | Catalog item endpoints, e.g. `/api/events/{id}/` | Retrieve, update, or (staff only) delete a catalog record |
| `GET`, `POST` | `/api/reservations/` | List the current user's reservations or create one |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/reservations/{id}/` | Manage a reservation you own |
| `POST` | `/api/reservations/{id}/cancel/` | Cancel a reservation |
| `GET` | `/health/live/` | Liveness check; does not query the database |
| `GET` | `/health/ready/`, `/health/` | Readiness check; includes database connectivity |
| `GET` | `/api/schema/` | OpenAPI schema |
| `GET` | `/api/docs/` | Swagger UI |
| — | `/admin/` | Django administration |

Validation errors use a consistent JSON envelope:

```json
{
  "error": {
    "code": "…",
    "message": "…",
    "details": {}
  }
}
```

Requests may include `X-Request-ID`. The API returns a valid supplied ID or generates one, and includes it in JSON application logs and Gunicorn access logs.

## Database indexes and constraints

| Model | Index | Why it is useful |
| --- | --- | --- |
| `Event` | `starts_at` | Supports event date filtering and chronological ordering |
| `Event` | `(venue, starts_at)` | Supports listing a venue's events in start-time order |
| `Reservation` | `(user, created_at)` | Supports a user's reservation history, newest first |
| `Reservation` | `(event, status)` | Supports reservation lookups by event and status |

Database constraints also enforce positive capacities and reservation quantities, non-negative ticket prices, and a unique ticket type per reservation. Reservation writes lock the event and ticket type rows to prevent concurrent bookings from exceeding capacity.

## Local development and tests

Docker is the easiest way to run the application with PostgreSQL. For local Python development, use Python 3.12.

Create and activate a virtual environment:

```console
python -m venv .venv
```

Windows Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies and run the app:

```console
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

Without `POSTGRES_HOST`, local development uses SQLite. The concurrency test is skipped on SQLite because `select_for_update` does not provide row locking there. CI runs tests against PostgreSQL.

Run tests with the 90% coverage gate and run the linter:

```console
pytest --cov=apps.core --cov-report=term-missing --cov-fail-under=90
flake8 .
```

## Docker commands

View logs:

```console
docker compose logs -f app
```

Stop the containers but keep database data:

```console
docker compose down
```

Stop the containers and permanently delete the database volume:

```console
docker compose down -v
```

## Project checklist

- [x] Django app with 3+ related models
- [x] CRUD endpoints with authentication and permissions
- [x] Custom error handling with a consistent JSON schema
- [x] Multi-stage Dockerfile
- [x] Docker Compose with PostgreSQL
- [x] Unit tests with at least 90% coverage; CI uses PostgreSQL
- [x] GitHub Actions CI pipeline (lint, test, build)
- [x] `/health/` endpoint
- [x] Swagger/OpenAPI documentation
- [x] README with setup, cURL samples, and index reasoning
