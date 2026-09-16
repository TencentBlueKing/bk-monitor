# AGENTS

## Project At A Glance
- `bk-monitor-base` is the foundational capability layer of BlueKing Monitor, exposing space management, data collection, and metadata services to upstream SaaS apps.
- This is a Python 3.11 project.
- Source lives under `src/bk_monitor_base`; Typer CLI (`bk-monitor-base-cli`) launches operational scripts, while Django + Celery supply APIs and background jobs backed by Kafka/Redis/Elasticsearch.
- Runtime dependencies are declared in `pyproject.toml`, version-locked via `uv.lock`, and target Python 3.11.
- `docs/` contains architecture, development, and testing guides; `scripts/` hosts operational helpers; `config.yaml` demonstrates configuration structure—never commit real secrets.
- Use Chinese in comments, commits, and PRs—English supplements are welcome.

## Directory Map
- `src/bk_monitor_base/domains`: Business-domain services (space, collection, metadata, etc.).
- `src/bk_monitor_base/infras`: Infrastructure primitives (databases, cache, logging, async tooling).
- `src/bk_monitor_base/config`: `pydantic-settings` models that read from YAML and environment variables.
- `src/bk_monitor_base/cli`: Typer commands for recurrent management workflows.
- `src/bk_monitor_base/tests`: Pytest suites that follow the `test_*.py` naming convention.
- `docs/architecture`, `docs/development`: High-level references that must be updated alongside behavior changes.

## Tech Stack & Quality Baseline
- Web & task layer: Django `<5` plus Celery `5.4`, with `django-celery-beat/results` for scheduling and persistence.
- Messaging & data: Kafka (`kafka-python`), Redis (`django-redis`), and Elasticsearch 5/6/7 client compatibility.
- Config & validation: `pydantic` v2, `pydantic-settings`, `blue-krill`, `bkstorages`, `pycryptodome`.
- Tooling: `uv` for dependency/runtime orchestration, `ruff` for style + lint, `basedpyright` for typing, `pytest` + `pytest-django` + `pytest-cov` for tests.
- Observability: `django-prometheus` exports metrics; complex logic blocks must emit structured logs with context IDs (e.g., `space_id`, `collector_id`).
- **Code Documentation & Type Annotations**: All code must include appropriate type annotations for function parameters, return values, and class attributes. Docstrings must follow the Google style guide (see https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). Functions, classes, and modules should have clear docstrings explaining their purpose, parameters, return values, and any exceptions they may raise. Inline comments should explain "why" rather than "what" for non-obvious logic.

## Configuration & Secret Management
- `bk_monitor_base.config.Config` loads `config.yaml` first, then `.env`, and finally environment variables (nested delimiter `__`). Production must rely on env/secret managers—never submit new plaintext secrets.
- When editing sensitive values, prefer `export BK_MONITOR_BASE__BLUEKING__APP_CODE=...` and verify via `uv run python -c "from bk_monitor_base.config import get_config; print(get_config().blueking)"`.
- `django_setup.py` performs lazy initialization; any script or test touching Django models must call `from bk_monitor_base.django_setup import django_setup; django_setup()`.
- For large local overrides, create an untracked `.env` and document the change in `docs/development/setup.md` so the team stays aligned.

## Dev Environment Tips
- Create an isolated environment with `uv venv --seed && source .venv/bin/activate`, then install all runtime/CLI/dev dependencies via `uv sync --all-groups`.
- Run every script through `uv run <command>` (e.g., `uv run bk-monitor-base-cli --help`, `uv run python scripts/bootstrap.py`) to guarantee consistent interpreter paths and locked dependencies.
- Maintain the tight feedback loop: `uv run python -m basedpyright`, `uv run ruff check src`, and `uv run pytest`; optionally call `uv run ruff format` before committing.
- Before touching a domain module, skim `docs/architecture/overview.md` and `src/bk_monitor_base/domains/README.md`, then extend the relevant `domains/` subdirectory to avoid cross-layer coupling.

## Testing Instructions
- Entry point: `pytest.ini` restricts discovery to `src/bk_monitor_base/tests`; execute `uv run pytest --cov --cov-branch` to collect coverage (source = `src/bk_monitor_base`, excluding tests/migrations).
- Targeted runs: `uv run pytest src/bk_monitor_base/tests/domains/test_space.py -k create_space`, optionally adding `-vv --maxfail=1` when iterating on failures.
- Django scenarios must invoke `django_setup()` (or dedicated fixtures) before accessing ORM objects; Celery coupling can rely on `CELERY_TASK_ALWAYS_EAGER=true` during tests.
- Static checks carry equal weight: `uv run ruff check src` plus `uv run basedpyright` must pass alongside pytest; introduce new APIs only with matching `docs/` and `tests/`.
- **Test Data Management**: All test data created during test execution must be cleaned up after each test to prevent interference with other tests. Use unique identifiers (e.g., timestamps, UUIDs, or test function names) to distinguish data generated by different test cases, ensuring parallel test execution does not cause data conflicts. Leverage pytest fixtures with `yield` or `finalizer` callbacks, or use `teardown` methods to guarantee cleanup.
- **Table-Driven Testing**: Prefer table-driven testing patterns when testing multiple similar scenarios. Define test cases as data structures (lists of dictionaries or tuples) and iterate over them in a single test function, which improves maintainability and reduces code duplication.
- **Test Code Readability**: Test code must be highly readable with sufficient comments and documentation. Each test function should include clear docstrings explaining what is being tested, why it matters, and any setup/teardown considerations. Use descriptive variable names, add inline comments for complex assertions or non-obvious logic, and structure tests to follow the Arrange-Act-Assert (AAA) pattern.

## PR Instructions
- PR titles must follow the Conventional Commits spec (scope optional, e.g., `feat(lang): add Polish language`). Use the body to describe motivation, impact, and rollback considerations.
- Commits must follow the Conventional Commits spec (e.g., `feat:`, `fix:`, `docs:`) so automation can infer changelog semantics.
- Before committing, run `uv run ruff check src`, `uv run basedpyright`, and `uv run pytest --cov --cov-branch`; add `uv run ruff format` when needed to keep style consistent.
- Reflect any configuration change in `docs/development/setup.md` or a new ADR; when touching scripts/CLI/domains, include corresponding tests and documentation.
- Whenever GitHub CLI (`gh`) is available, prefer it for repository interactions (e.g., creating PRs, viewing checks) instead of raw HTTP or manual browser steps.
- CI follows the upstream BlueKing templates (even if this repo lacks `.github/workflows`); ensure local checks are green before requesting review, and highlight error handling, logging context, and rollback strategy for reviewers.
