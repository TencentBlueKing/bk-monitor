# DDD Scope Rule

DDD activation establishes permission to use DDD skills. It does NOT require
executing every DDD skill. The active skill set MUST be determined by the user's
requested outcome.

## Examples

User: "设计 Aggregate"

Activate: ddd-gate, ddd-project-discovery, ddd-domain-discovery,
ddd-tactical-design, ddd-aggregate.

Do NOT automatically activate: ddd-refactoring, ddd-documentation,
ddd-context-map.

User: "分析当前项目并完整落地 DDD"

Activate the full chain: ddd-gate, ddd-project-discovery, ddd-domain-discovery,
ddd-strategic-design, ddd-bounded-context, ddd-context-map, ddd-tactical-design,
ddd-aggregate, ddd-domain-event, ddd-application-design, ddd-architecture,
ddd-code-mapping, ddd-refactoring, ddd-validation, ddd-documentation.

## Principle

Minimum Required Skill Set. Only activate the minimum skills required to satisfy
the user's DDD request.

## Rules Loading Order

1. ddd-gate
2. ddd-scope
3. relevant strategic rules
4. relevant tactical rules
5. relevant architecture rules
6. relevant code rules
7. relevant refactoring rules
8. relevant validation rules

Loading the full DDD rule set before the gate is forbidden.

## Tooling

`aafe ddd scope "<request>"` returns the resolved skill set and rule order.
