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

from django.utils.translation import ugettext_lazy as _lazy

# 标准事件字段
EVENT_NORMAL_FIELDS = [
    {
        "field": "alert_name",
        "display_name": _lazy("告警名称"),
        "description": _lazy("告警名称通过匹配规则生成，是事件去重的重要依据"),
        "field_type": "string",
    },
    {
        "field": "event_id",
        "display_name": _lazy("事件ID"),
        "description": _lazy("事件的唯一标识符，用于识别重复事件"),
        "field_type": "string",
    },
    {
        "field": "description",
        "display_name": _lazy("描述"),
        "description": _lazy("事件的详细描述及主体内容"),
        "field_type": "string",
    },
    {"field": "metric", "display_name": _lazy("指标项"), "description": _lazy("事件对应的指标项"), "field_type": "string"},
    {
        "field": "category",
        "display_name": _lazy("分类"),
        "description": _lazy('事件所属的数据分层，如 "application", "os", "others"'),
        "field_type": "string",
    },
    {"field": "target_type", "display_name": _lazy("目标类型"), "description": _lazy("产生事件的目标类型"), "field_type": "string"},
    {"field": "target", "display_name": _lazy("目标"), "description": _lazy("产生事件的目标"), "field_type": "string"},
    {
        "field": "severity",
        "display_name": _lazy("级别"),
        "description": _lazy("事件的严重程度，1:致命; 2:预警; 3:提醒"),
        "field_type": "int",
    },
    {
        "field": "bk_biz_id",
        "display_name": _lazy("业务ID"),
        "description": _lazy("事件所属的业务ID，不提供则根据 target 自动解析"),
        "field_type": "int",
    },
    {
        "field": "tags",
        "display_name": _lazy("标签"),
        "description": _lazy("事件的额外属性，K-V 键值对，不支持嵌套结构"),
        "field_type": "object",
    },
    {
        "field": "dedupe_keys",
        "display_name": _lazy("维度字段"),
        "description": _lazy("事件去重的维度字段"),
        "field_type": "object",
    },
    {
        "field": "assignee",
        "display_name": _lazy("受理人"),
        "description": _lazy("事件受理人，可作为动作的执行者"),
        "field_type": "string",
    },
    {
        "field": "time",
        "display_name": _lazy("事件时间"),
        "description": _lazy("事件产生的时间，不提供则默认使用采集时间"),
        "field_type": "timestamp",
    },
    {
        "field": "anomaly_time",
        "display_name": _lazy("异常时间"),
        "description": _lazy("事件实际发生异常的时间，不提供则默认使用事件时间"),
        "field_type": "timestamp",
    },
    {
        "field": "status",
        "display_name": _lazy("状态"),
        "description": _lazy('事件状态，用于控制告警状态流转。不提供则默认为 "ABNORMAL"'),
        "field_type": "string",
    },
]


class CollectType:
    """
    推送采集类型
    """

    BK_COLLECTOR = "bk_collector"
    BK_INGESTOR = "bk_ingestor"
