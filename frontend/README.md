# Rides Coordinator Bot - Frontend

[![React](https://img.shields.io/badge/react-18-blue.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/vite-6-yellow.svg)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/tailwindcss-3-sky.svg)](https://tailwindcss.com/)

The frontend is a Single Page Application (SPA) built with **React**, **TypeScript**, **Vite**, and **TailwindCSS**. It serves as the dashboard for managing rides and events.

## 🚀 Setup & Installation

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

3. Create environment file (if required):
   ```bash
   cp .env.example .env
   ```

## 🛠️ Development

### Running the Dev Server
Start the development server with hot reload:

```bash
npm run dev
```

The app will generally be available at `http://localhost:5173`.

### Linting
Lint the codebase using ESLint:

```bash
npm run lint
```

## 📦 Building for Production

To build the application for production (which outputs to `dist/`):

```bash
npm run build
```

This build artifact is typically served by the backend API or a dedicated static site host.
