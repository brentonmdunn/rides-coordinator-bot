# Portfolio Demo - Rides Coordinator

This repository contains a **frozen portfolio demonstration** of the Rides Coordinator application, separate from the main production app.

## 📂 Directory Structure

```
rides-coordinator-bot/
├── backend/              # Main production backend (continues to evolve)
├── frontend/             # Main production frontend (continues to evolve)
├── example-backend/      # 🎯 Portfolio demo backend (frozen snapshot)
├── example-frontend/     # 🎯 Portfolio demo frontend (frozen snapshot)
└── PORTFOLIO.md          # This file
```

## 🎯 Purpose

The `example-backend` and `example-frontend` directories are **standalone portfolio demonstrations** that:

- ✅ Use **hardcoded dummy data** - absolutely no real PII
- ✅ Work **independently** from the main app
- ✅ Are **frozen in time** - won't break as main app evolves
- ✅ Require **no Discord credentials** or external services
- ✅ Are **safe for public deployment** and showcasing
- ✅ Show **all current features** of the application

## 🚀 Quick Start (Local Development)

### 1. Start the Example Backend

```bash
cd example-backend

# Install dependencies (first time only)
uv sync

# Run the backend
uv run uvicorn api.app:app --reload --port 8001
```

Backend will be available at `http://localhost:8001`

### 2. Start the Example Frontend

```bash
cd example-frontend

# Install dependencies (first time only)
npm install

# Create environment file (first time only)
echo "VITE_API_URL=http://localhost:8001" > .env.local

# Run the frontend
npm run dev
```

Frontend will be available at `http://localhost:5175`

### 3. Use the App

Visit `http://localhost:5175` and explore:
- **Pickup Locations** - See dummy pickup points for Friday/Sunday
- **Ride Coverage** - View assignment status for dummy users
- **Driver Reactions** - See emoji reactions from drivers
- **Group Rides** - See automated ride groupings
- **Feature Flags** - Toggle features (mock - doesn't persist)
- **Ask Rides Status** - View scheduled job status

## 🌐 Deployment Options

### Option 1: All-in-One Deployment (Recommended for Portfolio)

Deploy backend and frontend as a single application:

```bash
# Build the frontend
cd example-frontend
npm run build

# Copy build to backend
cp -r dist ../example-backend/admin_ui

# Deploy the backend (which serves the frontend)
cd ../example-backend
# Deploy to Railway, Render, Fly.io, etc.
```

**Platforms:**
- **Railway**: Connect GitHub repo, set start command to `uv run uvicorn api.app:app --host 0.0.0.0 --port $PORT`
- **Render**: Create Web Service, use command `uv run uvicorn api.app:app --host 0.0.0.0 --port $PORT`
- **Fly.io**: `fly launch` and follow prompts

### Option 2: Separate Deployment

Deploy frontend and backend separately:

**Frontend** (Vercel/Netlify):
```bash
cd example-frontend
# Set VITE_API_URL to your backend URL in platform settings
# Deploy dist/ folder
```

**Backend** (Railway/Render):
```bash
cd example-backend
# Deploy as web service
```

## 🔒 Why Separate from Main App?

| Aspect | Main App | Portfolio Demo |
|--------|----------|----------------|
| **Data** | Real Discord messages & users | Hardcoded fictional data |
| **Dependencies** | Discord bot, PostgreSQL, Redis | Only FastAPI + Uvicorn |
| **Authentication** | Cloudflare Access required | Open access |
| **Stability** | Evolves with new features | Frozen snapshot |
| **Purpose** | Production use | Portfolio demonstration |
| **PII Risk** | Contains real PII | Zero PII |

## 📊 Dummy Data

All data in the portfolio demo is completely fictional:

- **Names**: Alice Johnson, Bob Smith, Carol Williams, etc.
- **Usernames**: alice_tech, bob_codes, carol_data, etc.
- **Locations**: Maple Hall, Oak Building, Pine Apartments, etc.
- **No real Discord data** or personally identifiable information

## 🔧 Maintenance

The example directories are **intentionally frozen**. To update them:

1. Only update if there's a significant feature you want to showcase
2. Manually copy relevant files from `backend/` and `frontend/`
3. Ensure all data remains hardcoded and contains no PII
4. Test thoroughly before deploying

**Note**: Regular development continues in `backend/` and `frontend/` - the example directories won't automatically update.

## 📝 Documentation

- [Example Backend README](./example-backend/README.md) - Backend setup and API documentation
- [Example Frontend README](./example-frontend/README.md) - Frontend setup and features

## 🎥 Live Demo

*Add your deployed demo URL here once deployed*

Example: `https://rides-coordinator-demo.railway.app`

## 📧 Questions?

This portfolio demo is safe to share publicly, deploy anywhere, and use for job applications or showcasing your work.

---

**Tip**: When showcasing to potential employers or on your portfolio site, emphasize:
- Full-stack development (React + FastAPI)
- Clean architecture with separation of concerns
- Responsive design and modern UI
- RESTful API design
- Safe data handling and privacy considerations
