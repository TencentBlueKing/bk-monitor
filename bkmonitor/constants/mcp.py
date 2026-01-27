"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# MCP请求状态
MCP_REQUESTS_STATUS_SUCCESS = "success"
MCP_REQUESTS_STATUS_FAILED = "failed"

# MCP异常类型
MCP_REQUESTS_EXCEPTION_TYPE_NONE = "none"

# MCP数据有效性标识
MCP_REQUESTS_HAS_DATA_TRUE = "true"
MCP_REQUESTS_HAS_DATA_FALSE = "false"

# MCP未知值标识
MCP_REQUESTS_UNKNOWN = "unknown"

# MCP Server Name 到 Permission Action 的映射关系
# Key: HTTP_X_BKAPI_MCP_SERVER_NAME 的值
# Value: 对应的权限动作ID
MCP_SERVER_NAME_TO_PERMISSION_ACTION = {
    # Streamable HTTP协议 MCP Server
    "bkmonitorv3-prod-dashboard-edit": "using_dashboard_mcp",
    "bkmonitorv3-prod-dashboard-query": "using_dashboard_mcp",
    "bkmonitorv3-prod-log-query": "using_log_mcp",
    "bkmonitorv3-prod-tracing": "using_apm_mcp",
    "bkmonitorv3-prod-metadata-query": "using_metadata_mcp",
    "bkmonitorv3-prod-metrics-query": "using_metrics_mcp",
    "bkmonitorv3-prod-event-query": "using_log_mcp",
    "bkmonitorv3-prod-alarm": "using_alarm_mcp",
    "bkmonitorv3-prod-relation-query": "using_metrics_mcp",
    # SSE协议 MCP Server
    "bkmonitorv3-prod-event": "using_log_mcp",
    "bkmonitorv3-prod-log": "using_log_mcp",
    "bkmonitorv3-prod-dashboard-operate": "using_dashboard_mcp",
    "bkmonitorv3-prod-apm-trace": "using_apm_mcp",
    "bkmonitorv3-prod-dashboard-ascode": "using_dashboard_mcp",
    "bkmonitorv3-prod-metadata": "using_metadata_mcp",
    "bkmonitorv3-prod-alerts": "using_alarm_mcp",
    "bkmonitorv3-prod-metrics": "using_metrics_mcp",
}
