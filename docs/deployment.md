# CampusStack deployment

This guide deploys the Django API to Render, uses Neon PostgreSQL, and publishes the Vite static frontend on Hostinger. Django reads environment variables from the process; it does not load `.env` files. Never commit credentials.

## Required environment variables

Set these on the Render web service. Values marked as examples must be replaced with the actual domains and secret values.

| Variable | Example or rule |
| --- | --- |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Generate a unique, high-entropy value in Render. Required in production. |
| `DJANGO_ALLOWED_HOSTS` | Exact API host, e.g. `campusstack-api.onrender.com` (hostname only; no scheme or path). |
| `DATABASE_URL` | Neon PostgreSQL connection string with SSL. See below. |
| `CORS_ALLOWED_ORIGINS` | Exact Hostinger frontend origin, e.g. `https://your-temporary-domain.example` (scheme included, no path/trailing slash). |
| `CSRF_TRUSTED_ORIGINS` | Separately set to the exact Hostinger origin, e.g. `https://your-temporary-domain.example`. |
| `CROSS_SITE_SESSION_COOKIES` | `True` for the separate Hostinger and Render sites. |
| `COLLEGE_EMAIL_DOMAIN` | Existing college email domain; defaults to `gvpcew.ac.in`. Preserve the institution's configured value. |
| `DB_CONN_MAX_AGE` | Defaults to `0`, suitable for Neon pooled URLs. |
| `SECURE_HSTS_SECONDS` | Defaults to `31536000` in production; keep HTTPS enabled. |

`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, and `POSTGRES_SSLMODE` remain supported for compatibility, but `DATABASE_URL` is the recommended deployment setting. Production startup requires a secret, hosts, explicit CORS and CSRF origins, and PostgreSQL; it does not silently fall back to SQLite.

## Neon PostgreSQL

1. Create a Neon project and database.
2. Copy its PostgreSQL connection URL. Prefer Neon’s pooled connection URL for a web service and keep `sslmode=require` in the URL.
3. Store the complete URL as Render's secret `DATABASE_URL`; do not paste it into Git, docs, a Vite variable, or logs. URL-encode special characters in the username/password.
4. Leave `DB_CONN_MAX_AGE=0` for a pooled endpoint. If deliberately using a direct endpoint, choose a connection lifetime with the database's connection limits in mind.

The configured `dj-database-url` parser uses PostgreSQL and requires SSL for `DATABASE_URL`. Local development continues to use SQLite when `DATABASE_URL` and the legacy `POSTGRES_DB` setting are absent.

## Render Django web service

Create a Python web service for this repository and branch `HEMS` (or the intended deployment branch). The root directory is the repository root.

- Python version: repository `.python-version` pins `3.13.5`.
- Build command: `bash build.sh`.
- Pre-deploy command: `bash predeploy.sh` (applies migrations before the new service version starts).
- Start command: `python -m gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:$PORT`.
- Configure all production variables above before the first deployment. Set `DJANGO_ALLOWED_HOSTS` to the exact Render hostname and use the full HTTPS frontend origin in both origin lists.
- Render terminates TLS; Django trusts its `X-Forwarded-Proto` header, redirects production HTTP to HTTPS, applies secure cookies, and enables HSTS.

Render's pre-deploy command is the preferred place to apply migrations before the new service version starts. Render currently makes this feature available only on paid web-service plans. If the selected plan does not expose a pre-deploy command, do not silently move migrations into the build step: run `python backend/manage.py migrate --noinput` as an explicit release operation before deploying schema-dependent code, or use a plan that supports pre-deploy commands. Take a Neon backup before production schema changes.

The root `build.sh` installs only `backend/requirements.txt` and runs `collectstatic`. The separate root `predeploy.sh` runs migrations. Migrations intentionally do not run during image/build preparation because they modify the live database and should run as a deployment pre-step.

## Hostinger static frontend

1. In a build environment with Node.js/npm, enter `frontend/` and run `npm ci`.
2. Set `VITE_API_BASE_URL` in the build environment to the absolute API URL, for example `https://campusstack-api.onrender.com/api/v1`. This value is compiled into public browser assets; never place secrets in any `VITE_` variable.
3. Run `npm run build`. Confirm the generated `frontend/dist/` contains the landing page and all current pages: login, student and faculty registration, workspace, question, profile, and following.
4. Enable HTTPS for the Hostinger temporary website URL. Upload the **contents** of `frontend/dist/` to the site's document root (commonly `public_html`) using Hostinger File Manager or SFTP. Do not upload `node_modules` or `.env` files.
5. When the frontend hostname changes, update Render's `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to that exact HTTPS origin, then redeploy/restart the API.

The local Vite `/api` proxy remains for development. Production uses the absolute `VITE_API_BASE_URL`; no Vite proxy is involved after static files are uploaded.

## CORS, CSRF, and browser cookies

`CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` are separate, explicit comma-separated origin lists. Set both to the Hostinger origin including `https://`, without a path or trailing slash. Credentialed CORS is enabled only for the listed origins; wildcard origins are rejected. CORS does not replace CSRF, and Django's `CsrfViewMiddleware` and existing endpoint protections remain enabled.

The Hostinger temporary domain and the Render `onrender.com` API are cross-site. Set `CROSS_SITE_SESSION_COOKIES=True`; this gives session and CSRF cookies `SameSite=None; Secure`, which requires HTTPS. The frontend must continue sending credentials and the CSRF header obtained from `GET /api/v1/auth/csrf/`.

Browser privacy controls may block third-party cookies even with correct CORS, `SameSite=None`, and `Secure` settings. In a browser that blocks them, session login will not persist across the Hostinger and Render sites. The reliable remedy is to serve the frontend and API from the same site (for example, reverse-proxy `/api/` under the frontend's custom domain), or use a hosting/domain arrangement browsers treat as first-party. Do not disable CSRF to work around cookie blocking.

## Production verification

After deployment:

1. Confirm the API responds over HTTPS at the expected `onrender.com` hostname and the frontend loads over HTTPS at its Hostinger URL.
2. In browser developer tools, verify the CSRF bootstrap request to `/api/v1/auth/csrf/` returns a token, sets a secure CSRF cookie, and includes `Access-Control-Allow-Origin` for the exact frontend origin plus `Access-Control-Allow-Credentials: true`.
3. Verify student/faculty registration, login, an authenticated `/api/v1/auth/me/` request, and logout. Unsafe requests must send the fresh `X-CSRFToken` and include cookies.
4. Verify the response cookie flags include `Secure`, `HttpOnly` where configured, and `SameSite=None` for cross-site deployment. Test in the browsers the college community uses, including their third-party-cookie settings.
5. Run `python backend/manage.py check --deploy` in the configured Render environment and address any remaining deployment warnings.
6. Confirm migrations are applied and the API is connected to Neon, not SQLite. Do not expose connection strings in diagnostic output.

## Rollback

1. Keep a copy of the previous `frontend/dist/` before uploading a release. To roll back the static site, restore that copy to Hostinger's document root.
2. In Render, redeploy the last known-good commit or use the dashboard's rollback/redeploy controls.
3. Take a Neon backup before schema changes. A code rollback does not reverse database migrations. Prefer forward corrective migrations; restore a database backup only as a deliberate recovery action after assessing data loss.
4. If frontend and API releases are incompatible, restore both to a matching release and verify login/CSRF/session behavior again.
