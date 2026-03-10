.PHONY: build up down restart logs lint dev clean purge-data

build:
	docker compose up --build -d

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down
	docker compose up --build -d

logs:
	docker compose logs -f

lint:
	uv run ruff check backend/

dev:
	uv run uvicorn backend.main:app --reload --port 8000

purge-data:
	rm -rf backend/data/videos/* backend/data/audio/*
	docker volume rm transciber_backend-data 2>/dev/null || true

clean:
	docker compose down -v
	docker image prune -f
