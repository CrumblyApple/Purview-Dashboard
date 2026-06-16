# Purview Dashboard



## Prerequisites

- **Node.js** 20+ and npm
- **Python** 3.12+
- **Docker** (optional, for containerized runs)

## System dependencies

```bash
sudo apt install osmium-tool gdal-bin
```

Required for OSM feature extraction and COG generation.

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


## Scripts reference

| Command | Description |
|---------|-------------|
| `npm run dev` | Backend + frontend concurrently |
| `npm run install:all` | Install root, frontend, and Python deps |
| `npm run docker:up` | Docker Compose (production build) |
| `npm run docker:dev` | Docker Compose with hot reload |


## In development

Convolutional Neural Network for dasymetric mapping will eventually replace the existing G-NAF implementation. A forecasting model is planned for future development.