.PHONY: help install install-dev test lint format typecheck clean docker-build docker-up docker-down

PYTHON := python
PIP := pip

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make test         - Run tests with pytest"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Run linters (flake8, isort --check, black --check)"
	@echo "  make format       - Format code with isort and black"
	@echo "  make typecheck    - Run mypy type checker"
	@echo "  make clean        - Remove cache and build artifacts"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start containers"
	@echo "  make docker-down  - Stop containers"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ -v --cov=eruditus --cov-report=term-missing --cov-report=html

lint:
	$(PYTHON) -m flake8 eruditus/
	$(PYTHON) -m isort --check-only eruditus/
	$(PYTHON) -m black --check eruditus/

format:
	$(PYTHON) -m isort eruditus/
	$(PYTHON) -m black eruditus/

typecheck:
	$(PYTHON) -m mypy eruditus/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down
