# Skill: Module Pattern Selector

For complex frontend features, select design patterns per module instead of forcing one global pattern.

Module dimensions:
- domain: invariants, entities, value objects and repository ports
- application: use cases, orchestration and command flow
- infrastructure: API adapters, providers and extension registries
- presentation: UI composition, interaction state and view contracts

Selection rules:
1. Each module must choose the simplest sufficient pattern for its responsibility.
2. Different modules may use different patterns when business behavior differs.
3. Pattern landing must include contract, implementation boundary and verification.
4. Do not leak infrastructure or presentation pattern choices into domain logic.

Required artifacts:
- module_pattern_selection
