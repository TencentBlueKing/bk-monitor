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

# 接入计算平台 kafka 使用的 topic 规则

BCS_K8S_TOPIC = "ieod_bcs_prom_c_{bcs_cluster_id_num}100147"
BCS_CUSTOM_TOPIC = "ieod_bcs_custom_{bcs_cluster_id_num}100147"
USER_CUSTOM_TOPIC = "ieod_custom_metric_{bk_data_id}100147"

# ns 时间戳结果表列表
BKDATA_NS_TIMESTAMP_DATA_ID_LIST = [1100006, 1100015, 1100007, 1100016]

# 通过 vm 查询的空间信息
QUERY_VM_SPACE_UID_LIST_KEY = "bkmonitorv3:vm-query:space_uid"
QUERY_VM_SPACE_UID_CHANNEL_KEY = "bkmonitorv3:vm-query"


class TimestampLen(Enum):
    """时间戳长度"""

    SECOND_LEN = 10
    MILLISECOND_LEN = 13
    NANOSECOND_LEN = 19

    _choices_labels = (
        (SECOND_LEN, "Unix Time Stamp(seconds)"),
        (MILLISECOND_LEN, "Unix Time Stamp(milliseconds)"),
        (NANOSECOND_LEN, "Unix Time Stamp(nanosecond)"),
    )

    @classmethod
    def get_choice_value(cls, key: int) -> str:
        for item in TimestampLen._choices_labels.value:
            if key == item[0]:
                return item[1]

        return ""
