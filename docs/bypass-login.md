# Emergency Bypass Login

When Discord OAuth is unavailable, `BYPASS_DISCORD=true` enables a shared password field on the login page. Successful bypass login creates a full session (same cookies, CSRF, 24-hour expiry) with `ride_coordinator` role.

## How it works

1. On startup, the server upserts a `user_accounts` row for the bypass email with `ride_coordinator` role.
2. The login page fetches `GET /api/auth/bypass/config` to decide whether to show the password field.
3. Submitting the form posts `{password}` to `POST /api/auth/bypass/login`.
4. The backend verifies the password against the stored bcrypt hash and issues session cookies identical to a normal Discord login (24-hour expiry).
5. The browser redirects to `/`.

The login endpoint returns `404` when `BYPASS_DISCORD` is not set, so it is not discoverable in normal operation.

## Setup

### Step 1 — Generate a bcrypt hash

Run this once to produce the value for `BYPASS_PASSWORD`:

```python
from passlib.context import CryptContext
print(CryptContext(schemes=["bcrypt"], deprecated="auto").hash("your-password-here"))
# Example output: $2b$12$abc123...
```

### Step 2 — Set backend environment variables

Add to your `.env.prod` (or `.env.preprod`):

```env
BYPASS_DISCORD=true
BYPASS_PASSWORD=$2b$12$abc123...   # the hash from step 1
# BYPASS_EMAIL=bypass-emergency@local   # optional, this is the default
```

`BYPASS_EMAIL` is the email stored in `user_accounts` for the bypass account. You rarely need to change it.

### Step 3 — Restart the server

On next startup the bypass account row is seeded automatically. No frontend rebuild needed — the login page fetches the config from the backend at runtime.

You can verify the account was created:

```sql
SELECT email, role FROM user_accounts WHERE email = 'bypass-emergency@local';
```

---

## Disabling the bypass

Remove `BYPASS_DISCORD` from the backend env (or set it to `false`) and restart. The password form disappears from the UI automatically and the endpoint returns `404`.

---

## Security notes

- The password is stored only as a bcrypt hash — never in plaintext.
- The login endpoint is not discoverable (`404`) when the feature is off.
- All bypass sessions use the same session infrastructure as Discord OAuth (httpOnly cookie, CSRF token, server-side revocation on logout).
- Sessions expire after **24 hours** (vs 30 days for Discord sessions) — intentionally shorter because this is a shared credential.
- The bypass account has `ride_coordinator` role, not `admin`.
- Rotate the password after the underlying Discord OAuth issue is resolved.
