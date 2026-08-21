# Over-engineering Rules

## Purpose

Prevent the pattern system from becoming an abstraction generator.

OVERENG-001
A pattern whose justifying complexity is absent MUST NOT be introduced.

OVERENG-002
Abstraction count MUST NOT exceed the number of variation points it isolates.

OVERENG-003
"可能以后会变" is not a variation point. Wait for the second concrete case.

OVERENG-004
Every abstraction layer MUST name the change it absorbs.

OVERENG-005
When two compositions solve the problem, the one with lower total cognitive cost
MUST be preferred.

OVERENG-006
The proposed composition MUST itself be audited for anti-patterns before it is
recommended.

ANTI-PATTERN-001
A pattern used outside its problem domain is a potential anti-pattern.

ANTI-PATTERN-002
Multiple patterns with overlapping responsibility MUST be reviewed.

ANTI-PATTERN-003
A pattern that increases complexity without reducing meaningful change cost MUST be rejected.

ANTI-PATTERN-004
Pattern count MUST NOT justify architecture quality.

ANTI-PATTERN-005
Generic abstractions MUST NOT hide business semantics.

ANTI-PATTERN-006
Global state MUST NOT become the default integration mechanism.

ANTI-PATTERN-007
Event Bus MUST NOT replace normal function calls without architectural justification.
