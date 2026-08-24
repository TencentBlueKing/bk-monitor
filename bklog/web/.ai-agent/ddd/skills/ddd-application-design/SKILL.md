# DDD Application Design

## Purpose

Define application-level use cases.

## Identify

- Commands
- Queries
- Use Cases
- Application Services
- Transactions
- Authorization boundaries
- Idempotency requirements
- Orchestration

## Rule

Application layer coordinates domain behavior. It MUST NOT become the location of core business invariants.

## Output

ApplicationModel

## Schema

`.ai-agent/ddd/schemas/use-case.schema.json`
