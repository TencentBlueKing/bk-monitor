"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum


class DataLinkKind(Enum):
    """数据链路资源类型"""

    DATAID = "DataId"
    RESULTTABLE = "ResultTable"
    VMSTORAGEBINDING = "VmStorageBinding"
    DATABUS = "Databus"
    CONDITIONALSINK = "ConditionalSink"
    SINK = "Sink"
    VMSTORAGE = "VmStorage"
    ELASTICSEARCH = "ElasticSearch"
    DORIS = "Doris"

    choices_labels = (
        (DATAID, "dataids"),
        (RESULTTABLE, "resulttables"),
        (VMSTORAGEBINDING, "vmstoragebindings"),
        (DATABUS, "databuses"),
        (CONDITIONALSINK, "conditionalsinks"),
        (SINK, "sinks"),
        (VMSTORAGE, "vmstorages"),
        (ELASTICSEARCH, "elasticsearchs"),
        (DORIS, "dorises"),
    )

    @classmethod
    def get_choice_value(cls, key: str) -> str:
        for item in DataLinkKind.choices_labels.value:
            if key == item[0]:
                return item[1]

        return ""


class DataLinkResourceStatus(Enum):
    """数据链路资源状态
    INITIALIZING: The resource is being initialized 自定义状态
    CREATING: The resource is being created 自定义状态
    Pending: The resource has been created but has not been scheduled yet 计算平台状态
    Reconciling: The resource is in a reconciliation loop   计算平台状态
    Terminating: The resource is terminating    计算平台状态
    Failed: The resource has failed 计算平台状态
    Ok: The resource has been scheduled and is ready for use 计算平台状态
    """

    # INITIALIZING -> CREATING -> PENDING -> OK
    INITIALIZING = "Initializing"
    CREATING = "Creating"
    PENDING = "Pending"
    FAILED = "Failed"
    OK = "Ok"
    TERMINATING = "Terminating"

    RECONCILING = "Reconciling"

    choices_labels = (
        (INITIALIZING, 0),
        (CREATING, 2),
        (PENDING, 3),
        (FAILED, 4),
        (OK, 1),
        (RECONCILING, 5),
        (TERMINATING, 6),
    )

    @classmethod
    def get_choice_value(cls, key: str) -> int:
        for item in DataLinkResourceStatus.choices_labels.value:
            if key == item[0]:
                return item[1]

        return -1


# 基础采集链路用途
BASEREPORT_USAGES = [
    "cpu_summary",
    "cpu_detail",
    "disk",
    "env",
    "inode",
    "io",
    "load",
    "mem",
    "net",
    "netstat",
    "swap",
]

BASEREPORT_DATABUS_FORMAT = "bkmonitor_basereport_v1"


# 基础采集数据链路来源 -- 主机系统、DBM、DEVX、Perforce
BASEREPORT_SOURCE_SYSTEM = "sys"
BASEREPORT_SOURCE_DBM = "dbm"
BASEREPORT_SOURCE_DEVX = "devx"
BASEREPORT_SOURCE_PERFORCE = "perforce"

# 默认转换器及对应的处理格式
DEFAULT_METRIC_TRANSFORMER_KIND = "PreDefinedLogic"
DEFAULT_METRIC_TRANSFORMER = "log_to_metric"
DEFAULT_METRIC_TRANSFORMER_FORMAT = "bkmonitor_standard_v2"

# 针对数据源名称需要替换的正则
MATCH_DATA_NAME_PATTERN = r"[\u4e00-\u9fa5\.\!\:\*\+\?\^\$\{\}\[\]\(\)\|\\]"


BKBASE_NAMESPACE_BK_MONITOR = "bkmonitor"
BKBASE_NAMESPACE_BK_LOG = "bklog"
BKBASE_NAMESPACE_BK_APM = "bkapm"
