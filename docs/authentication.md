# Authentication and account management

CampusStack uses Django session authentication. Session cookies are `HttpOnly` and `SameSite=Lax`; cookies are marked `Secure` whenever `DJANGO_DEBUG` is false. Django's CSRF middleware protects unsafe requests. Do not put passwords, cookies, or credentials in application logs.

## CSRF flow

Before any `POST`, fetch `GET /api/v1/auth/csrf/`. It sets the CSRF cookie and returns a masked `csrf_token`. Send that value in the `X-CSRFToken` header on registration, login, logout, and other unsafe session-authenticated requests. Fetch a fresh token after login before the next unsafe request. Missing or invalid CSRF tokens return JSON with status `403`.

For a browser frontend, use same-origin hosting or a same-origin reverse proxy. `CSRF_TRUSTED_ORIGINS` configures Django's CSRF origin checks; it does not enable CORS. Cross-origin frontend hosting needs a separately reviewed CORS configuration.

## Endpoints

### `POST /api/v1/auth/register/student/`

Requires a CSRF token. Example request:

```json
{
  "name": "Riya Student",
  "email": "riya@gvpcew.ac.in",
  "password": "a-strong-password",
  "department": "Computer Science",
  "batch_start_year": 2024,
  "batch_end_year": 2028,
  "admission_date": "2024-08-01",
  "expected_graduation_date": "2028-06-30"
}
```

Returns `201 Created` with `{"user": {...}}`. The user has the `STUDENT` role; request-supplied role fields are ignored. The college domain defaults to `gvpcew.ac.in` and can be configured with `COLLEGE_EMAIL_DOMAIN`. Passwords are checked with Django's configured validators and stored using Django's password hasher.

### `POST /api/v1/auth/register/faculty/`

Requires CSRF. Accepts `name`, `email`, `password`, `department`, and `designation`. Returns the safe user shape with a faculty profile whose `approval_status` is `PENDING`. Request-supplied approval fields are ignored.

### `POST /api/v1/auth/login/`

Requires CSRF. Accepts `email` and `password`. On success, returns `200 OK` with `{"user": {...}}` and starts a Django session. Invalid credentials return `400` and the same `{"detail": "Invalid email or password."}` response whether the email exists or not.

### `POST /api/v1/auth/logout/`

Requires an authenticated session and CSRF. Returns `200 OK` with `{"detail": "Logged out."}` and flushes the session.

### `GET /api/v1/auth/me/`

Requires an authenticated session. Returns `{"user": {...}}` with safe identity fields and the caller's profile. Passwords and password hashes are never serialized.

### `GET /api/v1/auth/csrf/`

Public CSRF bootstrap endpoint. Returns `{"csrf_token": "..."}` and sets the CSRF cookie; the token is required in the header for unsafe requests.

Registration is throttled to 10 requests per hour and login to 10 per minute per client IP. DRF's default local-memory cache is process-local; configure a shared cache before running multiple production workers.

## Administrator provisioning

After applying migrations, create the first administrator from a trusted local terminal:

```powershell
python backend\manage.py createsuperuser
```

Django prompts for email and password. The custom user manager assigns `ADMIN`, `is_staff=True`, and `is_superuser=True`. This is a controlled operator action, not a public API. Faculty approval remains available only through the administrator-checked `approve_faculty_profile` service; there is no public approval endpoint.
