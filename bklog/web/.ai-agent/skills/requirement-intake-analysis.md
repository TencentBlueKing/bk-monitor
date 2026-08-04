# Skill: Requirement Intake & Analysis

Trigger: **具体需求已获取**（TAPD 单据内容已拉取，或用户给出可执行的需求描述），且尚未开始写代码。

Rule: `.ai-agent/rules/requirement-intake-analysis.mdc`

Post-implementation (unchanged): `.ai-agent/rules/task-completion-impact.mdc` → `.ai-agent/rules/tapd-submit-backfill.mdc`

---

## Phase 0 — Confirm requirement source

| Source | Done when |
| --- | --- |
| TAPD | `stories_get` / `bugs_get` 或用户粘贴：标题、描述、验收、优先级、关联信息 |
| Non-TAPD | 用户消息含：要做什么、期望结果、范围边界（或经 Phase 1 补全） |

Record: `requirement_source`, `requirement_summary`, `tapd_entry_id`（若有）

---

## Phase 1 — Analyze & clarify (mandatory)

### 1.1 Parse

Extract:

- **Goal** — user-visible outcome
- **Scope** — in / out
- **Acceptance** — how to verify done
- **Constraints** — perf, compat, auth, deadline
- **Dependencies** — API, other modules, flags

### 1.2 Ambiguity register

For each unclear item, create `AMB-001`… with:

| Field | Content |
| --- | --- |
| Topic | What's unclear |
| Risk if guessed | Wrong fix cost |
| Resolution type | `choice` \| `question` \| `detail_needed` |

### 1.3 Interactive resolution (mandatory)

**choice** — present 2–4 options + recommendation:

```markdown
### AMB-001: （主题）
请选择：
- **A** …（推荐：…）
- **B** …
- **C** …
```

**question** — numbered precise questions.

**detail_needed** — ask for example, screenshot, API contract, edge case list.

**Hard:** `ambiguity_register` 非空且未关闭 → **stop**；不得进入 Phase 2。

Close each AMB with `resolution` text in output.

---

## Phase 2 — Historical accumulation search

**Only after** all AMB closed.

1. Read `.ai-agent/skills/memory-recaller.md`
2. Search:
   - `.ai-agent/memory/experience.md`
   - `.ai-agent/memory/learnings.jsonl`
   - `.ai-agent/memory/decisions.md`, topic files if relevant
   - Optional: `.docs`, TAPD comments (MCP)

Output `history_hits`:

| Hit | Source | Summary | Reuse? |
| --- | --- | --- | --- |
| H-001 | experience.md | … | full / partial / none |

If **full reuse** possible: propose applying historical path; confirm with user before skipping new design.

---

## Phase 3 — Code scope & root cause

After history review:

### 3.1 Code scope

- List files / symbols likely touched (use `project-architecture-locator.md` when needed)
- Mark read-only vs must-change
- Artifact: `code_scope`

### 3.2 Root cause (bugs / defects)

```text
Symptom → Immediate cause → Root cause hypothesis → How to verify
```

Artifact: `root_cause_analysis`

### 3.3 Implementation sketch

Bullet plan: what to change, what NOT to change.

---

## Phase 4 — Sizing gate & Plan mode

Estimate **before** coding:

| Signal | Count |
| --- | --- |
| Functions touched (incl. new) | n |
| Files touched | m |
| Estimated new lines | L |

### Direct path (small)

**All true:**

- Single-function logic fix **OR** style-only (CSS/class/layout), AND
- Not cross-cutting multi-module refactor

→ **Phase 5 direct implement**

### Plan path (large)

**Any true:**

- Cross-cutting multi-function **and** multi-file interdependency
- n > 5
- m > 5
- L > 300 (new feature / substantial addition)

Ask:

> 本次变更规模较大（约 n 个函数 / m 个文件 / L 行新增）。是否切换 **Plan 模式** 先制定详细实施计划？

Affirmative: `确认` / `同意` / `Yes` / `是` / `Y` / `切换plan` / `好`

**Action:** invoke **SwitchMode** with `target_mode_id: "plan"`. In Plan:

- Module boundaries, step order, file list, risks, test hooks
- Get user approval before returning to Agent for code

If user declines Plan: document risk; may proceed in Agent with explicit `plan_skipped: true`.

---

## Phase 5 — Implement

- Small: implement immediately
- Large + approved plan: follow plan steps
- Non-trivial frontend: then `.ai-agent/runtime/engine.md`, router, pipelines, gates as usual

**Do not** run task-completion-impact / TAPD backfill here — those run **after** implementation complete.

---

## Output template (end of intake, before code)

```markdown
## 需求摘要
...

## 不明确项处理
| ID | 问题 | _resolution |
...

## 历史方案检索
| Hit | 来源 | 是否复用 |
...

## 代码范围
...

## 根因分析
...

## 规模评估
functions: n, files: m, new_lines: L → direct | plan (user: yes/no)

## 下一步
direct fix | plan mode | blocked (waiting user)
```

---

## Anti-patterns

- Coding with open AMB items
- Skipping history on recurring bug classes
- >5 files change without plan ask
- Confusing this skill with post-task impact analysis (`architecture-impact-test-forecast.md`)
