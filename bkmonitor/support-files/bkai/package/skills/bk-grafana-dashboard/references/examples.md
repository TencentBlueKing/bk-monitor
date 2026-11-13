# 例子

以下均为合成示例；业务、资源、接收对象和查询字段在执行时以用户选择及工具发现结果为准。

脚本均在 skill 根目录执行。工作目录示例：`output/bk-grafana-dashboard/example-host-monitor-dashboard/`

## 新建（create）

用户：「在示例业务 的主机监控目录，做一张 CPU/内存/磁盘盘，带今日昨日上周。」

1. 读 dialect + panel-min-schema，生成 `dashboard.json`（UI 模式 + time_shift）。
2. `summary` 确认 3 张图。
3. 对每个 panel `validate-query`；`extract-promql` 后 `execute_range_query`。
4. `build-save --bk-biz-id '<bk_biz_id>' --folder 主机监控`
5. 确认后 `create_dashboard`。
6. 把返回的 uid 和 panel id 列表告诉用户。

## 改类型 + 加图（edit）

用户：「把主机监控仪表盘里 CPU 那张改成当前值 Stat，下面再加内存趋势。」

```bash
python scripts/dashboard_tools.py ingest --input mcp.json --out dashboard.json --meta meta.json
python scripts/dashboard_tools.py summary --file dashboard.json --meta meta.json
python scripts/dashboard_tools.py locate --file dashboard.json --query "CPU"
```

`ops.json`：

```json
{
  "operations": [
    { "op": "set_type", "panel_id": 1, "type": "stat" },
    { "op": "set_title", "panel_id": 1, "title": "当前 CPU" },
    {
      "op": "add_panel",
      "placement": { "after_panel_id": 1 },
      "panel": {
        "type": "timeseries",
        "title": "内存趋势",
        "targets": [{
          "mode": "ui",
          "source": "",
          "refId": "A",
          "type": "range",
          "format": "time_series",
          "query_configs": [{
            "alias": "今日",
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "display": true,
            "functions": [],
            "group_by": [],
            "interval": 60,
            "interval_unit": "s",
            "method": "AVG",
            "metric_field": "pct_used",
            "refId": "a",
            "result_table_id": "system.mem",
            "result_table_label": "os",
            "time_field": "time",
            "where": []
          }]
        }]
      }
    }
  ]
}
```

```bash
python scripts/dashboard_tools.py apply --file dashboard.json --ops ops.json --meta meta.json
python scripts/dashboard_tools.py validate-query --file dashboard.json --panel-id 1
python scripts/dashboard_tools.py extract-promql --file dashboard.json --panel-id 11
```

确认后 `build-save` → `update_dashboard`。

## 改 PromQL（code 盘）

用户：「总览里当前 TPS 改成按 5 分钟。」

`locate --query TPS` → `panel_id: 10` → `get-queries --panel-id 10`（确认 `mode: code`）。

```json
{
  "operations": [{
    "op": "set_query",
    "panel_id": 10,
    "mode": "code",
    "source": "round(sum(increase(rpc_server_handled_total{namespace=~\"$namespace\",service_name=~\"$service_name\"}[5m]))) / 300"
  }]
}
```

有 `$namespace`：问用户取值，或标记未实查。不要把变量从 query 里删掉。
