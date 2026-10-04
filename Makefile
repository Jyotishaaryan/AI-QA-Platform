.PHONY: install run run-ui test lint format docker-up docker-down
install:
	python -m pip install -e '.[dev]'
run:
	uvicorn app.main:app --reload
run-ui:
	streamlit run streamlit_app.py
test:
	pytest
lint:
	ruff check .
format:
	ruff format .
docker-up:
	docker compose up --build
docker-down:
	docker compose down
