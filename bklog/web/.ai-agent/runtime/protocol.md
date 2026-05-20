# Skill State Protocol

Every skill must output:

```json
{
  "status": "pass | warn | fail",
  "summary": "short decision summary",
  "artifacts": {},
  "risks": [],
  "nextHints": []
}
```

Artifacts should expose stable keys used by gates, such as boundaries, decomposition, pattern_selection, risk_review, extension_points and critic_pass.
