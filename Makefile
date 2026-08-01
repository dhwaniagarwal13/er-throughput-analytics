PY := .venv/Scripts/python.exe
DBT := .venv/Scripts/dbt.exe
DBT_FLAGS := --project-dir dbt --profiles-dir dbt

# Absolute repo root. dbt models resolve the raw CSV path against it (see
# stg_er_visits.sql) so the warehouse can be built from any working directory,
# not just from inside dbt/.
export ER_ROOT := $(CURDIR)

.PHONY: help install ingest profile build test export app lint clean all

help:
	@echo "make install    create venv and install deps"
	@echo "make ingest     fetch the Kaggle ER dataset into data/raw/"
	@echo "make profile    print a data-quality profile of the raw CSV"
	@echo "make build      run dbt models into data/er.duckdb"
	@echo "make test       run dbt tests + pytest"
	@echo "make export     write data/exports/*.csv for Power BI"
	@echo "make app        launch the Streamlit dashboard"
	@echo "make lint       ruff check"
	@echo "make all        ingest + build + test + export"
	@echo "make clean      drop the warehouse and exports (keeps raw cache)"

install:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

ingest:
	$(PY) -m erops.ingest

profile:
	$(PY) -m erops.profile

build:
	$(DBT) run $(DBT_FLAGS)

test:
	$(DBT) test $(DBT_FLAGS)
	$(PY) -m pytest -q

export:
	$(PY) -m erops.export_dashboard

app:
	$(PY) -m streamlit run app/streamlit_app.py

lint:
	$(PY) -m ruff check src app tests

all: ingest build test export

clean:
	rm -f data/er.duckdb data/er.duckdb.wal
	rm -f data/exports/*.csv
	rm -rf dbt/target dbt/logs
