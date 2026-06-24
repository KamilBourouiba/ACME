.PHONY: install up down dev test demo health

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cp -n .env.example .env || true

up:
	docker compose up -d

down:
	docker compose down

dev:
	PYTHONPATH=. .venv/bin/uvicorn acme.main:app --reload --host 0.0.0.0 --port 8000

test:
	PYTHONPATH=. .venv/bin/pytest tests/ -q --ignore=tests/test_ollama_live.py --ignore=tests/test_integration.py

test-integration:
	RUN_INTEGRATION=1 PYTHONPATH=. .venv/bin/pytest tests/test_integration.py -v

demo:
	PYTHONPATH=. .venv/bin/python scripts/demo.py

health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
