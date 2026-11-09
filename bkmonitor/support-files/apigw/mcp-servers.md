# 监控 API 网关与 MCP Server 同步

`definition.yaml` 维护 `bk-monitor` 网关、发布环境和 MCP Server；`resources/` 维护工具对应的 OpenAPI 资源。
部署使用现有的 `python manage.py sync_apigw`：合并资源、同步网关与环境、同步资源与文档、发布资源版本，随后执行
`sync_apigw_stage_mcp_servers`，最后同步应用授权与网关公钥。发布或 MCP 同步失败会使命令失败。

配置采用 `spec_version: 2`，每次只声明 `APIGW_STAGE` 对应的 `prod` 或 `stage`。后端地址、60 秒超时和
`x-bkapi-from: apigw` 沿用已有配置。`SYNC_APIGATEWAY_ENABLED=False` 时跳过整个同步流程。

## Server 与权限

声明包含 16 个公开业务 Server。`name` 使用现有名称的后缀，例如 `alarm`，网关生成
`bk-monitor-prod-alarm`。同名 Server 原位更新，既有访问地址保持有效；未声明的 Server 不由此接口删除。

全部声明的 Server 使用 Streamable HTTP，开启 OAuth2 公开客户端模式和个人令牌，关闭原始响应。
内部运营入口 `operation-data-query` 不再使用，不纳入注册。线上既有入口不由本次同步停用或删除。
声明不配置额外的 `target_app_codes`；普通应用的已有 Server 授权由网关保留。
Server 的个人令牌开关与每个 API 资源的 `oauth2PersonalClientEnabled` 是两层控制；本次不修改资源级鉴权设置。

工具以 `resource_names` 显式列出，工具名沿用资源的 `operationId`，包括 `apm_mcp_calculate_by_range`。
新增工具时应同时更新资源声明、对应 Server 清单及 `release.version`。`operation_mcp.yaml` 不纳入 Server 注册，
`ops_mcp.yaml` 和 `openclaw_recovering_mcp.yaml` 属于专用入口，本次不注册成通用业务 Server。

## 三环境核对记录

2026-11-09 通过各环境 `bk-monitor` 网关的 MCP Server 列表和编辑表单只读核对，均为 `prod`。
下表数字为表单中的已选工具数，`—` 表示该网关没有注册此 Server。核对时未保存任何网关配置。

| Server 后缀 | BKOP | BKTE | BK2GAME | 声明工具数 |
| --- | ---: | ---: | ---: | ---: |
| metadata-query | — | — | 2 | 2 |
| metrics-query | — | 4 | 4 | 4 |
| log-query | — | 5 | 6 | 6 |
| log-scene-search | 4 | — | — | 4 |
| event-query | — | — | 3 | 3 |
| alarm | — | 10 | 11 | 12 |
| alarm-handling | 18 | 17 | — | 18 |
| dashboard-query | — | — | 2 | 2 |
| dashboard-edit | — | — | 2 | 2 |
| tracing | — | — | 7 | 7 |
| profiling-query | 4 | 4 | 4 | 4 |
| relation-query | — | — | 2 | 2 |
| log-collector | 17 | 17 | — | 17 |
| log-extract | 7 | — | — | 7 |
| recording-rule | 7 | 7 | — | 7 |
| unified | 5 | 5 | — | 5 |
| operation-data-query（不公开，已排除） | 3 | — | — | — |
| Server 总数 | 8 | 8 | 10 | 16 |

本次只管理表中 16 个公开 Server。BKOP 已有的内部运营 Server 不由本次同步删除，若没有其他变更，
其网关列表发布后预计共 17 个；BKTE、BK2GAME 预计各 16 个。

已有同名 Server 的工具均被保留。BKTE 的 `log-query` 补充 `search_index_set_context`，`alarm` 补充
`get_strategy_snapshot` 与 `get_strategy_detail`，`alarm-handling` 补充 `create_alarm_notice_group`；
BK2GAME 的 `alarm` 补充 `get_strategy_detail`。其他缺失 Server 在对应环境发布此代码时创建。
核对范围为上述三个环境的 `bk-monitor` 网关；旧网关及其他环境尚未核对。

## 验证与发布验收

安装项目锁定的依赖后，可在 `bkmonitor/` 执行独立测试，无需网关凭据或业务数据库：

```bash
python -m pytest -c /dev/null -p no:cacheprovider \
  support-files/apigw/scripts/test_merge_resources.py \
  support-files/apigw/scripts/test_mcp_servers.py -q
```

测试验证 prod/stage 模板渲染、后端配置兼容、工具存在及请求 Schema、查询/写入分组、Server 名称与认证开关、真实 SDK
命令加载和发布顺序，并覆盖资源合并、资源发布及 MCP 同步失败场景。测试通过仅表示本地验证通过。

线上验收需在每个环境发布后单独完成：

1. 确认资源版本 `0.0.8` 已在目标 stage 生效，MCP 同步日志中的 Server 名称和数量与声明一致。
2. 若网关返回 `pending`，等待网关异步同步完成，回读 Server 清单；命令退出成功不等于异步同步已经完成。
3. 对照声明检查 `tools/list`，确认补充工具可见、现有应用授权保留，且内部运营入口未被新增注册。
4. 使用当前用户凭据执行指标、日志、告警等只读查询，分别验证业务成功与权限不足时的响应。

资源同步沿用原有 `--delete` 行为，执行真实命令会修改网关资源并发布版本；上述测试不执行真实同步。

参考：[apigw-manager 同步文档](https://github.com/TencentBlueKing/bkpaas-python-sdk/blob/master/sdks/apigw-manager/docs/sync_apigateway.md)、
[API 网关 MCP 保存逻辑](https://github.com/TencentBlueKing/blueking-apigateway/blob/master/src/dashboard/apigateway/apigateway/biz/mcp_server/mcp_server.py)。
