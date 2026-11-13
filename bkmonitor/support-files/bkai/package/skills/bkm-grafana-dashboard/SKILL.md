---
name: bkm-grafana-dashboard
description: 蓝鲸监控 iframe 二开 Grafana 仪表盘的新建与局部编辑。根据自然语言生成完整仪表盘，或按 panel.id 做增量修改，禁止整盘 JSON 重写。用户提到生成/创建/修改/编辑仪表盘、Grafana 面板、今日昨日上周对比、query_configs 时使用。
---

# 蓝鲸 Grafana 仪表盘

## 环境与依赖

同一目标监控网关下的 `dashboard-query`、`dashboard-edit`、`metrics-query` 和 `metadata-query`。本地脚本需要 Python 3.10 或更新版本。

先确认目标环境和 `bk_biz_id`，再发现该环境已授权的 MCP 工具并读取实时 schema。下文的 Server 后缀不是可直接调用的完整名称；无法唯一定位或缺少依赖时停止相应步骤，不跨环境回退。宿主提供认证入口时使用该入口完成认证，不在 Skill 中保存凭据。

这不是官方 Grafana，也不是 grafana/mcp-grafana。蓝鲸监控用 **iframe 嵌入二开 Grafana 页** 展示仪表盘；查询走 `bkmonitor-timeseries-datasource`（`mode: ui|code`）。读写只能用蓝鲸 dashboard MCP + 本 skill 的本地手术脚本。

## 强制第一步：路由

| 用户意图 | 走哪条 |
| --- | --- |
| 无 uid，要一张新盘 | `./skills/dash-create/SKILL.md` |
| 有 uid /「改这个盘」/ 改某一张图 | `./skills/dash-edit/SKILL.md` |
| 「整盘重做 / 推倒重来」 | 先确认覆盖，再走 **create + 原 uid**，不走 edit |

未给 `bk_biz_id` 时先问。写入前必须确认业务、目录、是否覆盖。

## 硬规则

1. **Create 产出完整 Grafana 10 JSON**；**Edit 只产出 operations**，由脚本改磁盘上的 JSON。
2. 编辑路径禁止把整盘 JSON 读进对话，禁止手写 `update_dashboard` 的完整 configs。
3. 写入只认 **uid**。禁止用 title 碰运气覆盖。
4. 二开字段（`mode`、`query_configs`、`source`、`cluster`、`host`、`promqlAlias` 以及未知字段）必须保留。脚本是 patch，不是重建。
5. 已有盘上的 datasource uid（常见 `000000002`）编辑时原样保留，不要改成模板变量。
6. 改 query / 新增 panel 后，用 `extract-promql` + `execute_range_query` 验数。含 `$变量` 且无法替换时，明确说「未实查」。

## 本地工具

统一入口（在本 skill 根目录）：

```bash
python scripts/dashboard_tools.py <command> ...
```

工作目录：`output/bkm-grafana-dashboard/<biz>_<uid>/`

```text
mcp.json            # MCP 原始返回，只给 ingest 用
dashboard.json      # 解包后的 Grafana JSON，禁止 Read 进对话
meta.json           # id/uid/slug/version
ops.json            # 本轮 operations
save.json           # build-save 产物
```

## 按需加载

| 何时 | 读什么 |
| --- | --- |
| 弄清 iframe / 二开 JSON / MCP 信封 | `./references/bk-grafana-model.md` |
| 写 PromQL 或 query_configs | `./references/promql-dialect.md` |
| 新建 panel 或 add_panel | `./references/panel-min-schema.md` |
| 调 MCP | `./references/mcp-workflow.md` |
| 对照完整例子 | `./references/examples.md` |
