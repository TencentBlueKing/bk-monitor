# DDD Aggregate Design

## Purpose

Define consistency boundaries.

## Analyze

- invariants
- transaction boundaries
- lifecycle
- concurrency
- consistency requirements
- command boundaries
- state transitions

## Questions

1. What must change atomically?
2. What must remain consistent?
3. What can become eventually consistent?
4. What is the Aggregate Root?
5. Is the Aggregate too large?
6. Are relationships incorrectly modeled?
7. Is the Aggregate derived from business behavior or database tables?

## Output

AggregateModel

## Schema

`.ai-agent/ddd/schemas/aggregate.schema.json`
