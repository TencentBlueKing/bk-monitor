# DDD Code Rules

R-CODE-001

Business terminology SHOULD be reflected in code naming.

R-CODE-002

Business rules SHOULD be located close to the domain concept they govern.

R-CODE-003

Primitive obsession SHOULD be identified when it hides meaningful domain concepts.

R-CODE-004

Anemic Domain Model SHOULD be reported when domain behavior is systematically externalized without justification.

R-CODE-005

God Aggregates MUST be reported.

R-CODE-006

God Domain Services MUST be reported.

R-CODE-007

Generic Utility classes MUST NOT become dumping grounds for domain behavior.

R-CODE-008

Infrastructure concerns MUST NOT be mixed with core domain behavior.

R-CODE-009

Existing code MUST be analyzed before introducing new DDD abstractions.

R-CODE-010

DDD refactoring MUST preserve existing business behavior unless behavior change is explicitly requested.

R-CODE-011

DDD migration MUST be incremental when the existing project is large or business-critical.

R-CODE-012

Every proposed domain concept SHOULD have traceable evidence from code, tests, API, documentation, or user-provided business knowledge.
