PYTHON := venv/bin/python
PIP := venv/bin/pip
LINTER := venv/bin/flake8

setup: venv
	$(PIP) install -q -r requirements.txt -r requirements-dev.txt

venv:
	python3 -m venv venv

test:
	$(PYTHON) -m pytest --cov semforge --cov-fail-under=80

lint:
	$(LINTER) semforge tests

clean:
	rm -rf venv .pytest_cache .coverage

.PHONY: setup test lint clean
