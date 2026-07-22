.PHONY: help sync build up down clean

help:
	@echo "Available targets:"
	@echo "  make sync          - Sync dependencies for each service using its own pyproject.toml"
	@echo "  make build         - Build all Docker images via docker-compose"
	@echo "  make up            - Start local containers with docker-compose"
	@echo "  make down          - Stop local containers"
	@echo "  make clean         - Remove service virtualenvs (.venv)"

sync:
	cd api_backend && uv sync
	cd mcp_server && uv sync
	cd mcp_agent && uv sync

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

clean:
	rm -rf api_backend/.venv mcp_server/.venv mcp_agent/.venv
