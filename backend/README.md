# Flowline Traffic Optimization System - FastAPI Backend

Production-ready FastAPI backend foundation for the Traffic Optimization System.

---

## Architecture Overview

The backend is structured into modular layers designed for high maintainability, strict typing, and clean domain separation:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application factory, CORS, and root endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # Pydantic BaseSettings (CORS, prefixes, env configuration)
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── api.py           # Top-level API router aggregator
│           └── endpoints/
│               ├── __init__.py
│               ├── health.py        # GET /api/health (Service operational check)
│               ├── traffic.py       # GET /api/traffic (Network telemetry & congestion)
│               ├── vehicles.py      # GET /api/vehicles (Fleet tracking)
│               ├── routes.py        # GET /api/routes (Route generation & shortest paths)
│               ├── optimization.py  # GET /api/optimization (QUBO problem & solvers)
│               ├── zones.py         # GET /api/zones (Zonal clustering & parallel graph solving)
│               └── priority.py      # GET /api/priority (Emergency weights & fleet rules)
├── main.py                      # Application entrypoint for uvicorn
├── requirements.txt             # Python dependencies
└── README.md                    # Backend documentation
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10 or higher (Tested on Python 3.11, 3.12, 3.13, and 3.14)
- `pip` package manager

### 2. Environment Setup (Recommended)
Navigate into the `backend/` directory:

```bash
cd backend
```

Create and activate a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
Install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## Running the Server

Start the development server with live reload enabled:

```bash
uvicorn main:app --reload
```

The server will initialize on:
`http://127.0.0.1:8000`

---

## Interactive API Documentation

Once the server is running, explore and test the API using the built-in documentation:
- **Swagger UI (Interactive)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc (Detailed Specifications)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema**: [http://127.0.0.1:8000/api/openapi.json](http://127.0.0.1:8000/api/openapi.json)

---

## Available Endpoints

### System Endpoints
| Method | Endpoint | Description | Sample Response |
|---|---|---|---|
| `GET` | `/` | Root service descriptor | `{"name": "...", "version": "0.1.0", "docs": "/docs"}` |
| `GET` | `/api/health` | Operational health check | `{"status": "ok", "service": "traffic-optimization-backend"}` |

### Domain Module Placeholders
| Method | Endpoint | Module Tag | Purpose |
|---|---|---|---|
| `GET` | `/api/traffic` | `traffic` | Road network conditions & congestion detection |
| `GET` | `/api/vehicles` | `vehicles` | Active vehicle telemetry and tracking |
| `GET` | `/api/routes` | `routes` | Candidate path generation & shortest path dispatch |
| `GET` | `/api/optimization`| `optimization`| QUBO formulation & quantum-inspired solvers |
| `GET` | `/api/zones` | `zones` | Sub-graph partitioning & parallel zonal solving |
| `GET` | `/api/priority` | `priority` | Priority fleet rules & emergency weight calibration |

---

## CORS Configuration

Cross-Origin Resource Sharing (CORS) is pre-configured in `app/core/config.py` to allow seamless communication with the Next.js frontend:
- `http://localhost:3000` (Local Next.js dev server)
- `http://127.0.0.1:3000`
- `http://localhost:8000` / `http://127.0.0.1:8000`
- `https://traffic-optimization-system.onrender.com` (Production deployment)

Origins can also be customized via an optional `.env` file using the `BACKEND_CORS_ORIGINS` variable.
