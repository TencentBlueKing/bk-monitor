"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

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

# MCP Server 名称格式: {apigw_name}-{stage}-{suffix}
# apigw_name 可含连字符（如 bk-monitor / bkmonitorv3），stage 取值见 _MCP_SERVER_STAGES
# 约定全部使用小写、连字符分隔；正则不开启 IGNORECASE 以避免与下方字典查找的大小写不一致。
# 前缀使用非贪婪匹配 + 限定字符集，避免后缀中再次出现 stage 关键字时被贪婪匹配吞掉。
_MCP_SERVER_STAGES = ("prod", "stage", "stag")
_MCP_SERVER_NAME_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*?-(?:" + "|".join(_MCP_SERVER_STAGES) + r")-(?P<suffix>[a-z0-9][a-z0-9-]*)$"
)

# MCP Server 后缀到 Permission Action 的映射（与网关前缀、环境无关）
# Key: HTTP_X_BKAPI_MCP_SERVER_NAME 中 {stage} 之后的后缀部分
# Value: 对应的权限动作 ID
MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION = {
    # Streamable HTTP 协议 MCP Server
    "dashboard-edit": "using_dashboard_mcp",
    "dashboard-query": "using_dashboard_mcp",
    "log-query": "using_log_mcp",
    "log-extract": "using_log_mcp",
    "tracing": "using_apm_mcp",
    "profiling": "using_apm_mcp",
    "profiling-query": "using_apm_mcp",
    "metadata-query": "using_metadata_mcp",
    "metrics-query": "using_metrics_mcp",
    "event-query": "using_log_mcp",
    "alarm": "using_alarm_mcp",
    "alarm-handling": "using_alarm_handling_mcp",
    "relation-query": "using_metrics_mcp",
    "operation": "using_operation_mcp",
    # SSE 协议 MCP Server
    "event": "using_log_mcp",
    "log": "using_log_mcp",
    "dashboard-operate": "using_dashboard_mcp",
    "apm-trace": "using_apm_mcp",
    "dashboard-ascode": "using_dashboard_mcp",
    "metadata": "using_metadata_mcp",
    "alerts": "using_alarm_mcp",
    "metrics": "using_metrics_mcp",
}


def extract_mcp_server_suffix(mcp_server_name: str) -> str:
    """从 MCP Server 全名中解析后缀，无法解析时返回空字符串。

    解析前会将输入统一转为小写，以便与下方的后缀映射字典保持一致。
    """
    if not mcp_server_name:
        return ""
    match = _MCP_SERVER_NAME_PATTERN.match(mcp_server_name.lower())
    if not match:
        return ""
    return match.group("suffix")


def get_mcp_permission_action_by_server_name(mcp_server_name: str) -> str:
    """根据 HTTP_X_BKAPI_MCP_SERVER_NAME 解析 IAM 权限动作 ID。"""
    suffix = extract_mcp_server_suffix(mcp_server_name)
    if not suffix:
        return ""
    return MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION.get(suffix, "")
