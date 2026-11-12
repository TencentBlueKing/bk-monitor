# 纯用户态 API

新增 101 个支持个人令牌的纯用户态 API，网关路径为 `/user/<接口名>/`，资源名称为 `user_<接口名>`，
文档分组为“纯用户态接口”。无需填写应用凭证或申请网关应用权限；用户仍须具备相应业务、索引集、
APM 应用或其他目标资源的 IAM 权限。现有 MCP 地址、Server 工具清单和应用态接口保持兼容。

## 范围与原有开启状态

仓库中共有 111 个 MCP API 声明，均要求用户认证。其中 69 个原入口显式开启了 API 级个人令牌，42 个未开启。
本次将其中 101 个业务接口发布为纯用户态 API，全部开启个人令牌。原 MCP 入口的个人令牌开关不作批量修改。
运营数据 3 个、运维诊断 4 个、OpenClaw 专用入口 3 个不进入公共目录。

Server 的 `oauth2_personal_client_enabled` 与 API 的 `oauth2PersonalClientEnabled` 是不同配置。
下方“原入口个人令牌”只统计原 `/mcp/...` API 的显式声明，不代表目标环境已经发布或实测成功。

| 范围 | 原接口数 | 原入口已开启 | 原入口未开启 | 新增纯用户态 API |
| --- | ---: | ---: | ---: | ---: |
| 业务接口 | 101 | 69 | 32 | 101，全部开启 |
| 内部与专用接口 | 10 | 0 | 10 | 0 |
| 合计 | 111 | 69 | 42 | 101 |

## 调用与权限

使用个人令牌时携带请求头：

```http
Authorization: Bearer <personal-token>
```

例如查询日志检索接口的参数契约：

```bash
curl 'https://gateway.example.com/api/bk-monitor/prod/user/lookup_tool_schema/' \
  -H 'Authorization: Bearer <personal-token>' \
  -H 'Content-Type: application/json' \
  -d '{"tool_name":"search_logs"}'
```

多租户环境还需按目标环境契约携带 `X-Bk-Tenant-Id`，凭证身份、用户租户与目标业务必须一致。
后端验证网关签发的用户身份，再通过现有权限执行器检查参数、资源归属和 IAM；不依赖 MCP Server 请求头，
也不接受调用方指定权限点。已配置 SaaS 权限复用的接口沿用该配置，未配置的接口继续检查原业务权限。

写入、任务和导出接口必须提供 `confirm=true`。统一执行入口 `/user/execute_tool/` 的确认字段仍放在 `tool_args` 内。
业务参数采用现有统一工具目录的公共 Schema，不能传入内部身份或权限字段；仪表盘 `configs` 直接接收 JSON 对象。
调用成功时保留现有 API 响应格式，拒绝或参数错误时返回对应 HTTP 状态与错误信封。HTTP 200 仍需检查业务结果。

## 全量接口清单

“未开启”表示原 `/mcp/...` 资源未声明 `oauth2PersonalClientEnabled: true`；新目录中列出路径的接口均已在代码中开启。
旧路径通常为 `/mcp/<接口名>/`；`apm_mcp_calculate_by_range` 对应 `/mcp/calculate_by_range/`，
`list_bcs_clusters` 对应 `/mcp/search_bcs_clusters/`。纯用户态入口统一使用工具目录中的名称。
方法与新路径可以直接用于 CLI 的原始 API 调用。

### 元数据

共 2 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_bcs_clusters` | GET | 已开启 | `/user/list_bcs_clusters/` |
| `search_spaces` | GET | 已开启 | `/user/search_spaces/` |

### 指标

共 4 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_time_series_groups` | POST | 已开启 | `/user/list_time_series_groups/` |
| `list_time_series_metrics` | GET | 已开启 | `/user/list_time_series_metrics/` |
| `execute_range_query` | POST | 已开启 | `/user/execute_range_query/` |
| `execute_sql_query` | POST | 已开启 | `/user/execute_sql_query/` |

### 日志检索

共 9 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_index_sets` | GET | 已开启 | `/user/list_index_sets/` |
| `get_index_set_fields` | GET | 已开启 | `/user/get_index_set_fields/` |
| `search_logs` | POST | 已开启 | `/user/search_logs/` |
| `search_index_set_context` | POST | 已开启 | `/user/search_index_set_context/` |
| `list_log_scenes` | GET | 已开启 | `/user/list_log_scenes/` |
| `list_scene_dimension_values` | POST | 已开启 | `/user/list_scene_dimension_values/` |
| `get_scene_log_fields` | POST | 已开启 | `/user/get_scene_log_fields/` |
| `analyze_field` | POST | 已开启 | `/user/analyze_field/` |
| `search_log_clustering_pattern` | POST | 已开启 | `/user/search_log_clustering_pattern/` |

### 事件

共 3 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_events` | POST | 已开启 | `/user/list_events/` |
| `get_event_view_config` | POST | 已开启 | `/user/get_event_view_config/` |
| `search_event_log` | POST | 已开启 | `/user/search_event_log/` |

### 告警查询

共 12 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_alerts` | POST | 已开启 | `/user/list_alerts/` |
| `get_alert_top_n` | POST | 已开启 | `/user/get_alert_top_n/` |
| `get_strategy_snapshot` | POST | 已开启 | `/user/get_strategy_snapshot/` |
| `get_strategy_detail` | GET | 已开启 | `/user/get_strategy_detail/` |
| `get_alert_info` | GET | 已开启 | `/user/get_alert_info/` |
| `get_alert_events` | POST | 已开启 | `/user/get_alert_events/` |
| `get_alert_event_ts` | POST | 已开启 | `/user/get_alert_event_ts/` |
| `get_alert_event_tag_detail` | POST | 已开启 | `/user/get_alert_event_tag_detail/` |
| `get_alert_k8s_target` | GET | 已开启 | `/user/get_alert_k8s_target/` |
| `get_alert_host_target` | GET | 已开启 | `/user/get_alert_host_target/` |
| `get_alert_traces` | POST | 已开启 | `/user/get_alert_traces/` |
| `get_alert_log_relations` | GET | 已开启 | `/user/get_alert_log_relations/` |

### 告警处置

共 18 个，原入口未开启 10 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `search_alarm_strategies` | POST | 已开启 | `/user/search_alarm_strategies/` |
| `get_alarm_strategy` | POST | 已开启 | `/user/get_alarm_strategy/` |
| `create_alarm_strategy` | POST | **未开启** | `/user/create_alarm_strategy/` |
| `update_alarm_strategy` | POST | **未开启** | `/user/update_alarm_strategy/` |
| `search_alarm_shields` | POST | 已开启 | `/user/search_alarm_shields/` |
| `get_alarm_shield` | GET | 已开启 | `/user/get_alarm_shield/` |
| `create_alarm_shield` | POST | **未开启** | `/user/create_alarm_shield/` |
| `update_alarm_shield` | POST | **未开启** | `/user/update_alarm_shield/` |
| `disable_alarm_shield` | POST | **未开启** | `/user/disable_alarm_shield/` |
| `search_alarm_notice_groups` | POST | 已开启 | `/user/search_alarm_notice_groups/` |
| `create_alarm_notice_group` | POST | **未开启** | `/user/create_alarm_notice_group/` |
| `update_alarm_notice_group` | POST | **未开启** | `/user/update_alarm_notice_group/` |
| `search_alarm_action_configs` | GET | 已开启 | `/user/search_alarm_action_configs/` |
| `get_alarm_action_config` | GET | 已开启 | `/user/get_alarm_action_config/` |
| `update_alarm_action_config` | POST | **未开启** | `/user/update_alarm_action_config/` |
| `search_alarm_assign_groups` | POST | 已开启 | `/user/search_alarm_assign_groups/` |
| `save_alarm_assign_group` | POST | **未开启** | `/user/save_alarm_assign_group/` |
| `delete_alarm_assign_group` | POST | **未开启** | `/user/delete_alarm_assign_group/` |

### APM 与性能分析

共 11 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_apm_applications` | GET | 已开启 | `/user/list_apm_applications/` |
| `get_apm_filter_fields` | GET | 已开启 | `/user/get_apm_filter_fields/` |
| `search_spans` | POST | 已开启 | `/user/search_spans/` |
| `get_trace_detail` | POST | 已开启 | `/user/get_trace_detail/` |
| `get_span_detail` | POST | 已开启 | `/user/get_span_detail/` |
| `get_profile_application_service` | POST | 已开启 | `/user/get_profile_application_service/` |
| `get_profile_type` | POST | 已开启 | `/user/get_profile_type/` |
| `get_profile_label` | POST | 已开启 | `/user/get_profile_label/` |
| `query_graph_profile` | POST | 已开启 | `/user/query_graph_profile/` |
| `apm_mcp_calculate_by_range` | POST | 已开启 | `/user/calculate_by_range/` |
| `list_apm_services` | POST | 已开启 | `/user/list_apm_services/` |

### 仪表盘

共 4 个，原入口未开启 2 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `get_dashboard_tree_list` | GET | 已开启 | `/user/get_dashboard_tree_list/` |
| `get_dashboard_detail_by_uid` | GET | 已开启 | `/user/get_dashboard_detail_by_uid/` |
| `create_dashboard` | POST | **未开启** | `/user/create_dashboard/` |
| `update_dashboard` | POST | **未开启** | `/user/update_dashboard/` |

### 资源关联

共 2 个，原入口未开启 0 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `find_relations` | POST | 已开启 | `/user/find_relations/` |
| `find_relations_range` | POST | 已开启 | `/user/find_relations_range/` |

### 日志采集

共 17 个，原入口未开启 9 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `update_log_collector_clean_config` | POST | **未开启** | `/user/update_log_collector_clean_config/` |
| `fast_create_log_collector` | POST | **未开启** | `/user/fast_create_log_collector/` |
| `list_third_party_es_clusters` | GET | 已开启 | `/user/list_third_party_es_clusters/` |
| `list_result_tables` | GET | 已开启 | `/user/list_result_tables/` |
| `preview_log_etl` | POST | 已开启 | `/user/preview_log_etl/` |
| `list_log_index_set_groups` | GET | 已开启 | `/user/list_log_index_set_groups/` |
| `list_log_collectors` | GET | 已开启 | `/user/list_log_collectors/` |
| `get_log_collector` | GET | 已开启 | `/user/get_log_collector/` |
| `get_log_index_set` | GET | 已开启 | `/user/get_log_index_set/` |
| `create_custom_report` | POST | **未开启** | `/user/create_custom_report/` |
| `create_bkdata_index_set` | POST | **未开启** | `/user/create_bkdata_index_set/` |
| `create_third_party_es` | POST | **未开启** | `/user/create_third_party_es/` |
| `update_custom_report` | POST | **未开启** | `/user/update_custom_report/` |
| `update_third_party_es` | POST | **未开启** | `/user/update_third_party_es/` |
| `update_bkdata_index_set` | POST | **未开启** | `/user/update_bkdata_index_set/` |
| `get_log_collector_status` | POST | 已开启 | `/user/get_log_collector_status/` |
| `fast_update_log_collector` | POST | **未开启** | `/user/fast_update_log_collector/` |

### 日志提取

共 7 个，原入口未开启 3 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_log_extract_topology` | POST | 已开启 | `/user/list_log_extract_topology/` |
| `search_log_extract_hosts` | POST | 已开启 | `/user/search_log_extract_hosts/` |
| `list_log_extract_allowed_paths` | POST | 已开启 | `/user/list_log_extract_allowed_paths/` |
| `search_log_extract_files` | POST | **未开启** | `/user/search_log_extract_files/` |
| `create_log_extract_task` | POST | **未开启** | `/user/create_log_extract_task/` |
| `get_log_extract_task` | GET | 已开启 | `/user/get_log_extract_task/` |
| `get_log_extract_download_url` | POST | **未开启** | `/user/get_log_extract_download_url/` |

### 预计算规则

共 7 个，原入口未开启 7 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `preview_recording_rule` | POST | **未开启** | `/user/preview_recording_rule/` |
| `create_recording_rule` | POST | **未开启** | `/user/create_recording_rule/` |
| `update_recording_rule` | POST | **未开启** | `/user/update_recording_rule/` |
| `delete_recording_rule` | POST | **未开启** | `/user/delete_recording_rule/` |
| `get_recording_rule` | POST | **未开启** | `/user/get_recording_rule/` |
| `apply_recording_rule` | POST | **未开启** | `/user/apply_recording_rule/` |
| `list_recording_rules` | POST | **未开启** | `/user/list_recording_rules/` |

### 统一工具目录

共 5 个，原入口未开启 1 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `lookup_tool` | POST | 已开启 | `/user/lookup_tool/` |
| `lookup_tool_schema` | POST | 已开启 | `/user/lookup_tool_schema/` |
| `execute_tool` | POST | **未开启** | `/user/execute_tool/` |
| `lookup_metadata` | POST | 已开启 | `/user/lookup_metadata/` |
| `lookup_permissions` | POST | 已开启 | `/user/lookup_permissions/` |

### 运营数据（排除）

共 3 个，原入口未开启 3 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `list_operation_metrics` | POST | **未开启** | 排除 |
| `get_operation_metric` | POST | **未开启** | 排除 |
| `get_operation_overview` | POST | **未开启** | 排除 |

### 运维诊断（排除）

共 4 个，原入口未开启 4 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `query_datalink_metadata` | GET | **未开启** | 排除 |
| `query_data_link_info` | GET | **未开启** | 排除 |
| `diagnose_metadata_datalink` | GET | **未开启** | 排除 |
| `get_data_link_metadata` | GET | **未开启** | 排除 |

### OpenClaw 专用入口（排除）

共 3 个，原入口未开启 3 个。

| 原资源名称 | 方法 | 原入口个人令牌 | 纯用户态入口 |
| --- | --- | --- | --- |
| `search_openclaw_spans` | POST | **未开启** | 排除 |
| `get_openclaw_trace_detail` | POST | **未开启** | 排除 |
| `search_openclaw_logs` | POST | **未开启** | 排除 |

## 维护与发布验收

`kernel_api/user_api.py` 显式维护公开来源及需确认的操作，`scripts/merge_resources.py` 从原 OpenAPI
生成公共资源。共享 Schema 位于 `kernel_api/tool_schema.py`。新增来源须评审，并通过公共目录与业务目录一致性测试；
不得按文件名或请求方法自动开放内部能力。

发布资源版本为 `0.0.9`，由现有 `python manage.py sync_apigw` 流程同步；真实执行会更新网关资源并发布版本。
本次代码与本地测试不代表任一环境已经发布。目标环境发布后，应验证：

1. 网关出现“纯用户态接口”分组，101 个 `user_*` 资源公开可见，认证为仅用户认证且支持个人令牌。
2. 三类内部接口没有新增 `/user/...` 资源；已有 MCP Server 的工具清单与访问地址保持兼容。
3. 使用个人令牌、不携带 MCP 来源头，验证查询成功、缺权拒绝、跨租户拒绝和参数错误。
4. 在授权测试资源上验证写入确认及执行，检查业务结果；不得以目录可见替代真实调用验收。
