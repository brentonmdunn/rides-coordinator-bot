# Rides Coordinator - Portfolio Example Backend

> **Portfolio Demonstration Backend** - This is a frozen snapshot of the Rides Coordinator backend with hardcoded dummy data for safe portfolio demonstration.

## 🎯 Purpose

This is a **standalone portfolio demo backend** that:
- ✅ Uses **hardcoded dummy data** - no real PII
- ✅ Requires **no Discord bot** or credentials
- ✅ Requires **no database** or external services
- ✅ **Frozen in time** - won't change as main app evolves
- ✅ **Lightweight** - only FastAPI, minimal dependencies
- ✅ **Safe for public deployment** - no sensitive data

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- uv (for dependency management)

### Installation

```bash
# Install dependencies
uv sync

# Run the server
uv run uvicorn api.app:app --reload --port 8001
```

The API will be available at `http://localhost:8001`

### API Documentation

Visit `http://localhost:8001/docs` for interactive API documentation.

## 📡 Available Endpoints

### Ride Management
- `POST /api/list-pickups` - Get pickup locations for Friday/Sunday
- `GET /api/check-pickups/{ride_type}` - Check ride coverage status
- `GET /api/check-pickups/driver-reactions/{day}` - Get driver emoji reactions
- `POST /api/group-rides` - Get ride groupings
- `POST /api/check-pickups/sync` - Mock sync (returns success)

### Feature Management
- `GET /api/feature-flags` - List all feature flags
- `PUT /api/feature-flags/{feature_name}` - Toggle feature flag (mock - not persisted)

### Status
- `GET /api/ask-rides/status` - Get scheduled job status
- `GET /api/health` - Health check

## 📦 Dummy Data

All responses use hardcoded data from `api/dummy_data.py`:
- **Users**: Fictional names (Alice Johnson, Bob Smith, etc.)
- **Discord Usernames**: Made-up handles (alice_tech, bob_codes, etc.)
- **Locations**: Generic names (Maple Hall, Oak Building, etc.)
- **No real PII** - completely safe for public demonstration

## 🌐 Serving Frontend

To serve the example frontend:

```bash
# Build the example-frontend
cd ../example-frontend
npm run build

# Copy build to backend
cp -r dist ../example-backend/admin_ui

# Run backend (it will serve the frontend)
cd ../example-backend
uv run uvicorn api.app:app --port 8001
```

Visit `http://localhost:8001` to see the full app.

## 🚢 Deployment

This backend can be deployed to any platform that supports Python:
- **Railway**: `railway up`
- **Render**: Connect to GitHub and deploy
- **Fly.io**: `fly deploy`
- **Heroku**: `git push heroku main`

Just make sure to set the port appropriately (most platforms use `PORT` env var).

## 🔒 What's Different from Main App?

| Feature | Main App | Example Backend |
|---------|----------|-----------------|
| Discord Bot | ✅ Full integration | ❌ Removed |
| Database | ✅ PostgreSQL | ❌ Not needed |
| Authentication | ✅ Cloudflare Access | ❌ Open access |
| Data Source | ✅ Real Discord | ✅ Hardcoded JSON |
| Dependencies | ~20 packages | 3 packages |
| Persistence | ✅ Saves changes | ❌ Stateless |

## 📝 License

Same as main project.
