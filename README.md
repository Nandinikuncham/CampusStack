# CampusStack

CampusStack is a college-specific knowledge-sharing platform for students, faculty, and administrators. This repository starts with a separate static frontend and a Django REST API backend.

## Technology stack

- Frontend: HTML5, Tailwind CSS, vanilla JavaScript
- Backend: Python, Django, Django REST Framework
- Database: PostgreSQL (Neon in deployed environments); SQLite is the local default until PostgreSQL environment variables are supplied
- File storage and AI integrations are planned for later phases and are not dependencies in this foundation.

## Structure

```text
backend/
  manage.py
  config/                 Django settings, URLs, ASGI and WSGI
  apps/
    accounts/             Account and role features (foundation only)
    profiles/             Student and faculty profiles (foundation only)
    academics/            Academic calendar/progression (foundation only)
    audit/                Audit logging (foundation only)
frontend/
  pages/                  HTML pages
  components/             Reusable UI components
  js/                     Vanilla JavaScript modules
  css/                    Tailwind input and generated output
docs/                     Project documentation
```

## Setup (PowerShell)

From the repository root, create and activate a virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Set a development secret key in the current shell before running Django. Do not use a checked-in or committed secret:

```powershell
$env:DJANGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(50))")
$env:DJANGO_DEBUG = "True"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1"
```

SQLite is used when no PostgreSQL settings are provided. To use PostgreSQL (including Neon), set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and optionally `POSTGRES_PORT`/`POSTGRES_SSLMODE` in the process environment. For Neon, use SSL mode `require`. `.env.example` documents these names; Django reads process environment variables directly and does not load `.env` files.

## Development commands

Run from the repository root:

```powershell
python backend\manage.py check
python backend\manage.py migrate
python backend\manage.py runserver
```

The API root namespace is `/api/v1/`. Start Tailwind's watcher from the repository root after installing its CLI in the frontend phase:

```powershell
npx @tailwindcss/cli -i ./frontend/css/input.css -o ./frontend/css/output.css --watch
```

No database models or authentication flows are part of this foundation yet.
