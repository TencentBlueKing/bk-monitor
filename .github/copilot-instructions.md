# GitHub Copilot Code Review Instructions

This document provides comprehensive code review guidelines for the **bk-monitor** project, ensuring consistency and quality in all pull requests reviewed by GitHub Copilot.

[TOC]

## Core Review Principles

As a Copilot agent reviewing this project, prioritize the following principles:

1.  **Clarity and Maintainability**: Code must be easy to read and understand. Follow PEP 8 (via `ruff`) and **Google Python Style Guide** principles.
2.  **Correctness and Reliability**: Ensure algorithms are implemented correctly. Pay close attention to concurrency (`asyncio`, `threading`, `gevent`), thread safety, and data integrity.
3.  **Performance**: Monitoring systems deal with high-throughput data. Suggest efficient data structures, batch processing, and async I/O. Use the project's established tooling (`ruff`, `pyright`) to enforce quality.
4.  **Test Coverage**: All new logic must be accompanied by comprehensive `pytest` tests. Aim for high test coverage, especially for data processing pipelines and alerting logic.
5.  **MANDATORY Review Acknowledgment**: This is a **REQUIRED** and **NON-NEGOTIABLE** rule. **All code reviews must be provided in Chinese.** When GitHub Copilot generates any PR review summary, it **MUST** begin with the following exact acknowledgment statement:
    > ✓ 代码评审按照 `.github/copilot-instructions.md 中定义的指南进行。`

    **Important Notes:**
    - This statement confirms that ALL guidelines in this document have been actively applied.
    - Omitting this acknowledgment statement is **NOT ACCEPTABLE**.
    - The statement must appear at the **very beginning** of every PR review summary.

---

## Python Code Review Guidelines

As an expert-level Python engineer, provide professional feedback on the following aspects, targeting **Python 3.11+**:

### 1. Code Quality & Style (Google Style Guide)

- **Style Guide**: Adhere to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) where it does not conflict with project-specific `ruff` configurations.
- **Docstrings**: Use **reStructuredText (reST)** format for docstrings (compatible with Sphinx).
    ```python
    def connect_to_next_port(self, minimum: int) -> int:
        """Connects to the next available port.

        :param minimum: A port value greater or equal to 1024.
        :return: The new minimum port.
        :raises ConnectionError: If no port is available.
        """
    ```
- **Line Length**: Maximum **120 characters** (as configured in `pyproject.toml`).
- **Import Organization**:
    - Group imports: standard library, third-party, local.
    - Handled automatically by `ruff`, but ensure no unused imports remain.
    - **No Wildcard Imports**: `from module import *` is strictly forbidden.

### 2. Naming Conventions

- **Variables/Functions**: `snake_case`.
- **Classes**: `PascalCase`.
- **Constants**: `UPPER_SNAKE_CASE`.
- **Private Members**: Prefix with single underscore `_private_method`.
- **Google Style Specifics**:
    - Use `_` for unused variables in loops.
    - Avoid single-letter names except for counters and iterators (e.g., `i`, `j`).

### 3. Frameworks & Middleware Best Practices

The project relies heavily on **Django, Redis, Elasticsearch (ES), MySQL, and Kafka**. Reviews must target these technologies specifically:

#### **Django (Web Framework)**
- **ORM Optimization**:
    - Strictly check for **N+1 problems**. Suggest `select_related()` for foreign keys and `prefetch_related()` for M2M relationships.
    - Use `iterator()` for processing large querysets to save memory.
    - Avoid `len(queryset)`; use `queryset.count()`.
- **Architecture**:
    - **Thin Views**: Move business logic to **Service layers** or **Model Managers**. Views should only handle request parsing and response formatting.
    - **Serializers**: Use DRF Serializers for validation, not just serialization.

#### **MySQL (Relational DB)**
- **Transactions**: Ensure atomicity in multi-step writes using `transaction.atomic()`.
- **Indexing**: Check if new fields used in filters/ordering are indexed.
- **Schema**: Avoid altering large tables without a migration strategy (e.g., `gh-ost` awareness, though usually out of code scope, code should minimize locks).

#### **Redis (Cache & Queue)**
- **Pipelines**: Use pipelines (`pipe = redis.pipeline()`) for batch operations to reduce RTT.
- **Key Naming**: Ensure keys have a consistent namespace (e.g., `bkmonitor:cache:metric:<id>`) to avoid collisions.
- **TTL**: Always verify that cache keys have an expiration time (TTL) to prevent memory leaks.
- **Data Structures**: Suggest `Hashes` for object storage over serialized strings where appropriate.

#### **Elasticsearch (Search & Analytics)**
- **Query Optimization**:
    - Avoid deep pagination (`from` + `size`). Use `search_after` or Scroll APIs for deep scanning.
    - Use `filter` context instead of `query` context for non-scoring exact matches (better caching).
- **Writes**: Prefer `bulk` APIs for indexing multiple documents.

#### **Kafka (Message Queue)**
- **Consumer**: Ensure consumers handle **rebalancing** gracefully.
- **Idempotency**: Message processing must be idempotent to handle duplicate deliveries.
- **Accumulation**: Check for logic that might cause slow consumption and lag.

### 4. Design Patterns & Architecture

- **SOLID Principles**: Strictly apply SOLID principles.
- **Error Handling**:
    - Catch specific exceptions (e.g., `redis.RedisError` instead of `Exception`).
    - Use `try/except/else/finally` blocks effectively.
    - **Google Style**: Do not use `assert` statements for data validation (they can be compiled out with `-O`).

### 5. Performance & Concurrency

- **Async/Await**: Used for I/O-bound tasks. Ensure `await` is not called inside a loop if requests can be concurrent (use `asyncio.gather`).
- **Celery**:
    - Tasks should be **atomic** and **idempotent**.
    - Avoid passing complex objects (ORM instances) to tasks; pass primary keys (IDs) instead.

---

## Specific to Observability & Monitoring Projects

This project (`bk-monitor`) operates in the observability domain. Reviews must consider:

### 1. Data Model & Standards
- **OpenTelemetry**: Align with OTel semantic conventions (Resource, Scope, Attributes).
- **Prometheus**:
    - **High Cardinality**: CRITICAL check. Do not allow unbounded values (user inputs, full URLs, error messages) in metric labels.
    - Correct usage of Counter (monotonically increasing) vs Gauge (fluctuating).

### 2. Data Pipeline
- **High Throughput**: Code handling data ingestion must be non-blocking.
- **Downsampling**: Suggest rollups or downsampling logic for historical data queries to improve dashboard loading speed.

### 3. Alerting Logic
- **Flapping**: Ensure alert conditions have hysteresis or windowing to prevent "flapping" (rapid on/off switching).
- **No Data**: Logic must account for "missing data" vs "zero value".

---

## References

For deep dives and context, refer to these authoritative sources:

- **Python Style**: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- **Docstrings**: [Sphinx reStructuredText Primer](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- **Django**: [Django Database Optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- **Celery**: [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#tips-and-best-practices)
- **Redis**: [Redis Pipeline Documentation](https://redis.io/docs/manual/pipelining/)
- **Elasticsearch**: [Tune for Search Speed](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-search-speed.html)
- **OpenTelemetry**: [OTel General Concepts](https://opentelemetry.io/docs/concepts/)
- **Prometheus**: [Metric and Label Naming](https://prometheus.io/docs/practices/naming/)

---

## Industry Best Practices Checklist

- [ ] **Docstrings**: Uses reStructuredText and describes params/returns/raises.
- [ ] **Database**: No N+1 queries; transactions used for atomicity.
- [ ] **Redis/ES/Kafka**: Batching used (pipelines/bulk); resources cleaned up.
- [ ] **Security**: No hardcoded secrets; SQL injection prevented.
- [ ] **Observability**: Metric labels are low-cardinality.
- [ ] **Style**: Follows Google Python Style Guide & PEP 8.

---

**Last Updated**: 2025-12-09
