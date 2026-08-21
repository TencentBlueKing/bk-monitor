# Pattern Boundary Rules

## Purpose

Keep each pattern inside the responsibility it was selected for.

BOUNDARY-001
Every pattern MUST declare its boundary: what is inside it and what is not.

BOUNDARY-002
A pattern MUST NOT absorb responsibilities belonging to another selected pattern.

BOUNDARY-003
Patterns MUST NOT be layered purely to satisfy a naming convention.

BOUNDARY-004
Cross-boundary communication MUST be explicit; implicit coupling through shared
mutable state is not a pattern relation.

BOUNDARY-005
A pattern's failure behavior MUST be defined at its boundary.

BOUNDARY-006
DDD decides boundaries; patterns operate inside them. A pattern MUST NOT be used
to redraw a bounded context.
