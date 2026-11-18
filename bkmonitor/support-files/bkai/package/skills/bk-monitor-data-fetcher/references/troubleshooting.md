# 常见问题与解决方案

本文档记录在使用MCP数据拉取工具时遇到的常见问题及解决方案,帮助快速定位和解决问题。

## 目录

- [配置相关问题](#配置相关问题)
- [协议相关问题](#协议相关问题)
- [响应格式问题](#响应格式问题)
- [参数格式问题](#参数格式问题)
- [网络和认证问题](#网络和认证问题)

---

## 配置相关问题

### 问题1: 服务器名称不存在

**错误信息**:
```
ValueError: 服务器 'user-bk-monitor-prod-metrics-query' 不存在
```

**原因**: MCP配置文件中的服务器名称与代码中使用的名称不匹配。

**解决方案**:

1. 检查自动发现到的配置文件和实际服务器名称:
```python
from mcp_data_fetcher import MCPClient
client = MCPClient()
client.validate_config()
```

2. Server 名称以实际配置为准。`bk-monitor-prod-metrics-query` 与带 `user-` 前缀的名称都可能有效，不能自行删改前缀。

3. 使用 `client.find_server(confirmed_env, "metrics-query")` 在已确认环境中查找唯一名称。缺失或多匹配时停止；自定义名称通过 `call_tool` 精确指定，不跨环境回退。

**预防措施**:
- 使用 `client.list_servers()` 动态获取可用服务器列表
- 在脚本开始时打印可用服务器,方便调试

---

## 协议相关问题

### 问题2: 协议字段名称不一致

**错误信息**:
```
ValueError: 服务器 'xxx' 不是streamableHttp协议: None
```

**原因**: MCP配置文件中使用 `type` 字段而非 `transport` 字段标识协议类型。

**配置文件格式**:
```json
{
  "mcpServers": {
    "bk-monitor-prod-metrics-query": {
      "type": "streamableHttp",  // 注意: 是 type 不是 transport
      "url": "https://...",
      "headers": {...}
    }
  }
}
```

**解决方案**:

代码中同时检查 `type` 和 `transport` 字段:
```python
transport = server_config.get("type") or server_config.get("transport")
```

**历史背景**: 早期MCP配置使用 `transport` 字段,新版本改为 `type` 字段。为了兼容性,建议同时支持两者。

---

## 响应格式问题

### 问题3: JSON解析失败 - SSE格式响应

**错误信息**:
```
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**: Streamable HTTP协议返回的是 `text/event-stream` 格式,不是直接的JSON。

**响应格式示例**:
```
data: {"jsonrpc":"2.0","id":"xxx","result":{...}}

```

**解决方案**:

1. 客户端已自动识别（参考 `_decode_jsonrpc_body` 实现），无需在调用方手动处理。
2. 如必须手动解析，按 SSE 标准只取 `data:` 前缀的行，拼接后再 JSON 解码。

**关键点**:
- SSE 每个事件由若干 `data:` 行组成，行之间可能有空行作为事件分隔
- `event:` / `id:` / `retry:` / `:` (注释) 行需忽略
- 同一事件多行 `data:` 必须按顺序拼接（流式 JSON 可能被 chunk 截断）

---

### 问题3.1: 响应为 SSE 但解析不出 JSON-RPC 对象（v3.4.0+）

**错误信息**:
```
MCPProtocolError: 响应无法解析为合法的 JSON-RPC 对象 (tool=xxx, content_type=text/event-stream)
  尝试: primary-sse: SSE 解析未匹配到 JSON-RPC 对象; fallback-json: JSON 解析失败: ...
  响应内容(前 200 字符): : ping\n\n
```

**触发场景**：

1. **服务端只发了心跳/keepalive**：响应正文是 `: ping\n\n` 或 `event: keepalive\n\n`，没有真正的 `data:` 帧。
2. **网关 chunk 截断**：长 JSON 被中间设备拆包，`data:` 行不连续。常见于跨地域、慢链路或代理超时（502/503/504）。
3. **服务端误标 Content-Type**：实际正文是完整 JSON，但响应头标了 `text/event-stream`（已自动回退处理）。
4. **第二次/连续调用首次失败**：HTTP 连接复用时上次响应未读完导致 body 污染（已通过显式 `response.close()` 修复）。

**v3.4.0 起的自愈能力**：

- `_parse_sse_response` 兼容 `event:`/`id:`/`retry:`/`:` 注释行、`[DONE]` 终结符、心跳事件。
- `_decode_jsonrpc_body` 在 SSE 与 JSON 之间双向回退（误标 Content-Type 也可解析）。
- `MCPProtocolError` 已纳入 `call_tool` 和 `call_bkm_tool` 默认重试范围，均为 `retries=1`。
- `_call_tool_*` 在 `try/finally` 中显式关闭 `requests.Response`，避免连接池污染。

**v3.6.0 起的进一步增强**：

- **streamableHttp / http / remote 改走 `stream=True` 流式读取**：实时按 SSE 帧解析，命中 `request_id` 立即返回，规避网关 buffering 与大响应截断。
- **跨事件 `data:` 拼接 fallback**：兼容某些非规范 MCP 服务器把单个 JSON 拆到多个 SSE 事件的情况。
- **强制 UTF-8 解码**：MCP 协议规定 UTF-8，避免 charset 误判。
- **解析失败自动 dump 原始响应**：保存到 `bkmonitor-files/_mcp_failed_responses/<tool>_<ts>_<reqid>.txt`，错误信息中包含文件路径。

**仍未恢复时的人工排查**：

1. **本地查看 dump 文件**：`MCPProtocolError` 错误信息会指出 `原始响应已保存: <path>`。先按最小范围检查计数和解析失败原因；对外反馈前移除地址、凭据和业务内容，不直接发送完整文件。
2. 增大 `retries`：`client.call_tool(server, tool, args, retries=3, timeout=120)`。
3. 缩窄查询时间范围：单次窗口 ≤ 24h，必要时拆成多个 1h 子查询。
4. 直接 `curl -i -N -X POST <mcp_url> -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '<jsonrpc payload>'`（注意 `-N` 关闭 buffering）抓原始响应，确认是网关问题还是客户端解析问题。

**Dump 文件格式**：

```
# tool: search_event_log
# request_id: 6f1a-...
# content_type: text/event-stream
# body_bytes: 1024
# line_count: 18, data_lines: 6
# attempt[primary-sse]: SSE 解析未匹配到 JSON-RPC 对象
# attempt[fallback-json]: JSON 解析失败: ...
# attempt[fallback-concatenated-sse]: 拼接 6 条 data: 行后仍非合法 JSON
# --- raw body ---
event: message
data: ...
```

---

## 参数格式问题

### 问题4: 参数格式错误 - body_param vs query_param

**错误信息**:
```
400 Bad Request
或
参数缺失错误
```

**原因**: 不同的MCP工具使用不同的参数格式。

**规则**:
- **POST请求** → 使用 `body_param`
- **GET请求** → 使用 `query_param`

**如何确定使用哪种格式**:

1. 查看MCP工具定义文件:
```bash
cat ~/.cursor/projects/.../mcps/<server-name>/tools/<tool-name>.json
```

2. 检查 `arguments` 字段中的 `properties` 或 `patternProperties`:
   - 如果包含 `body_param` → 使用 `{"body_param": {...}}`
   - 如果包含 `query_param` → 使用 `{"query_param": {...}}`

**示例对比**:

```python
# POST请求 - 指标查询
{
    "body_param": {
        "bk_biz_id": "<bk_biz_id>",
        "promql": "...",
        "start_time": "...",
        "end_time": "..."
    }
}

# GET请求 - 获取应用列表
{
    "query_param": {
        "bk_biz_id": "<bk_biz_id>"
    }
}
```

---

## 网络和认证问题

### 问题5: 认证失败

**错误信息**:
```
401 Unauthorized
或
403 Forbidden
```

**原因**:
1. Token过期或无效
2. Token格式错误
3. 缺少必要的请求头

**解决方案**:

1. 检查当前客户端实际使用的 MCP 配置文件。`MCPClient().validate_config()` 会打印配置路径；如运行环境已有固定凭证文件,优先设置 `BK_MCP_CONFIG_PATH` / `BKM_MCP_CONFIG_PATH` / `MCP_CONFIG_PATH`。

2. Token格式应该是:
```json
{
  "headers": {
    "X-Bkapi-Authorization": "{\"access_token\":\"YOUR_TOKEN\"}"
  }
}
```

3. 如果Token过期,需要重新获取并更新配置文件。

**预防措施**:
- 定期检查Token有效期
- 在脚本中添加认证错误的友好提示

---

### 问题6: 网络超时

**错误信息**:
```
requests.exceptions.Timeout: ...
或
requests.exceptions.ConnectionError: ...
```

**原因**:
1. 网络连接问题
2. 服务器响应慢
3. 超时设置过短

**解决方案**:

1. 增加超时时间:
```python
client.call_tool(server, tool, args, timeout=120)  # 增加到120秒
```

2. 检查网络连接:
```bash
curl -I https://gateway.example.com
```

3. 对于大数据量查询,考虑分批处理:
```python
# 将1天的查询拆分为多个1小时的查询
for hour in range(24):
    start = base_time + hour * 3600
    end = start + 3600
    result = query_data(start, end)
```

---

## 数据查询问题

### 问题7: 查询时间范围超限

**错误信息**:
```
查询跨度不得超过1天(86400秒)
```

**原因**: MCP工具对单次查询的时间范围有限制。

**解决方案**:

实现分批查询:
```python
def query_large_timerange(start_time, end_time, step=86400):
    """分批查询大时间范围的数据"""
    results = []
    current = start_time

    while current < end_time:
        batch_end = min(current + step, end_time)
        result = client.call_tool(server, tool, {
            "body_param": {
                "start_time": str(current),
                "end_time": str(batch_end),
                ...
            }
        })
        results.append(result)
        current = batch_end

    return merge_results(results)
```

---

### 问题8: 时间戳格式错误

**错误信息**:
```
时间格式错误
或
Invalid timestamp
```

**原因**:
1. 使用了毫秒时间戳而非秒时间戳
2. 时间戳是数字而非字符串

**正确格式**:
```python
import time

# ✅ 正确: 秒级时间戳,字符串格式
end_time = str(int(time.time()))
start_time = str(int(time.time()) - 3600)

# ❌ 错误: 毫秒时间戳
end_time = int(time.time() * 1000)

# ❌ 错误: 数字格式
end_time = int(time.time())
```

**关键点**:
- 使用**秒级**Unix时间戳
- 转换为**字符串**格式
- 确保 `start_time < end_time`

---

## 调试技巧

### 技巧1: 记录不含凭据的请求摘要

```python
print(f"工具: {tool_name}")
print(f"参数字段: {list(arguments)}")
```

### 技巧2: 保存原始响应

```python
# 保存响应用于分析
with open('debug_response.txt', 'w') as f:
    f.write(f"Status: {response.status_code}\n")
    f.write(f"Headers: {dict(response.headers)}\n")
    f.write(f"Body: {response.text}\n")
```

### 技巧3: 使用try-except捕获详细错误

```python
try:
    result = client.call_tool(server, tool, args)
except Exception as e:
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
    import traceback
    traceback.print_exc()
```

### 技巧4: 验证配置文件

```python
from mcp_data_fetcher import MCPClient

def validate_mcp_config():
    """验证MCP配置文件"""
    try:
        return MCPClient().validate_config()
    except Exception as e:
        print(f"❌ 配置文件解析失败: {e}")
        return False
```

---

## 最佳实践

### 1. 始终验证配置

在脚本开始时验证MCP配置:
```python
if __name__ == "__main__":
    if not validate_mcp_config():
        sys.exit(1)
    # 继续执行...
```

### 2. 提供友好的错误提示

```python
try:
    result = client.call_tool(server, tool, args)
except ValueError as e:
    if "不存在" in str(e):
        print(f"\n💡 提示: 请检查服务器名称是否正确")
        print(f"   可用服务器: {client.list_servers()}")
    raise
```

### 3. 记录成功的查询

```python
# 保存查询历史,方便后续参考
query_log = {
    "timestamp": time.time(),
    "server": server_name,
    "tool": tool_name,
    "arguments": arguments,
    "success": True
}
with open("query_history.jsonl", "a") as f:
    f.write(json.dumps(query_log) + "\n")
```

### 4. 使用配置文件管理常用参数

```python
# config.json
{
    "selected_biz_id": "<bk_biz_id>",
    "default_timeout": 60,
    "default_step": "1m"
}

# 在脚本中加载
with open("config.json") as f:
    config = json.load(f)
```

---

## 快速诊断清单

遇到问题时,按此清单逐项检查:

- [ ] MCP配置文件存在且格式正确
- [ ] 服务器名称与配置文件中的名称完全匹配
- [ ] 协议类型正确识别(type/transport字段；bkai-code 为 `remote`)
- [ ] 参数格式正确(body_param/query_param)
- [ ] 时间戳格式正确(秒级,字符串)
- [ ] 时间范围在允许的限制内(<1天)
- [ ] Token有效且格式正确
- [ ] 网络连接正常
- [ ] 响应格式正确处理(SSE/JSON/JSONC)
- [ ] bkai-code 配置使用顶层 `mcp`,脚本会按 OpenCode 远端 MCP 读取

---

## 获取帮助

如果以上方案都无法解决问题:

1. 查看完整的错误堆栈信息
2. 在本地保留原始证据，对外反馈前移除凭据、地址及业务内容
3. 检查MCP工具的定义文件
4. 参考 `mcp_tools_guide.md` 中的工具说明
5. 查看成功的查询示例进行对比
