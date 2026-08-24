# Skill: Pattern Gate

Decide whether the frontend design-pattern system may run at all.

Design-pattern skills are opt-in. The presence of factory, adapter, observer,
strategy, singleton, store, reducer, hook or middleware in the codebase is never
sufficient to activate them.

Steps:
1. Run `aafe pattern gate "<request>"`.
2. disabled -> stop. Handle the task as ordinary development work.
3. ambiguous -> ask the user. Do not activate silently.
4. enabled -> continue to discovery, not to selection.

Full rule: `.ai-agent/frontend-engineering/rules/pattern-gate.md`

Required artifacts:
- pattern_decision
