# Skill: Experience Recorder

Record verified solution ideas for repeated problems.

Trigger condition:
- The same problem has been handled three times and still exists or regresses.
- A final solution has been verified as successful.

Write to .ai-agent/memory/experience.md and learnings.jsonl with type=experience.

Capture only:
- problem signature
- successful solution idea
- decision path
- applicable boundary
- avoid/retry warning

Do not capture:
- full trial-and-error logs
- temporary debugging details
- blame, emotions or noisy conversation history

Required artifacts:
- experience_memory
