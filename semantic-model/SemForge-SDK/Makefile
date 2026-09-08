PYTHON := venv/bin/python
PIP := venv/bin/pip
LINTER := venv/bin/flake8

setup: venv
	$(PIP) install -q -r requirements.txt -r requirements-dev.txt
	# Editable install so `semforge` imports regardless of the working
	# directory. The language server is launched with the folder the user
	# opened as its cwd, so an uninstalled package fails there while working
	# fine from a terminal inside this directory.
	$(PIP) install -q -e .

venv:
	python3 -m venv venv

test:
	$(PYTHON) -m pytest --cov semforge --cov-fail-under=80

lint:
	$(LINTER) semforge tests

clean:
	rm -rf venv .pytest_cache .coverage

.PHONY: setup test lint clean
