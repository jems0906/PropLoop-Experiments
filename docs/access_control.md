# Single-team access control

Accounts are invite-only, named, and belong to one installation/team. Roles are
`admin`, `reviewer`, and `member`; no public signup, tenant selection, password
reset, or email delivery is implemented. Share invitations privately out of band.

## Integration contract

- Import `app.auth_models` before using `Base.metadata` in application startup
  and Alembic's environment. Apply migration `0004_team_auth` after
  `0003_controlled_tests`; it creates and seeds `auth_state(id=1)`. Merely calling
  `create_all` is insufficient: tests/development that deliberately bypass
  migrations must insert that singleton once before serving requests. Never
  recreate it in request handlers.
- Mount `app.auth.router` with `app.include_router(router, prefix="/api")`.
- Exported dependencies: `current_user` returns `AuthUser` (401 otherwise);
  `reviewer` permits admin/reviewer (403 otherwise); `admin` permits admin.
  Require `current_user` for application reads, and add
  `Depends(require_same_origin)` to every cookie-authenticated mutation.
  A reviewer dependency alone does **not** add CSRF protection.
- Add settings fields so `BaseSettings` reads environment variables:
  `bootstrap_token: str | None = None` (`BOOTSTRAP_TOKEN`),
  `cookie_secure: bool = False` (`COOKIE_SECURE`),
  `session_ttl_seconds: int = 43200` (`SESSION_TTL_SECONDS`),
  `invite_ttl_seconds: int = 172800` (`INVITE_TTL_SECONDS`).
  These are read using `getattr` until integrated; the auth module itself does
  not separately read `.env`. TTLs are bounded to 60 seconds–30 days.
- Configure credentialed CORS for the exact `frontend_url`, including the
  `X-CSRF-Token` header. Frontend fetches must use `credentials: "include"`.

## HTTP API

All paths below start with `/api/auth`.

| Method/path | Input / result | Authorization |
| --- | --- | --- |
| GET `/status` | Only `{setup_required: bool}` | Public |
| POST `/bootstrap` | `{email,name,password}` → `{user,csrf_token}`, 201 | `X-Bootstrap-Token` |
| POST `/login` | `{email,password}` → `{user,csrf_token}` | Public |
| POST `/logout` | 204; revokes session and clears both cookies | Session + CSRF |
| GET `/me` | `{user,csrf_token}` | Session |
| POST `/invites` | `{email,role?}` → metadata + one-time `token`, 201 | Admin + CSRF |
| GET `/invites` | Metadata array, no token/hash; `?offset=0`, 200/page | Admin |
| POST `/accept-invite` | `{email,name,password,token}` → `{user,csrf_token}`, 201 | Invitation |
| GET `/users` | User array; `?offset=0`, 200/page | Admin |
| PATCH `/users/{id}` | `{role?,active?}` → user | Admin + CSRF |

User JSON: `{id,email,name,role,active,created_at}`. Invitation metadata:
`{id,email,role,created_by,created_at,expires_at,accepted_at}`. Role defaults to
`member` when creating an invite. Email is strictly validated ASCII and stored
lowercase; names are trimmed/nonempty, passwords are 12–128 characters on account
creation (login accepts 1–128). Unexpected fields and explicit null patches are
rejected. Passwords and session/invitation hashes never appear in API results.

## Bootstrap and deployment

Set a high-entropy operator-only `BOOTSTRAP_TOKEN` before initial setup and send it
only via `X-Bootstrap-Token`, never in a URL or frontend build. Without a configured
token bootstrap returns 503. Wrong/missing headers return 403. Database locking of
the seeded singleton makes initial setup atomic: only one admin can be created.
After setup, remove the token from deployment secrets; accounts cannot bootstrap
again, even if they later become inactive. `/status` exposes no bootstrap secret.

In production use HTTPS and `COOKIE_SECURE=true`. Local HTTP development may
use false. Passwords use salted stdlib scrypt (`N=16384,r=8,p=1`); random opaque
session and invite credentials use 256-bit randomness and only SHA-256 hashes
are persisted. Sessions expire server-side as well as through cookie Max-Age.
Changes to role/active revoke all sessions for that user. Atomic serialized
administrator updates cannot demote/deactivate the final active admin.

Session cookie `proploop_session` is HttpOnly, SameSite=Lax, Path=/.
`proploop_csrf` is readable, SameSite=Lax, Path=/, and has the same Secure flag.
For every authenticated mutation send the returned CSRF value in
`X-CSRF-Token`; it must match both the CSRF cookie and the server-side session
secret. Origin, when present, must match configured `frontend_url` or the
externally visible request Host (including port). This permits same-host reverse
proxy deployments even where the backend sees an internal HTTP scheme. Trust
only your reverse proxy, reject unrecognized Host headers at the edge, and do
not configure wildcard origins. Missing Origin is allowed for CLI clients only
in combination with the same cookie/header CSRF proof for protected mutations.
Cross-site fetch metadata is rejected when Origin is absent. Login, bootstrap,
and invitation acceptance require Origin validation when present but do not
require a preexisting session or CSRF token. They reject cross-site fetch metadata
when Origin is absent. No endpoint logs credentials; configure infrastructure
logging to redact auth request bodies, cookies, and secret headers.

Login attempts (including successes) are persisted for 15-minute windows:
10/email, 30/direct peer address, and 100/installation. Exhaustion returns generic
429 with `Retry-After: 900`; invalid email/password, unknown and inactive accounts
all return the same 401 message with equivalent password-hashing work. The global
cap bounds rotating identifiers and bucket growth; expired buckets are cleaned
on login. Behind a proxy, direct peer limiting is intentionally conservative;
do not trust user-supplied forwarded IP headers. This protects a small team, not
a high-volume public identity service. Add an edge limiter for public credential
and invitation routes. Invite reissue expires prior unconsumed invitations.

## Validation

From the repository root in PowerShell:

```powershell
Set-Location backend
& '..\.venv\Scripts\python.exe' -m pytest tests\test_auth.py -q
```

Tests use an isolated custom FastAPI app, overridden SQLite `get_db`, and patched
settings: no `app.main` integration is required. They cover bootstrap races,
role boundaries, final-admin retention, CSRF, hashed credentials, invite replay,
expiration, revocation, strict validation, persisted limits, and migration
upgrade/downgrade.
