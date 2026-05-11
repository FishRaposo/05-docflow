DOCKER_COMPOSE := docker compose
PYTHON := python

.PHONY: help install test lint format clean setup dev dev-down migrate seed

help:
	@echo "DocFlow - Available targets:"
	@echo "  install      Install dependencies"
	@echo "  test         Run tests"
	@echo "  lint         Run ruff + mypy"
	@echo "  format       Run ruff format"
	@echo "  clean        Remove build artifacts"
	@echo "  setup        First-time setup"
	@echo "  dev          Start docker compose"
	@echo "  dev-down     Stop docker compose"
	@echo "  migrate      Run alembic migrations"
	@echo "  seed         Ingest sample data"

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v --cov=docflow --cov-report=term-missing

lint:
	ruff check docflow/ tests/ && mypy docflow

format:
	ruff format docflow/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/

setup: install migrate

dev:
	$(DOCKER_COMPOSE) up -d

dev-down:
	$(DOCKER_COMPOSE) down

migrate:
	cd docflow && alembic upgrade head

seed:
	$(PYTHON) -m docflow.admin.cli ingest data/sample/ --source=local
