# PriceCompare

A full-stack price comparison platform with a FastAPI backend, Next.js frontend, background crawling via Celery, and a full observability stack.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Frontend | Next.js (TypeScript, Tailwind CSS) |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Task Queue | Celery (worker + beat scheduler) |
| Tracing | OpenTelemetry + Jaeger |
| Metrics | Prometheus + Grafana |

## Getting Started

### Prerequisites
- Docker & Docker Compose

### Setup

```bash
cp .env.example .env
# Edit .env with your values
```

### Run

```bash
docker compose up --build
```

Or use the Makefile:

```bash
make up
```

## Services & Ports

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9091 |
| Jaeger UI | http://localhost:16686 |

## Project Structure

```
.
├── backend/        # FastAPI app, Celery workers, Alembic migrations
├── frontend/       # Next.js app
├── grafana/        # Grafana provisioning config
├── otel-collector/ # OpenTelemetry collector config
├── prometheus.yml  # Prometheus scrape config
├── docker-compose.yml
└── Makefile
```

## Environment Variables

See `.env.example` for all available configuration options.
