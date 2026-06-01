SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
UV ?= uv

PY_FILES := $(shell git ls-files --cached --others --exclude-standard '*.py' ':!:out/**' ':!:dist/**' ':!:node_modules/**' ':!:.venv/**')
MYPY_FILES := $(shell git ls-files --cached --others --exclude-standard '*.py' ':!:tests/**' ':!:out/**' ':!:dist/**' ':!:node_modules/**' ':!:.venv/**')
SHELL_FILES := $(shell git ls-files --cached --others --exclude-standard '*.sh')

.PHONY: help lint lint-paths lint-python lint-shell type test check package clean

help:
	@printf "Available targets:\n"
	@printf "  make lint     Run linters and source hygiene checks\n"
	@printf "  make type     Run type checks where typed source exists\n"
	@printf "  make test     Run unit tests and repository hygiene tests\n"
	@printf "  make package  Build the .ankiaddon package\n"
	@printf "  make check    Run lint, type, and test\n"

lint: lint-paths lint-python lint-shell

lint-paths:
	@$(PYTHON) tests/test_repo_hygiene.py --path-only

lint-python:
	@if [ -n "$(PY_FILES)" ]; then \
		$(UV) run --extra dev ruff check $(PY_FILES); \
	else \
		printf "No Python files to lint.\n"; \
	fi

lint-shell:
	@if [ -n "$(SHELL_FILES)" ]; then \
		for file in $(SHELL_FILES); do bash -n "$$file"; done; \
	else \
		printf "No shell files to lint.\n"; \
	fi

type:
	@if [ -n "$(MYPY_FILES)" ]; then \
		$(UV) run --extra dev mypy $(MYPY_FILES); \
	else \
		printf "No Python files to type-check.\n"; \
	fi

test:
	$(PYTHON) -m unittest discover -s tests -v

check: lint type test

package:
	@./scripts/build_ankiaddon.sh

clean:
	@rm -rf dist
