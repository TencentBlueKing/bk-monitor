# AG-UI 小鲸后台接口

后台契约对齐 `@blueking/ai-blueking`、`@blueking/chat-helper` 的 `3.1.0-beta.6` AG-UI 版本。前端组件由前端项目升级；本目录不包含前端升级代码。

## 启用与保存职责

升级环境同时配置 `AI_AGENT_BACKEND=hermes`、`AI_AGENT_STREAM_PROTOCOL=agui`。公共默认仍为 `aidev` / `legacy`，原有客户端继续使用旧协议；不要在旧前端上单独切换流式协议。

AG-UI 模式下，前端保存用户消息，后台保存本轮 AI 正文、工具调用和工具结果，前端不再创建或更新 AI 占位消息。底层执行器只产出事件；HTTP 适配层是本轮 AI 消息的唯一保存方。调用方必须先确认用户消息保存成功，再发起执行。

后台依赖平台现有的用户身份、会话和 `property.turn_id`。流内消息 ID 同时写入 `property.builtin_property.message_id`；工具调用、结果通过同一 `tool_call_id` 关联。历史恢复沿用同一平台接口，不启用 SDK 会话库。

## API

以下路径均相对于 `/ai_whale/chat/`，保留现有登录态、业务权限及当前用户工具授权。普通 JSON 响应只包含宿主的一层 `result/data`，不再嵌套第二层平台响应；平台错误不能转换为空列表或成功。

| 方法与路径 | 输入与返回 |
|---|---|
| `POST session/` | `session_code`、`session_name`、可选 `agent_code` / `is_temporary`；后台补齐 `channel_type=popup`、`protocol_version=v2`、`session_type=agent` |
| `GET session/` | 可选 `session_code`，或 `page`、`page_size`；分页返回 `results/count/page/num_pages`，保留平台分页信息 |
| `GET session/{session_code}/` | 获取单个会话 |
| `PUT/DELETE session/{session_code}/` | 沿用会话更新、删除接口 |
| `POST session_content/` | 保存用户消息；支持 `input` 或 `content`、`message_id`、`property` |
| `GET session_content/content/?session_code=...` | 返回消息数组，保留正文/工具顺序，过滤客户端不支持的历史角色 |
| `PUT session_content/{id}/` | 支持仅更新状态或元数据，不用缺省值覆盖既有正文 |
| `POST chat_completion/` | `session_code`、`execute_kwargs: {"stream": true}`，可选 `agent_code`、`messageId` |
| `POST session_content/stop/` | `session_code`；按当前登录用户请求取消当前流，返回 `stopped` |

客户端的 `message_id/tool_calls/tool_call_id/error` 写入平台的 `property.builtin_property`，`duration` 写入其中的 `additional_kwargs`。支持字符串、对象和对象列表正文；结构化工具消息允许空正文。非流式 `stream=false` 保留旧调用方保存职责，不返回 AG-UI 事件。

停止标记使用宿主共享缓存，使停止请求可以到达另一 Worker 的流；缓存需使用共享 Redis 或数据库后端。SDK 在下一次事件/心跳时处理取消，已经开始的外部工具是否立即停止取决于其 transport。返回 `stopped=true` 表示找到运行中的流并登记取消，不表示外部副作用已回滚。

## 流式事件

响应为 `text/event-stream`，每帧为 `data: {JSON}\n\n`。JSON 使用 AG-UI 的 `type` 字段，保活也是 JSON `RAW`；不向 AG-UI 客户端输出 SSE 注释或 `[DONE]`。

正常回合：

```text
RUN_STARTED
TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END
TOOL_CALL_START → TOOL_CALL_ARGS → TOOL_CALL_END → TOOL_CALL_RESULT
TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END
RUN_FINISHED
```

`RUN_STARTED/RUN_FINISHED` 携带 `threadId/runId`；正文携带 `messageId`；工具携带 `toolCallId`。工具失败通过 `TOOL_CALL_RESULT.isError` 表达，模型仍可继续解释失败。工具参数与结果先脱敏，再同时交给实时流和历史保存层。

执行失败、截断、停止或历史保存未确认以 `RUN_ERROR` 收尾，不能发送成功的 `RUN_FINISHED`。客户端关闭连接会释放 SDK；部分正文和缺失结果的工具保存为未完成状态。写入超时后不自动重试，避免已提交的消息被重复创建。

本轮覆盖通用聊天、工具过程、历史恢复与停止。业务阶段执行、业务页面上下文、人工确认中断和关联子 Agent 不由该通用接口自动实现；启用这些能力前需要独立的宿主契约和验收。
