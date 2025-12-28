# Frontend Environment Configuration

This project uses environment-specific configuration for API endpoints.

## Environment Files

- `.env.development` - Used during development (`npm run dev`)
- `.env.production` - Used during production builds (`npm run build`)

## Development Mode

In development, the frontend runs on Vite dev server (port 5173/5174) and the backend runs separately on port 8000.

**`.env.development`**:
```
VITE_API_URL=http://localhost:8000
```

This tells the frontend to make API calls to `http://localhost:8000`.

## Production Mode

In production, the backend serves the frontend static files from `admin_ui/`, so both run on the same origin (no CORS needed).

**`.env.production`**:
```
# No VITE_API_URL needed - uses same origin
```

When `VITE_API_URL` is not set, API calls use relative URLs (same origin).

## Using the API

Import the API utilities from `lib/api.ts`:

```typescript
import { apiFetch, getApiUrl } from './lib/api'

// Simple fetch wrapper
const response = await apiFetch('/api/hello')
const data = await response.json()

// Or get the URL manually
const url = getApiUrl('/api/discord/send-message')
fetch(url, { method: 'POST' })
```

The utilities automatically handle environment-specific URLs:
- **Dev**: `http://localhost:8000/api/hello`
- **Prod**: `/api/hello` (same origin)
