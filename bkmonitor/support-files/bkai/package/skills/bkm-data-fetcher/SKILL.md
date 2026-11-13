---
name: bkm-data-fetcher
description: 通过目标环境已配置的 MCP 直接拉取蓝鲸日志、指标、链路和告警数据，保存为本地 JSON 并进行脚本统计。适用于需要批量取数、保留原始返回或避免把大 JSON 放入模型上下文的查询；告警、采集等配置写入交给对应 Skill。
---

# 观测数据拉取

使用随包的 Python 客户端读取目标环境 MCP 配置，直接请求工具并把结果写入用户工作目录。需要 Python 3.10+ 和 `requirements.txt` 中的 requests、PyYAML。

## 环境与权限

1. 先确认目标环境、业务范围和时间窗口。通过 `BK_MCP_CONFIG_PATH` 指定该环境已有的 JSON、JSONC 或 Hermes YAML 配置，配置与凭据由运行环境提供。
2. 用 `MCPClient().list_servers(show_details=True)` 列出可用 Server，再读取宿主提供的实时工具 schema。此 Skill 不创建 MCP、不申请权限，也不根据示例猜地址或账号。
3. `find_server(env, service)` 只匹配明确指定环境中的标准名称；缺失或多匹配时停止。自定义别名使用 `call_tool` 精确指定配置中的完整名称，不跨环境回退。
4. 本 Skill 的操作范围是只读查询。配置变更使用对应的告警或日志采集 Skill，并遵守其写入确认与回查要求。
5. 时间戳使用 Unix 秒字符串，单次指标或日志查询窗口不超过 86400 秒。更长范围由调用方拆分，并说明覆盖区间、重复和截断情况。

## 定位脚本

根据当前 `SKILL.md` 的真实位置确定 Skill 根目录，使用绝对路径执行脚本；输出路径放在用户工作目录，不在安装目录里生成业务数据。

```bash
export BK_MCP_CONFIG_PATH=/path/to/target-mcp.json
python /path/to/bkm-data-fetcher/scripts/fetch_metrics.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --metric cpu --hours 1 \
  --output bkmonitor-files/cpu.json

python /path/to/bkm-data-fetcher/scripts/fetch_logs.py \
  --biz-id '<bk_biz_id>' --env '<confirmed-stage>' --list-indexes
```

`--env` 是目标配置里的环境标识，不预设环境列表或默认环境。脚本支持 `bk-monitor-{env}-{service}`、`bkm-{env}-{service}` 及客户端的 `user-` 前缀；完整名称必须来自已确认的配置。

## 通用 API

使用前把 `<skill-directory>` 和 `<configured-server>` 替换为实际发现结果。参数结构以实时 schema 为准；下例仅展示指标查询的字段语义。

```python
import sys
import time

sys.path.insert(0, "<skill-directory>/scripts")
from mcp_data_fetcher import MCPClient, output_result, parse_mcp_result, raise_if_business_error

client = MCPClient(mcp_config_path="/path/to/target-mcp.json")
client.list_servers(show_details=True)
end = int(time.time())
result = client.call_tool("<configured-server>", "execute_range_query", {
    "body_param": {
        "bk_biz_id": "<bk_biz_id>",
        "promql": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
        "start_time": str(end - 3600),
        "end_time": str(end),
        "step": "1m"
    }
})
raise_if_business_error(result)
parsed = parse_mcp_result(result)
body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
output_result(body, "bkmonitor-files/cpu.json")
```

`call_bkm_tool(env, service, tool, payload)` 提供标准名称查找、常用 GET/POST 参数包装和业务错误检查。其内置包装表只能作为常用默认值；与实时 schema 不同时使用 `call_tool` 提交明确的 `query_param` 或 `body_param`。

## 配置与协议

- 显式配置路径或 `BK_MCP_CONFIG_PATH`、`BKM_MCP_CONFIG_PATH`、`MCP_CONFIG_PATH` 优先；无效时直接报错，不退回另一份配置。
- 显式 `HERMES_HOME` 时读取其 `config.yaml`；未指定显式路径时才发现已安装客户端的配置文件。完整顺序见 [配置与 API 指南](COMPLETE_GUIDE.md)。
- JSON/JSONC 支持 `mcpServers`、项目嵌套 `projects.*.mcpServers` 和 OpenCode 的 `mcp`；Hermes YAML 支持 `mcp_servers`。
- 支持 `sse`、`streamableHttp`、`http`、`remote`。不根据 URL 后缀猜协议。
- Hermes YAML 使用安全解析，环境变量只从当前进程展开；缺失变量、未知或无法保持的认证、TLS、工具过滤配置报错。禁用项与 stdio 不执行，安全模式不暴露服务。
- JSON 配置示例见 [mcp.example.json](resources/mcp.example.json)。它只说明结构，运行时应挂载或注入目标配置，不能直接使用示例地址或凭据占位值。

## 返回与失败

保留原始返回、请求标识及已执行的查询范围。对大 JSON 使用脚本统计计数、分布和分位，不通过人工扫样本推断总体。

HTTP 401、业务错误和协议错误必须分别报告；网络、协议解析和部分服务端错误只进行有限重试。解析失败时客户端可能把原始响应保存在工作目录的失败响应文件中，排查时按最小范围读取，不能把这些文件放入外发包。

日志分批脚本按时间片取数，可能受每批条数和最大批次数限制；不能据此声称完整覆盖或没有重复。输出应说明窗口、返回数、截断和未完成项。任务失败或只有部分数据时，不把它描述成完整成功。

## 按需参考

| 任务 | 参考 |
| --- | --- |
| 配置来源、客户端 API、结果解析 | [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) |
| 工具参数和 GET/POST 包装 | [mcp_tools_guide.md](references/mcp_tools_guide.md) |
| 常用系统指标 | [system-metrics.md](references/system-metrics.md) |
| 配置、协议或查询错误 | [troubleshooting.md](references/troubleshooting.md) |
| 指标、日志和 CPU 脚本参数 | [scripts/README.md](scripts/README.md) |
