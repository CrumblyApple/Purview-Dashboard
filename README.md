# Purview Dashboard

React (Vite + TypeScript) frontend and Python (FastAPI) backend with REST communication and Docker support.

## Project structure

```
├── backend/          # FastAPI REST API (port 8000)
├── frontend/         # React SPA (port 5173 in dev, 3000 in Docker prod)
├── scripts/          # Convenience dev runners
├── docker-compose.yml
└── package.json      # Run both services with one command
```

## Prerequisites

- **Node.js** 20+ and npm
- **Python** 3.12+
- **Docker** (optional, for containerized runs)

## Quick start (local dev)

Install dependencies once:

```bash
npm run install:all
```

Start both frontend and backend with hot reload:

```bash
npm run dev
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| Backend  | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

On Windows you can also run:

```powershell
.\scripts\dev.ps1
```

The sample UI calls `GET /api/health` and `GET /api/hello` to verify REST connectivity.

## Docker

**Production-style build** (nginx + API):

```bash
npm run docker:up
# or: docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |

**Development with hot reload in containers:**

```bash
npm run docker:dev
```

Frontend: http://localhost:5173 — API requests are proxied to the backend container.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/hello?name=` | Sample greeting |
| GET | `/docs` | OpenAPI (Swagger) UI |

## REST communication

- **Local dev:** Vite proxies `/api/*` to `http://127.0.0.1:8000`.
- **Docker prod:** nginx proxies `/api/*` to the `backend` service.
- **Frontend client:** `frontend/src/api/client.ts` uses `VITE_API_BASE_URL` (default `/api`).

## Scripts reference

| Command | Description |
|---------|-------------|
| `npm run dev` | Backend + frontend concurrently |
| `npm run install:all` | Install root, frontend, and Python deps |
| `npm run docker:up` | Docker Compose (production build) |
| `npm run docker:dev` | Docker Compose with hot reload |
