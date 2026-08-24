---
name: ddd-pattern-bridge
description: Map DDD building blocks onto pattern roles (§15).
---

# DDD ↔ Pattern Bridge

## Purpose

Map DDD building blocks onto pattern roles (§15).

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-boundary.md`

## Steps

1. Bounded Context → module / feature boundary (Feature Module, Public API).
2. Aggregate → State Machine, Command, Repository.
3. Domain Service → Strategy, Specification.
4. Domain Event → Domain Event, Observer, Pub/Sub.
5. Application Service → Facade, Mediator.
6. These are candidates, not conclusions: a Domain Service becomes a Strategy only when something actually varies.
7. DDD 决定业务模型和边界，设计模式负责解决这些边界内部的变化、协作、状态、创建、通信、数据访问和性能问题。

## Output

- DDDPatternBridge[] { dddBlock, name, candidatePatterns, role, note }
