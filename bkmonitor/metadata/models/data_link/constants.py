# -*- coding: utf-8 -*-
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

    _choices_labels = (
        (DATAID, "dataids"),
        (RESULTTABLE, "resulttables"),
        (VMSTORAGEBINDING, "vmstoragebindings"),
        (DATABUS, "databuses"),
        (CONDITIONALSINK, "conditionalsinks"),
    )

    @classmethod
    def get_choice_value(cls, key: str) -> str:
        for item in DataLinkKind._choices_labels.value:
            if key == item[0]:
                return item[1]

        return ""


class DataLinkResourceStatus(Enum):
    """数据链路资源状态

    Pending: The resource has been created but has not been scheduled yet
    Reconciling: The resource is in a reconciliation loop
    Terminating: The resource is terminating
    Failed: The resource has failed
    Ok: The resource has been schedualed and is ready for use
    """

    PENDING = "Pending"
    RECONCILING = "Reconciling"
    TERMINATING = "Terminating"
    FAILED = "Failed"
    OK = "Ok"


# 默认转换器及对应的处理格式
DEFAULT_METRIC_TRANSFORMER_KIND = "PreDefinedLogic"
DEFAULT_METRIC_TRANSFORMER = "log_to_metric"
DEFAULT_METRIC_TRANSFORMER_FORMAT = "bkmonitor_standard_v2"

# 针对数据源名称需要替换的正则
MATCH_DATA_NAME_PATTERN = r"[\u4e00-\u9fa5\.\!\:\*\+\?\^\$\{\}\[\]\(\)\|\\]"
