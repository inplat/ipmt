.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

VENV_EXISTS=$(shell [ -e .venv ] && echo 1 || echo 0 )
VENV_BIN=.venv/bin
VERSION=$(shell $(VENV_BIN)/python run.py version)
BROWSER := $(VENV_BIN)/python -c "$$BROWSER_PYSCRIPT"

.PHONY: clean
clean: clean-pyc clean-venv clean-test clean-build ## Remove all file artifacts and latest docker images

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec sudo rm -fr {} +

.PHONY: clean-venv
clean-venv:
	-rm -rf .venv

.PHONY: clean-test
clean-test: ## remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .cache

.PHONY: clean-build
clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: venv
venv: ## Create virtualenv directory and install all requirements
ifeq ($(VENV_EXISTS), 1)
	@echo virtual env already initialized
else
	virtualenv -p python3.6 .venv
	poetry install
endif

.PHONY: lint
lint: venv ## check style with flake8
	poetry run flake8 --exclude=ipmt/compat.py ipmt tests

.PHONY: test
test: venv lint ## run tests
	poetry run pytest -v -s

.PHONY: coverage
coverage-quiet: venv ## check code coverage
	poetry run pytest --cov-report html --cov=ipmt tests/

.PHONY: coverage
coverage: coverage-quiet ## check code coverage and open report in default browser
	$(BROWSER) htmlcov/index.html

.PHONY: docs-quiet
docs-quiet: venv ## generate Sphinx HTML documentation, including API docs
	rm -f docs/ipmt.rst
	rm -f docs/modules.rst
	$(VENV_BIN)/sphinx-apidoc -o docs/ ipmt
	$(MAKE) -C docs clean
	$(MAKE) -C docs html

.PHONY: docs
docs: docs-quiet ## generate Sphinx HTML documentation, including API docs and open it in default browser
	$(BROWSER) docs/_build/html/index.html

.PHONY: servedocs
servedocs: docs ## compile the docs watching for changes
	$(VENV_BIN)/watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .

.PHONY: dist
dist: venv ## builds source and wheel package
	poetry build

.PHONY: install
install: clean ## install the package to the active Python's site-packages
	poetry install

.PHONY: release
release: venv lint test ## package and upload a release
	poetry publish

.PHONY: help
help:  ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-23s\033[0m %s\n", $$1, $$2}'
