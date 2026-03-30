.PHONY: up down build logs migrate worker shell-backend

## Start all services
up:
	docker compose up -d

## Start in foreground (shows all logs)
up-fg:
	docker compose up

## Stop all services
down:
	docker compose down

## Rebuild images
build:
	docker compose build --no-cache

## View logs (all services)
logs:
	docker compose logs -f

## View backend logs only
logs-backend:
	docker compose logs -f backend worker beat

## Run Alembic migrations
migrate:
	docker compose exec backend alembic upgrade head

## Create a new Alembic migration
migration:
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

## Open a Python shell in the backend container
shell-backend:
	docker compose exec backend python

## Open psql
shell-db:
	docker compose exec db psql -U postgres pricecompare

## Run a one-off crawl (example)
crawl:
	curl -s -X POST http://localhost:8000/api/v1/crawl \
		-H "Content-Type: application/json" \
		-d '{"query": "$(q)"}' | python3 -m json.tool

## Tail Celery worker
worker:
	docker compose exec worker celery -A app.workers.celery_app inspect active

## Status check
status:
	@echo "=== Services ==="
	@docker compose ps
	@echo "\n=== Backend health ==="
	@curl -s http://localhost:8000/health | python3 -m json.tool

## URLs
urls:
	@echo "Frontend:       http://localhost:3000"
	@echo "API docs:       http://localhost:8000/api/docs"
	@echo "Jaeger UI:      http://localhost:16686"
	@echo "Grafana:        http://localhost:3001  (admin/admin)"
	@echo "Prometheus:     http://localhost:9091"
