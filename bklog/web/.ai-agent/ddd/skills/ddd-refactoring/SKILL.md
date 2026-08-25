# DDD Refactoring

## Activation

Only execute when all of the following hold:

1. DDD is enabled
2. The user requests implementation / migration / refactoring
3. Code mapping is available

## Workflow

```text
Discovery -> DDD Model -> Code Mapping -> Migration Plan -> Implementation -> Validation
```

## Rules

Never directly perform large-scale DDD restructuring without an intermediate migration plan.

## Schema

`.ai-agent/ddd/schemas/code-mapping.schema.json`
