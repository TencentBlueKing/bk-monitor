# DDD Skill System

Domain-Driven Design capability pack. **DDD is opt-in.** Nothing in this
directory may run until the gate says the user explicitly asked for DDD.

## Entry Point

```text
User Request -> DDD Gate -> DISABLED ? STOP
                         -> ENABLED  -> Scope -> Load Rules -> Execute Skills -> Validate
```

The gate is not an ordinary skill; it is the entry controller for this pack.
Read `.ai-agent/ddd/rules/ddd-gate.md` before anything else here.

## Rules Loading Order

1. `rules/ddd-gate.md`
2. `rules/ddd-scope.md`
3. `rules/ddd-strategic-rules.md`
4. `rules/ddd-tactical-rules.md`
5. `rules/ddd-architecture-rules.md`
6. `rules/ddd-code-rules.md`
7. `rules/ddd-refactoring-rules.md`
8. `rules/ddd-validation-rules.md`

Rules 3-8 load only when a selected skill needs them. Loading the full rule set
before the gate is forbidden: it is what causes ordinary tasks to drift into DDD
because a skill description mentioned Domain, Entity, Aggregate or Repository.

## Skills

- `skills/ddd-gate/SKILL.md` — Determine whether the current user request explicitly requires DDD.
- `skills/ddd-project-discovery/SKILL.md` — Understand the existing project before DDD modeling.
- `skills/ddd-domain-discovery/SKILL.md` — Discover business concepts from the existing project.
- `skills/ddd-strategic-design/SKILL.md` — DDD Strategic Design
- `skills/ddd-bounded-context/SKILL.md` — Define explicit model boundaries.
- `skills/ddd-context-map/SKILL.md` — Model relationships between Bounded Contexts.
- `skills/ddd-tactical-design/SKILL.md` — Transform strategic domain concepts into tactical domain models.
- `skills/ddd-aggregate/SKILL.md` — Define consistency boundaries.
- `skills/ddd-domain-event/SKILL.md` — Identify business-significant occurrences.
- `skills/ddd-application-design/SKILL.md` — Define application-level use cases.
- `skills/ddd-architecture/SKILL.md` — Map DDD concepts into the project's actual architecture.
- `skills/ddd-code-mapping/SKILL.md` — Map the DDD model to the existing implementation.
- `skills/ddd-refactoring/SKILL.md` — DDD Refactoring
- `skills/ddd-validation/SKILL.md` — Validate the DDD implementation.
- `skills/ddd-documentation/SKILL.md` — Persist the DDD model as project knowledge.

## Dispatch Matrix

| 用户意图 | Gate | Discovery | Strategic | Context | Tactical | Aggregate | Application | Architecture | Mapping | Refactor | Validate |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| 普通开发 | - | - | - | - | - | - | - | - | - | - | - |
| 普通架构分析 | - | - | - | - | - | - | - | - | - | - | - |
| DDD 分析 | Y | Y | Y | Y | Y | opt | opt | Y | Y | - | opt |
| DDD 战略设计 | Y | Y | Y | Y | - | - | - | - | - | - | - |
| Aggregate 设计 | Y | Y | - | - | Y | Y | - | - | - | - | opt |
| DDD 架构设计 | Y | Y | Y | Y | Y | opt | Y | Y | - | - | opt |
| DDD 重构 | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| DDD 完整落地 | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| DDD 验证 | Y | Y | opt | opt | Y | Y | Y | Y | Y | - | Y |

## Tooling

```bash
aafe ddd gate "<request>"      # enabled | disabled | ambiguous, with reasons
aafe ddd scope "<request>"     # minimum skill set + rule loading order
aafe ddd analyze "<request>"   # domain model, each concept observed or inferred
aafe ddd ask "<request>"       # discovery questions
```

The `domain-feature` pipeline runs this chain end to end and is only reachable
when the gate passes.

## Core Constraints

- **DDD-SYSTEM-001** DDD is opt-in, not opt-out.
- **DDD-SYSTEM-002** Explicit user intent is required to activate DDD.
- **DDD-SYSTEM-003** DDD terminology in the project MUST NOT activate DDD.
- **DDD-SYSTEM-004** Architecture analysis MUST NOT automatically become DDD analysis.
- **DDD-SYSTEM-005** DDD activation MUST be scoped to the user's requested capability.
- **DDD-SYSTEM-006** DDD patterns MUST NOT be introduced without domain justification.
- **DDD-SYSTEM-007** Existing project evidence MUST be collected before DDD modeling.
- **DDD-SYSTEM-008** Observed facts and inferred models MUST be distinguished.
- **DDD-SYSTEM-009** Strategic design MUST precede tactical design when performing full DDD design.
- **DDD-SYSTEM-010** Bounded Context MUST be based on semantic boundaries.
- **DDD-SYSTEM-011** Aggregate MUST be based on consistency boundaries.
- **DDD-SYSTEM-012** Business rules MUST remain close to the domain model.
- **DDD-SYSTEM-013** DDD MUST NOT force a specific architecture.
- **DDD-SYSTEM-014** DDD MUST NOT force Microservices, CQRS, Event Sourcing, or Domain Events.
- **DDD-SYSTEM-015** DDD refactoring MUST preserve existing behavior by default.
- **DDD-SYSTEM-016** DDD migration MUST be incremental for existing systems.
- **DDD-SYSTEM-017** Every major DDD decision MUST be traceable to evidence.
- **DDD-SYSTEM-018** DDD validation MUST detect both violations and false positives.
- **DDD-SYSTEM-019** DDD documentation MUST be generated from the validated model.
- **DDD-SYSTEM-020** If DDD is not explicitly requested, DDD skills MUST NOT execute.

The load-bearing ones are 001, 002, 003 and 005: DDD is an explicitly enabled
capability, not a code-feature-triggered one.
