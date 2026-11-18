# 单个 Panel 最小结构

`add_panel` 和新建盘都按这个最小集写。缺的 `id` / `gridPos` 在 add 时由脚本补。

## 公共

```json
{
  "type": "timeseries",
  "title": "CPU使用率",
  "datasource": {
    "type": "bkmonitor-timeseries-datasource",
    "uid": "000000002"
  },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "drawStyle": "line",
        "lineWidth": 2,
        "fillOpacity": 0,
        "showPoints": "never",
        "spanNulls": false
      },
      "min": 0,
      "thresholds": { "mode": "absolute", "steps": [{ "color": "green", "value": null }] }
    },
    "overrides": []
  },
  "options": {
    "legend": { "calcs": ["lastNotNull"], "displayMode": "list", "placement": "bottom", "showLegend": true },
    "tooltip": { "mode": "multi", "sort": "none" }
  },
  "pluginVersion": "10.4.10",
  "targets": []
}
```

- **新建盘**：`datasource.uid` 用 `${DS_蓝鲸监控_- 指标数据}`
- **往已有盘加图**：复制该盘已有 panel 的 datasource uid，不要改成模板变量

## UI target

```json
{
  "datasource": { "type": "bkmonitor-timeseries-datasource", "uid": "000000002" },
  "format": "time_series",
  "mode": "ui",
  "query_configs": [],
  "refId": "A",
  "source": "",
  "type": "range"
}
```

`query_configs` 内容见 `promql-dialect.md`。

## Code target

```json
{
  "cluster": [],
  "datasource": { "type": "bkmonitor-timeseries-datasource", "uid": "000000002" },
  "enableDownSampling": true,
  "expressionList": [],
  "format": "time_series",
  "host": [],
  "mode": "code",
  "module": [],
  "promqlAlias": "今日",
  "query_configs": [],
  "refId": "A",
  "source": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
  "step": "",
  "type": "range"
}
```

## Stat

`type: "stat"`。`options` 用脚本 `set_type` 的默认即可，或：

```json
{
  "colorMode": "value",
  "graphMode": "area",
  "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
  "textMode": "auto"
}
```

`gridPos` 单位是 Grafana 网格：宽 24 列。默认一张图 `w: 12, h: 8`。
