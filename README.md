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
    accounts/             Accounts, session authentication, roles and permissions
    profiles/             Student/faculty profiles and faculty approval
    academics/            Academic calendar and progression
    audit/                Sensitive-action audit logging
    questions/            Questions, tags, answers and comments
frontend/
  index.html             CampusStack landing page
  package.json           Vite scripts and frontend tooling
  vite.config.js         Tailwind integration and Django API proxy
  assets/                Local brand assets
  pages/                  HTML pages
  components/             Reusable UI components
  js/                     Vanilla JavaScript ES modules and API config
  css/                    Tailwind input stylesheet
docs/                     Project documentation
```

## Setup (PowerShell)

From the repository root, create and activate a virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

For stable local sessions, set a development secret key in the current shell. If it is omitted while `DJANGO_DEBUG=True`, Django generates a random, process-local development key. Production must set `DJANGO_DEBUG=False` and supply `DJANGO_SECRET_KEY`; startup fails if the key is missing. Never commit a real secret:

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

The API root namespace is `/api/v1/`. Authentication endpoints and CSRF usage are documented in [docs/authentication.md](docs/authentication.md). Create the first administrator only from a trusted local shell with `python backend\manage.py createsuperuser`; this uses Django's custom manager to assign the `ADMIN` role. There is no public administrator registration.

Questions, tags, answers and comments API behavior is documented in [docs/content-api.md](docs/content-api.md).

## Frontend development

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the landing page locally and proxies browser requests under `/api/` to `http://127.0.0.1:8000` by default. Set `VITE_DJANGO_PROXY_TARGET` in `frontend/.env` to change the Django development server address. `VITE_API_BASE_URL` defaults to `/api/v1`; `frontend/.env.example` lists both frontend settings. Keep credentials out of Vite environment variables because `VITE_` variables are exposed to browser code.

Run a production build or preview it locally with:

```powershell
npm run build
npm run preview
```

Start Django separately from the repository root so the Vite proxy can reach it:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\manage.py migrate
python backend\manage.py runserver 127.0.0.1:8000
```
