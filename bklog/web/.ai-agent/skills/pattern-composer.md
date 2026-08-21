# Skill: Pattern Composer

Compose the selected patterns into a coherent architecture. This is the step
that makes the system something other than a pattern lookup table.

Rules:
1. Every pattern gets an explicit responsibility and boundary (RULE-003, RULE-007).
2. Pull in required collaborators; a pattern missing its dependency is incomplete.
3. Detect conflicts — two patterns claiming the same responsibility (RULE-009).
4. Detect redundancy — interchangeable alternatives to one problem (RULE-010).
5. Prefer the simplest sufficient composition (RULE-011).
6. Pattern count is not a quality metric (RULE-012). Fewer may be better (RULE-013).

Required artifacts:
- pattern_composition
- pattern_relations
- pattern_conflicts
