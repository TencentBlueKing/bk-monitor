# 配置与客户端 API

所有名称、地址、业务和索引集均由用户选择或目标环境发现，不从示例继承。

## 配置发现

显式传入 `MCPClient(mcp_config_path=...)` 时只读取该文件。否则依次检查：

1. `BK_MCP_CONFIG_PATH`、`BKM_MCP_CONFIG_PATH`、`MCP_CONFIG_PATH`。
2. 显式 `HERMES_HOME` 中的 `config.yaml`。
3. Cursor 的用户级配置，然后当前目录和工作区的项目配置。
4. CodeBuddy 的用户级和项目配置。
5. OpenCode、Windsurf、VS Code 的相应配置。
6. 当前目录和工作区的 `.mcp.json`，以及 Claude 客户端的用户级配置。
7. OpenClaw 的 mcporter 配置。
8. 未显式选择 `HERMES_HOME` 时的 `~/.hermes/config.yaml`。

显式路径和显式 Hermes Home 失败时停止，不自动改读其他来源。自动发现配置后仍需确认它属于本次目标环境。

Hermes YAML 使用 `mcp_servers`，支持 `${VAR}` 引用当前进程环境变量，不加载额外秘密文件。JSON/JSONC 不进行该环境变量展开，凭据应由部署系统在运行时提供。客户端不会改写原配置。

## 服务器选择

`client.list_servers(show_details=True)` 只展示支持的 Server 名称与协议，不展示认证 Header。

标准命名使用 `bk-monitor-{env}-{service}` 或 `bkm-{env}-{service}`，也识别客户端的 `user-` 前缀。`env` 可以是目标配置使用的任意合法标签；`prod`、`stage` 等只是示例。

`client.find_server(env, service)` 在指定环境内必须匹配唯一结果。缺失、多匹配或完整名称与环境不一致时均报错。对于自定义别名，使用已确认的完整名称调用 `client.call_tool`。

## 调用与参数

- `call_tool(server_name, tool_name, arguments, timeout=60, retries=1)`：使用完整名称和实时 schema 定义的参数。
- `call_bkm_tool(env, service, tool_name, payload, timeout=60, retries=1)`：查找标准名称、按常用工具表包装参数并检查业务错误。
- `resolve_server_target(env, service_or_name)`：解析标准名称；环境冲突时报错。
- `build_server_name(env, service)`：只构造标准名称，不证明服务器存在或已授权。
- `parse_mcp_result(result)`：解析文本 JSON、fenced JSON、MCP 内容块和 SSE JSON-RPC 返回。
- `raise_if_business_error(result)`：业务层明确失败时抛出错误。
- `output_result(result, path)`：保存 JSON，并打印结构提示。
- `client.save_result(result, filename)`：保存到工作目录的 `bkmonitor-files`；filename 只传文件名。

GET/POST 包装以实时 schema 为准。常用默认表与实际接口不一致时，调用 `call_tool` 并明确提供 `query_param` 或 `body_param`。

## 协议和错误

客户端支持 SSE、Streamable HTTP、HTTP JSON-RPC 和远端 HTTP 别名。SSE 心跳、分帧、跨事件 JSON 和 Content-Type 误标由协议层处理，请求结束后关闭响应。

网络、协议解析以及部分服务端暂时错误可有限重试；身份和权限错误不通过切换环境解决。JSON-RPC 错误、业务错误、解析失败和成功返回没有数据应分别说明。原始失败响应可能写入工作目录，仅供当前排查使用，不能作为外发示例。

## 长时间与大量数据

内置指标和日志脚本的单次窗口上限为 24 小时。更长时间由调用方拆分；逐批记录范围和错误，不把部分完成当作全部完成。日志时间片取数可能截断或重叠，需说明限制，不能只按返回条数推断数据完整。
