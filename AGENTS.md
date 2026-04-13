# AGENTS.md

## Repo purpose

`bartiq` is a symbolic quantum resource estimation compiler and analysis library with docs, tutorials, and optional interactive extras.

## Setup prerequisites

- Python 3.10-3.12
- `poetry`
- Graphviz on `PATH` for rendering-related workflows

## Canonical local commands

- Install default environment: `poetry install`
- Install with interactive/optimization extras: `poetry install -E optimization -E interactive -E jupyter`
- Lint/hooks: `poetry install -E jupyter && pre-commit run -a`
- Unit tests (default): `poetry run pytest`
- Unit tests (all extras): `poetry install -E optimization -E interactive && poetry run pytest`
- Type checks: `MYPYPATH=src poetry run mypy src --install-types --non-interactive`
- Docs build: `poetry install --with docs && poetry run mkdocs build`
- Tutorial execution: `poetry install -E jupyter && poetry run jupyter nbconvert --to python docs/tutorials/*.ipynb --execute`

## Validation before handoff

- Run `pre-commit run -a` for normal code changes.
- Run `poetry run pytest` for library changes.
- Run the mypy command when changing typed library code.
- Run `poetry run mkdocs build` when touching docs or `mkdocs.yml`.
- Run tutorial execution when changing tutorial notebooks or notebook-dependent docs.

## Risky or restricted areas

- Keep GitHub Actions and release automation consistent with the existing GitHub workflow model.
- Avoid changing versioning or release files unless the task explicitly requires it.
- Graphviz-dependent features may fail in environments without the binary installed.

## Repo-specific notes for agents

- This repo uses GitHub Actions and an open-source-style toolchain instead of the internal GitLab conventions used by most other repos here.
- Pre-commit uses `isort`, `black`, and `flake8`, not Ruff.
- Prefer small, library-safe changes and keep public API compatibility in mind.
