install:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest

test-cov:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=85

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app tests

audit:
	pip-audit -r requirements.txt

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f worker

db:
	docker compose exec postgres psql -U jobhunter -d jobhunter

run-task:
	docker compose exec worker celery -A app.celery_app call app.tasks.fetch_and_process_jobs

quality:
	ruff check .
	ruff format --check .
	mypy app tests
	pytest --cov=app --cov-report=term-missing --cov-fail-under=85
