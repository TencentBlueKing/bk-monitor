# Skill: DDD ↔ Pattern Bridge

DDD decides the business model and boundaries; design patterns solve the
variation, collaboration, state, creation, communication, data access and
performance problems inside those boundaries.

Mapping:
- Bounded Context -> module / feature boundary (Feature Module, Public API)
- Aggregate -> State Machine, Command, Repository
- Domain Service -> Strategy, Specification
- Domain Event -> Domain Event, Observer, Pub/Sub
- Application Service -> Facade, Mediator

These are candidates, not conclusions. A Domain Service becomes a Strategy only
when something actually varies.

Required artifacts:
- ddd_pattern_bridge
