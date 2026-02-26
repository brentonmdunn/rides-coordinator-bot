# Role-Based Access Control (RBAC)

This document outlines how Role-Based Access Control is enforced across the backend API and the React frontend.

## Roles

The system has three established roles in the database (defined in `bot/core/enums.py -> AccountRoles`):
1. **Admin** (`admin`): Full access to everything, including user management and global feature flags.
2. **Ride Coordinator** (`ride_coordinator`): Can trigger manual sends and pause/resume automated scheduled jobs.
3. **Viewer** (`viewer`): Default role on first login. Can view all data on the dashboard (read-only).

---

## Backend Implementation

The backend enforces RBAC at the route level using FastAPI dependency injection. The core logic lives in `api/auth.py`.

### Protecting a Route

To restrict an API route to a specific role (or higher), import the appropriate dependency from `api/auth.py` and add it to the router or the specific endpoint's `dependencies` list.

**Example: Admin Only Route**
```python
from fastapi import APIRouter, Depends
from api.auth import require_admin

# Apply to a single route
@router.get("/api/admin/stats", dependencies=[Depends(require_admin)])
async def get_stats():
    ...

# Or apply to an entire router
router = APIRouter(dependencies=[Depends(require_admin)])
```

**Example: Ride Coordinator (or Admin) Route**
```python
from fastapi import APIRouter, Depends
from api.auth import require_ride_coordinator

@router.post("/api/rides/send", dependencies=[Depends(require_ride_coordinator)])
async def send_rides():
    ...
```

### How it Works
- `require_admin` ensures the user is `AccountRoles.ADMIN`.
- `require_ride_coordinator` ensures the user is `AccountRoles.RIDE_COORDINATOR` **OR HIGHER** (so Admins automatically pass this check).
- The hierarchy is defined in `UserAccountsService.ROLE_LEVELS`. 
  - `admin` = 3
  - `ride_coordinator` = 2
  - `viewer` = 1

---

## Frontend Implementation

The frontend enforces RBAC by conditionally rendering UI elements based on the current user's role. It does **not** rely on frontend checks for security (the backend APIs will reject unauthorized requests), but rather for UX (hiding buttons the user can't use).

### Checking the Current User's Role

The current user's data, including their role, is fetched from the `/api/me` endpoint. This data is usually queries at the top of a page (like `Home.tsx`) using React Query.

```tsx
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { AccountRole } from '../types'

const { data: meData } = useQuery<{ email: string; role: AccountRole; is_local: boolean }>({
    queryKey: ['me'],
    queryFn: async () => {
        const res = await apiFetch('/api/me')
        return res.json()
    },
})

// Derive boolean flags for rendering logic
const role = meData?.role ?? 'viewer'
const isAdmin = role === 'admin'
const canManage = role === 'admin' || role === 'ride_coordinator'
```

### Hiding UI Elements

Pass the boolean flags (`isAdmin`, `canManage`) as props to child components that need to hide specific actions.

**Example: Hiding an Admin Section**
```tsx
{isAdmin && <UserManagement />}
```

**Example: Disabling or Hiding a Button**
```tsx
interface Props {
  canManage: boolean
}

function Controls({ canManage }: Props) {
    if (!canManage) return null // Hide entirely
    
    return <button>Send Now</button>
}
```

---

## Local Development (Testing Roles)

When running locally (`APP_ENV=local`), the authentication flow is bypassed. 

1. **Auto-Admin**: The default local user (`dev@example.com`) is automatically seeded as an Admin on startup.
2. **Role Switcher**: The UI includes a "Dev Mode" dropdown banner at the top of the screen that allows you to instantly switch your role between Admin, Ride Coordinator, and Viewer to test different UI states without restarting the app.
