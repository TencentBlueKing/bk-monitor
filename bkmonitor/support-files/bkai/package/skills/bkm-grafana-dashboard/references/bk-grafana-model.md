# 蓝鲸 iframe Grafana 数据模型

## 和官方 Grafana 的差别

| | 官方 Grafana | 蓝鲸这里 |
| --- | --- | --- |
| 展示 | Grafana 应用本身 | 监控页面 **iframe** 嵌 `/grafana/d/<uid>/<slug>` |
| 读写 | Grafana HTTP API / mcp-grafana patch | 蓝鲸 `dashboard-query` + `dashboard-edit` IaC 导入 |
| 数据源 | prometheus / loki 等 | 二开 `bkmonitor-timeseries-datasource` |
| 查询 | `targets[].expr` | `targets[].mode` + `source` 或 `query_configs` |
| 编辑 UX | Assistant 可点选 panel | 没有。定位靠 `panel.id` + 本地脚本 |

不要调用 grafana/mcp-grafana，不要假设 Grafana PATCH、`get_dashboard_property`、`run_panel_query`、`get_panel_image` 存在。

## MCP 读回来的信封

`get_dashboard_detail_by_uid` 的 `data` **不是** Grafana 对象，而是：

```json
{
  "id": 3303,
  "uid": "host-monitor-dashboard",
  "title": "主机监控仪表盘",
  "version": 1,
  "slug": "e4b8bb-...",
  "data": "{...Grafana JSON 字符串...}"
}
```

必须先 `ingest` 解包。目录树是「folder 节点 + dashboards[]」，folder `title` 用于保存路径 `grafana/<folder>/<title>.json`。General 可省略目录段。

## 查询形态（二开）

同一个 `targets[]` 元素：

**UI 模式**（主机标准指标常见）

```json
{
  "mode": "ui",
  "source": "",
  "query_configs": [{ "alias": "今日", "data_source_label": "bk_monitor", "result_table_id": "system.cpu_summary", "metric_field": "usage", "method": "AVG" }],
  "refId": "A",
  "type": "range",
  "format": "time_series"
}
```

**Code 模式**（PromQL）

```json
{
  "mode": "code",
  "source": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
  "query_configs": [],
  "promqlAlias": "今日",
  "refId": "A"
}
```

已有盘可能使用 `"000000002"` 等 datasource uid，必须以读回的值为准。IaC 新建用 `"${DS_蓝鲸监控_- 指标数据}"`。**编辑不要互相改写。**

常见二开附加字段（保留，不要删）：`cluster` `host` `module` `enableDownSampling` `expressionList` `showLastPoint` `step` `promqlAlias`。

## 身份

- 仪表盘：`uid`（写入键）
- 面板：`id`（int，盘内唯一）。脚本 `add_panel` 取 `max(id)+1`
- 查询：`panel_id` + `target_index`（以及 UI 的 `query_configs[].refId`）
- 变量：`templating.list[].name`
- row：`type: "row"`，子 panel 可能在 `row.panels`

`version` / 顶层 `id` 由脚本在 apply 后写回，模型不要改。

## 保存

`create_dashboard` / `update_dashboard` 的 `configs` 是字典：`{ "grafana/目录/名.json": "<Grafana JSON 字符串>" }`。MCP schema 可能把该字段标成 string，实际接口要 dict。只用 `build-save` 的 `mcp_arguments`，不要手拼转义。

`update_dashboard` 在 uid **或 title** 匹配时会覆盖。Skill 侧写入只认 uid，保存前必须确认。
