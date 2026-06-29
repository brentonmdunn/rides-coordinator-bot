# Rides Coordinator Bot - Frontend

[![React](https://img.shields.io/badge/react-19-blue.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/vite-7-yellow.svg)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/tailwindcss-4-sky.svg)](https://tailwindcss.com/)

The frontend is a Single Page Application (SPA) built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS v4**. It serves as the dashboard for managing rides and events.

## Setup & Installation

### Prerequisites
- Node.js (v18+)
- npm

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables:
   ```bash
   cp .env.development .env.development.local
   # Edit with your local API URL if needed
   ```

## Development

Start the development server with hot reload:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### Linting & Type Checking

```bash
npm run lint        # ESLint
npx tsc --noEmit    # TypeScript type check
```

## Building for Production

```bash
npm run build
```

Output is written to `dist/`. See [ENV_CONFIG.md](ENV_CONFIG.md) for environment variable configuration.
