# Rides Coordinator - Portfolio Example Frontend

> **Portfolio Demonstration Frontend** - This is a frozen snapshot of the Rides Coordinator frontend configured to work with the example backend.

## 🎯 Purpose

This is a **standalone portfolio demo frontend** that:
- ✅ Points to the **example-backend** (port 8001)
- ✅ Shows all features working with **dummy data**
- ✅ **Frozen in time** - represents current feature set
- ✅ **Safe for public deployment** - no real PII displayed
- ✅ Runs on **port 5175** to avoid conflicts with main frontend

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Create .env.local file
echo "VITE_API_URL=http://localhost:8001" > .env.local

# Run the development server
npm run dev
```

The app will be available at `http://localhost:5175`

### Make sure the example-backend is running!

```bash
# In another terminal
cd ../example-backend
uv run uvicorn api.app:app --reload --port 8001
```

## 🎨 Features

All features work exactly like the main frontend, but with dummy data:

- **📍 Pickup Locations** - View pickup locations for Friday/Sunday rides
- **✅ Ride Coverage Check** - See which users have rides assigned
- **😊 Driver Reactions** - View emoji reactions from drivers
- **🚗 Group Rides** - See automated ride groupings
- **🎛️ Feature Flags** - Toggle feature flags (mock - doesn't persist)
- **📅 Ask Rides Dashboard** - View scheduled job status

## 🌐 Building for Production

```bash
# Build the frontend
npm run build

# The built files will be in dist/
# Copy them to the example-backend to serve as a single app:
cp -r dist ../example-backend/admin_ui

# Then run the backend which will serve the frontend
cd ../example-backend
uv run uvicorn api.app:app --port 8001

# Visit http://localhost:8001 to see the full app
```

## 🚢 Deployment

### Option 1: Deploy with Backend (Recommended)
1. Build the frontend: `npm run build`
2. Copy to backend: `cp -r dist ../example-backend/admin_ui`
3. Deploy the backend (which serves the frontend)

### Option 2: Deploy Separately
- Deploy frontend to **Vercel/Netlify**
- Deploy backend to **Railway/Render**
- Set `VITE_API_URL` environment variable to point to backend URL

## 🔒 Configuration

### Environment Variables

Create a `.env.local` file:

```bash
# Point to example backend
VITE_API_URL=http://localhost:8001

# For production deployment (if deploying separately):
# VITE_API_URL=https://your-example-backend.railway.app
```

## 📝 What's Different from Main Frontend?

| Feature | Main Frontend | Example Frontend |
|---------|---------------|------------------|
| Backend URL | http://localhost:8000 | http://localhost:8001 |
| Dev Port | 5173 | 5175 |
| Data Source | Real Discord (via backend) | Hardcoded dummy data |
| Purpose | Production app | Portfolio demo |

## 🧪 Testing

All components should work identically to the main frontend. Test:
- ✅ All widgets load and display data
- ✅ Feature flag toggling (shows as success)
- ✅ Ride grouping with different capacities
- ✅ Coverage check shows mix of assigned/unassigned users
- ✅ No errors in browser console

## 📝 License

Same as main project.
