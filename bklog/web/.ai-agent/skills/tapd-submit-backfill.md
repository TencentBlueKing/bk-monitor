# Skill: TAPD Submit Backfill

Trigger: user intent to **commit / push / submit / 提交代码 / 提测 / 提 PR**, and `.aafe.config.json` → `tapd.enabled === true`.

## MCP workflow (user-tapd_taihu)

1. `lookup_tool_param_schema` — get tool args
2. `proxy_execute_tool` — execute TAPD API
3. Optional: `lookup_tapd_tool` when tool name uncertain

Common tools: `stories_get`, `stories_create`, `stories_update`, `bugs_get`, `bugs_create`, `bugs_update`, `comments_create`, `tapd_id_get`, `user_participant_workspace_get`, `tapd_fields_summary_get`

## Config (`.aafe.config.json` → `tapd`)

```json
{
  "enabled": true,
  "username": "...",
  "api_password": "...",
  "workspace_id": "...",
  "milestone_id": "...",
  "default_entry_type": "story",
  "tapd_story": {
    "status_backlog": "backlog",
    "status_todo": "todo",
    "status_doing": "developing,status_7",
    "status_done": "for_test",
    "status_release": "status_3,status_9"
  },
  "tapd_bug": {
    "status_done": "resolved",
    "status_release": "verified",
    "status_doing": "assigned,in_progress"
  }
}
```

- `status_doing`: comma-separated **sequential** intermediate statuses before `status_done`
- `milestone_id`: used as `iteration_id` (or release) when creating new stories

## Step 1 — Gather backfill content

Before TAPD actions, ensure you have (from current task or `.ai-agent/skills/architecture-impact-test-forecast.md`):

- Self-test results (case table + pass/fail/skipped + command)
- Impact scope report (direct / indirect / potential)
- Change summary (files, PR/commit intent)

If missing, run impact/test analysis first or ask user to confirm proceeding with partial content.

## Step 2 — Resolve TAPD entry

| Source | Action |
| --- | --- |
| TAPD-origin task | Use known `entry_type`, `entry_id`, `workspace_id` |
| User provides ID | Short ID → `tapd_id_get`; confirm story vs bug |
| New story | Require `workspace_id` + `milestone_id`; `stories_create` |
| New bug | Require `workspace_id`; `bugs_create` |

## Step 3 — Post comment

`comments_create`:

- `workspace_id`, `entry_type` (story|bug), `entry_id`, `description` (Markdown: 自测结果 + 影响范围 + 变更摘要)

## Step 4 — Status transitions (strict, no skips)

### Existing story (TAPD-origin, not new)

Path: `status_todo` → each token in `status_doing` → `status_done`

Example config: todo → developing → status_7 → for_test

**Forbidden:** todo → for_test in one call.

### New story

Path: `status_backlog` → `status_todo` → each `status_doing` token → `status_done`

**Forbidden:** backlog → for_test, todo → for_test.

### Bug

Path: first `status_doing` token (if current is earlier) → ... → `status_done`

Algorithm:

1. `stories_get` / `bugs_get` — read `status` or `v_status`
2. Build ordered chain from config (see above)
3. Find current index in chain; if already at or past `status_done`, skip updates
4. For each remaining step until `status_done`:
   - `stories_update` / `bugs_update` with `status` or `v_status`, `check_workflow: "permission,condition"`
   - On failure, report and stop; do not skip steps
5. Log each transition for the user

## Step 5 — Report

Output:

- TAPD entry link/ID
- Comment posted (yes/no)
- Status transition log (from → to per step)
- Final status
- Any workflow errors

## Pure GitHub projects

If `tapd` is absent or `enabled: false`, skip this skill entirely; do not prompt TAPD unless user asks.
