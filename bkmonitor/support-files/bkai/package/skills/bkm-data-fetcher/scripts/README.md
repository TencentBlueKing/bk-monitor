# 拉取脚本

先安装 Skill 根目录 `requirements.txt` 中的依赖，并通过 `BK_MCP_CONFIG_PATH` 提供已确认的目标环境配置。配置不会随脚本写回。

## 指标

```bash
python /path/to/bkm-data-fetcher/scripts/fetch_metrics.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --metric cpu --hours 1 \
  --output bkmonitor-files/cpu.json
```

`--metric` 支持 cpu、memory、disk、load、net_recv、net_sent，或改用 `--promql`。两者不能同时传。可通过 `--start-time`、`--end-time` 指定 Unix 秒，通过 `--step` 设置查询步长。单次窗口不超过 86400 秒。

## 日志

```bash
python /path/to/bkm-data-fetcher/scripts/fetch_logs.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --list-indexes

python /path/to/bkm-data-fetcher/scripts/fetch_logs.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --index-set-id '<index_set_id>' \
  --hours 1 --query 'level:ERROR' --output bkmonitor-files/errors.json
```

也可使用 `--index-name` 搜索名称；存在多个匹配时改用精确 ID。`--limit` 控制单批数量，`--fetch-all` 按时间片分批，`--max-batches` 限制批次数。分批不保证全部取回或无重复，必须报告截断、重叠和失败。

## CPU 便捷入口

```bash
python /path/to/bkm-data-fetcher/scripts/fetch_cpu_data.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --hours 1
```

业务和环境均须明确指定，不继承示例值。

## 直接调用

标准名称查找失败或存在多个别名时，不选择第一项，也不跨环境回退。通过 `MCPClient.list_servers()` 选择配置里的完整名称，再按实时 schema 使用 `call_tool`。API 与配置优先级见 [完整指南](../COMPLETE_GUIDE.md)，工具字段见 [工具指南](../references/mcp_tools_guide.md)。
