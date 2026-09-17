.PHONY: install run test seed backup
install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
run:
	.venv/bin/uvicorn app.main:app --reload
test:
	.venv/bin/pytest -q
seed:
	.venv/bin/python -m scripts.seed_demo
backup:
	docker compose --profile backup run --rm backup
