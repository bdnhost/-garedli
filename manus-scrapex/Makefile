.PHONY: help install dev-install test lint format clean docker-build docker-up docker-down migrate

help:
	@echo "Manus-ScrapeX - Available commands:"
	@echo "  make install        - Install production dependencies"
	@echo "  make dev-install    - Install development dependencies"
	@echo "  make test           - Run tests with coverage"
	@echo "  make lint           - Run linters (flake8, mypy, pylint)"
	@echo "  make format         - Format code (black, isort)"
	@echo "  make clean          - Clean up generated files"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start Docker services"
	@echo "  make docker-down    - Stop Docker services"
	@echo "  make migrate        - Run database migrations"
	@echo "  make run-api        - Run FastAPI server"
	@echo "  make run-worker     - Run Celery worker"
	@echo "  make run-beat       - Run Celery beat scheduler"

install:
	pip install -r requirements.txt
	playwright install chromium

dev-install:
	pip install -r requirements.txt
	pip install -e ".[dev]"
	playwright install chromium
	pre-commit install

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	flake8 src/ tests/
	mypy src/
	pylint src/

format:
	black src/ tests/
	isort src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

migrate:
	alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

run-api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	celery -A src.workers.celery_app worker --loglevel=info

run-beat:
	celery -A src.workers.celery_app beat --loglevel=info

run-flower:
	celery -A src.workers.celery_app flower --port=5555

shell:
	ipython

db-shell:
	psql -h localhost -U scrapex -d scrapex_db
