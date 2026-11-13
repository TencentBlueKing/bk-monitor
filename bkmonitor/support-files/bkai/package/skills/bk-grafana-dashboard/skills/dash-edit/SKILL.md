---
name: dash-edit
description: Edit an existing BlueKing iframe Grafana dashboard with panel-id operations. Never rewrite full dashboard JSON.
---

# dash-edit

编辑已有盘。模型只产出 **operations**；完整 JSON 留在磁盘上，由 `dashboard_tools.py` 改。页面在蓝鲸监控 iframe 里刷新后才能看见，没有 Grafana 官方的选中 panel / canvas。

所有 `python scripts/dashboard_tools.py` 命令都在 **bk-grafana-dashboard skill 根目录** 执行。

先读 `../../references/bk-grafana-model.md`。改查询时再读 `../../references/promql-dialect.md`。加图时再读 `../../references/panel-min-schema.md`。

## 硬禁止

- 禁止 `Read` `dashboard.json` 或把整盘 JSON 贴进对话。
- 禁止手写完整 dashboard 再调用 `update_dashboard`。
- 禁止用 title 作为写入键。
- 禁止改已有 panel 的 datasource uid（保留 `000000002` 或盘上现有值）。
- 禁止删除或重写不认识的二开字段。
- 匹配到多个 panel 时禁止猜第一个，必须问 `panel_id`。
- 「整盘重做」退出本流程，转 create。

## 流程

工作目录：`output/bk-grafana-dashboard/<biz>_<uid>/`

1. 解析 uid（用户给、URL 里 `/grafana/d/<uid>/`、或 `get_dashboard_tree_list` 搜索）。多命中先确认。
2. `get_dashboard_detail_by_uid`。把 **MCP 原始 JSON** 写到 `mcp.json`（不要解析后复述 panels）。
3. 立刻解包，此后只看脚本输出：

```bash
python scripts/dashboard_tools.py ingest --input mcp.json --out dashboard.json --meta meta.json
python scripts/dashboard_tools.py summary --file dashboard.json --meta meta.json
```

4. 用用户说的标题定位：

```bash
python scripts/dashboard_tools.py locate --file dashboard.json --query "CPU使用率"
```

`ambiguous: true` → 停，列出 matches，问用户。
5. 按意图取最小上下文：
   - 改标题 / 类型 / 布局：有 summary 即可。
   - 改查询 / 换可视化细节：`get-queries` 或 `get-panel`（只取这一个 panel）。
6. 把 operations 写入 `ops.json`，执行：

```bash
python scripts/dashboard_tools.py apply --file dashboard.json --ops ops.json --meta meta.json
```

7. 若改了 query 或 add_panel：`validate-query` + `extract-promql`。无 `$变量` 时 `execute_range_query`（近 1h，跨度 ≤ 24h）。失败则继续 apply 修复，不要宣称已改好。
8. `build-save --file dashboard.json --bk-biz-id <id> --folder "<原目录>" --meta meta.json --out save.json`
9. 确认后，把 `save.json` 里的 `mcp_arguments` **原样**传给 `update_dashboard`。
10. 用 apply 返回的新 summary 告诉用户改了哪些 `panel_id`。iframe 路径在 summary 的 `iframe_path`。

## 允许的 op

`set_title` `set_description` `set_type` `set_query` `set_viz` `set_grid` `add_panel` `remove_panel` `add_variable` `set_variable` `set_dashboard_meta`

`set_query` 必须带 `mode`。`ui` 只传 `query_configs`；`code` 只传 `source`。脚本会拒绝 UI 模式非空 `source`、`metric_field` 带表名前缀等方言错误。

`add_panel.panel` 只生成**一个** panel。`id` 和默认 `gridPos` 由脚本分配。`placement.after_panel_id` 优先。

## 保存后

用户要在蓝鲸监控里打开该业务的仪表盘 iframe 才能看到。不要说「已在 Grafana 官方 UI 保存」。
