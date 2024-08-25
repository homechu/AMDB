SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:

MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

test:  ## Run check and test
	poetry run pytest
.PHONY: test

lint-fix:  ## Fix lint
	poetry run isort .
	poetry run black .
.PHONY: lint-fix

typecheck:  ## Run typechecking
	poetry run mypy .
.PHONY: typecheck

clean:  ## Clean cache files
	find . -name '.tox' -type d | xargs rm -rvf
	find . -name '__pycache__' -type d | xargs rm -rvf
	find . -name '.mypy_cache' -type d | xargs rm -rvf
	find . -name '.pytest_cache' -type d | xargs rm -rvf
.PHONY: clean

ci: lint-fix test clean ## Run all checks (lint, typecheck, test)
.PHONY: ci

.DEFAULT_GOAL := help
help: Makefile
	@grep -E '(^[a-zA-Z_-]+:.*?##.*$$)|(^##)' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\[32m##/[33m/'
.PHONY: help
