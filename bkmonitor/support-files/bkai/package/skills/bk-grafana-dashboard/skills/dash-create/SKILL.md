---
name: dash-create
description: Create a BlueKing iframe Grafana dashboard by generating complete Grafana 10 JSON with BK query_configs or PromQL code mode.
---

# dash-create

从用户语义生成**一整份**可导入的蓝鲸 Grafana 仪表盘。展示发生在监控页面的 iframe 里，不要按官方 Grafana 保存 API 来想。

所有 `python scripts/dashboard_tools.py` 命令都在 **bk-grafana-dashboard skill 根目录** 执行。

先读 `../../references/bk-grafana-model.md`、`../../references/promql-dialect.md`、`../../references/panel-min-schema.md`。

## 流程

1. 确认 `bk_biz_id`、目录（folder 标题）、仪表盘标题、是否覆盖同 uid。
2. 确认指标与图表：缺指标时先推荐再等用户点头。用户已给出明确 query 则可继续。
3. 用 `get_dashboard_tree_list` 看目录是否已有同名盘；有则停下来确认。
4. 直接生成完整 Grafana 10 JSON（见下方最小结构），落到
   `output/bk-grafana-dashboard/<biz>_<slug>/dashboard.json`。
   **只写这一次完整文件。** 之后的校验/修复用 `dashboard_tools.py apply`，禁止再整文件覆盖。
5. `python scripts/dashboard_tools.py summary --file dashboard.json` 自检 panel 列表。
6. 对每个有查询的 panel：`validate-query`；再 `extract-promql`，无 `$变量` 时用 `execute_range_query` 探针（近 1h）。
7. `build-save --file dashboard.json --bk-biz-id <id> --folder "<目录>"`。
8. 向用户确认后，把返回的 `mcp_arguments` **原样**传给 `dashboard-edit.create_dashboard`。
9. 成功后把 summary（uid、每个 panel 的 id/title/type）回给用户，方便下一轮走 edit。

## 生成时必须带上

- `title`、`uid`（可留空让平台生成，用户指定则用用户的）、`timezone`、`time`、`panels`、`templating`
- `__inputs` / `__requires`（脚本 `build-save` 也会补；生成时仍应写入）
- 每个 panel：`id`、`title`、`type`、`gridPos`、`datasource`、`targets`
- **新建** datasource uid 用模板：`${DS_蓝鲸监控_- 指标数据}`，type 固定 `bkmonitor-timeseries-datasource`
- 今日 / 昨日 / 上周：红色 / 绿色 / `#808080`，用 `time_shift` `1d` / `1w`（UI 模式）或三条 PromQL（code 模式）
- 默认时间 `now/d` ~ `now/d` 或用户指定

## 查询二选一，不要混在同一个 target 里

- **UI 模式**（主机/标准指标优先）：`mode: "ui"`，`source: ""`，填 `query_configs`
- **Code 模式**（PromQL / 容器 / 自定义计算）：`mode: "code"`，`query_configs: []`，填 `source`

## 禁止

- 不要用官方 Grafana MCP，不要假设能调 Grafana PATCH / Assistant / 截图渲染。
- 不要在 UI 模式把 PromQL 塞进 `source`。
- `metric_field` 只写字段名，例如 `usage`，不要写成 `cpu_summary.usage`。
- 容器指标 PromQL 不要加结果表：`bkmonitor:container_cpu_usage_seconds_total`。
- 不要把 `build-save` 成功说成已导入；MCP 成功返回才算保存。
