"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum

# 默认的间隔, 默认为60秒
DEFAULT_EVALUATION_INTERVAL = "60s"
DEFAULT_RULE_TYPE = "prometheus"

# V4 预计算相关常量
RECORD_RULE_V4_BKBASE_NAMESPACE = "bkmonitor"
RECORD_RULE_V4_BKMONITOR_NAMESPACE = "bkmonitor"
RECORD_RULE_V4_DEFAULT_TENANT = "default"
RECORD_RULE_V4_DEFAULT_REFRESH_INTERVAL = 3600
RECORD_RULE_V4_DELETED_RETENTION_DAYS = 180
RECORD_RULE_V4_INTERVAL_CHOICES = ("1min", "2min", "5min", "10min")


class RecordRuleStatus(Enum):
    """预计算状态"""

    CREATED = "created"
    RUNNING = "running"
    DELETED = "deleted"


class RecordRuleV4InputType(Enum):
    """V4 预计算输入类型"""

    QUERY_TS = "query_ts"
    PROMQL = "promql"


class RecordRuleV4Status(Enum):
    """V4 预计算聚合状态"""

    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    OUTDATED = "outdated"
    DELETING = "deleting"
    FAILED = "failed"
    DELETED = "deleted"


class RecordRuleV4DesiredStatus(Enum):
    """V4 预计算期望状态"""

    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class RecordRuleV4FlowActionType(Enum):
    """V4 预计算 Flow 执行动作类型。

    动作本身不独立成表，只作为 event detail 中的结构化枚举。
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    START = "start"
    STOP = "stop"


class RecordRuleV4FlowStatus(Enum):
    """V4 Flow 实际观测状态"""

    OK = "ok"
    ABNORMAL = "abnormal"
    NOT_FOUND = "not_found"


class BkDataFlowStatus(Enum):
    """流程状态"""

    NO_ACCESS = "no-access"
    NO_CREATE = "no-create"
    NO_START = "no-start"

    ACCESSING = "accessing"
    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"

    ACCESS_FAILED = "access-failed"
    CREATE_FAILED = "create-failed"
    START_FAILED = "start-failed"
    STOP_FAILED = "stop-failed"
