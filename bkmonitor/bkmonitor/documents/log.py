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

from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import Q, field

from bkmonitor.documents.base import BaseDocument, Date


@registry.register_document
class AlertLog(BaseDocument):
    class Index:
        name = "bkfta_log_alert"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    class OpType:
        # 告警产生
        CREATE = "CREATE"
        # 告警收敛
        CONVERGE = "CONVERGE"
        # 告警恢复
        RECOVER = "RECOVER"
        # 告警关闭
        CLOSE = "CLOSE"
        # 告警恢复
        RECOVERING = "RECOVERING"
        # 延迟恢复
        DELAY_RECOVER = "DELAY_RECOVER"
        # 中断恢复
        ABORT_RECOVER = "ABORT_RECOVER"
        # 系统恢复
        SYSTEM_RECOVER = "SYSTEM_RECOVER"
        # 系统关闭
        SYSTEM_CLOSE = "SYSTEM_CLOSE"
        # 告警确认
        ACK = "ACK"
        # 严重级别上升
        SEVERITY_UP = "SEVERITY_UP"
        # 严重级别上升
        SEVERITY_CHANGE = "SEVERITY_CHANGE"
        # 低级别关联事件丢弃
        EVENT_DROP = "EVENT_DROP"
        # 套餐处理
        ACTION = "ACTION"
        # 通知降噪
        NOISE_REDUCE = "NOISE_REDUCE"
        # 告警QOS
        ACTION_QOS = "ACTION_QOS"

        # 告警QOS
        ALERT_QOS = "ALERT_QOS"

    # 流水记录必须字段
    alert_id = field.Keyword()
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    op_type = field.Keyword()

    operator = field.Keyword()
    time = Date(format=BaseDocument.DATE_FORMAT)
    event_id = field.Keyword()
    description = field.Text()

    status = field.Keyword()
    severity = field.Integer()

    next_status = field.Keyword()
    next_status_time = Date(format=BaseDocument.DATE_FORMAT)

    def get_index_time(self):
        return self.create_time

    @classmethod
    def get_ack_logs(cls, alert_ids):
        ack_logs = (
            cls.search(all_indices=True)
            .filter(Q("terms", alert_id=list(alert_ids)) & Q("term", op_type=AlertLog.OpType.ACK))
            .sort("-create_time", "-_doc")
            .execute()
        )
        return ack_logs
