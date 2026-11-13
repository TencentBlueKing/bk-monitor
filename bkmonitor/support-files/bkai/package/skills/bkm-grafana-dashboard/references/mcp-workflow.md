# MCP 编排

调用前用宿主的工具发现能力读取 schema。下表使用 Server 后缀；完整名称以已确认目标网关和发布环境的发现结果为准：

| 用途 | Server | Tool |
| --- | --- | --- |
| 目录树 | `dashboard-query` | `get_dashboard_tree_list` |
| 拉盘 | 同上 | `get_dashboard_detail_by_uid` |
| 新建 | `dashboard-edit` | `create_dashboard` |
| 更新 | 同上 | `update_dashboard` |
| 验数 | `metrics-query` | `execute_range_query` |
| 业务 | `metadata-query` | `search_spaces` |

## 读

```json
{ "query_param": { "bk_biz_id": "<bk_biz_id>", "dashboard_uid": "host-monitor-dashboard" } }
```

返回后立刻写入 `mcp.json` 并 `ingest`。不要在回复里展开 `data` 字符串。

## 写

只传 `build-save` 给出的 `mcp_arguments`：

```json
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "configs": {
      "grafana/主机监控/主机监控仪表盘.json": "{...Grafana JSON string...}"
    }
  }
}
```

`configs` 必须是字典（path → Grafana JSON 字符串）。MCP tool schema 可能写成 string，实际 API 拒绝 string。更新已有盘用 `update_dashboard`，新建用 `create_dashboard`。写之前向用户确认 `bk_biz_id`、路径、uid。

## 验数

```json
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "promql": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
    "start_time": "<now-3600>",
    "end_time": "<now>",
    "step": "1m"
  }
}
```

时间戳必须现场算。单次 ≤ 86400s。有 `$变量` 先替换或跳过。
