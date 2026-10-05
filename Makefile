# Research Workbench: one-command local run. The front end is already built (frontend/dist).
install:
	pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $${PORT:-8000}

demo:
	MODE=fixtures uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $${PORT:-8000}

test:
	python -m pytest -q

check:
	python tools/contract_check.py http://localhost:$${PORT:-8000}

.PHONY: install run demo test check
