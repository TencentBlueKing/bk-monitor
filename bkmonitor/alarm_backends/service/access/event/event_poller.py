"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from django.conf import settings

from alarm_backends.core.storage.kafka import KafkaQueue
from bkmonitor.utils.common_utils import safe_int
from core.drf_resource import api


class EventPoller:
    def start(self):
        pass

    def handle_event_v2(self):
        # 直接在这里拉事件，并推送给worker处理
        # 新增通过环境变量控制 dataid 禁用入口
        DISABLE_EVENT_DATAID = os.getenv("DISABLE_EVENT_DATAID", "0")
        disabled_data_ids = {safe_int(i) for i in DISABLE_EVENT_DATAID.split(",")}
        data_ids = {
            settings.GSE_BASE_ALARM_DATAID,
            settings.GSE_CUSTOM_EVENT_DATAID,
            settings.GSE_PROCESS_REPORT_DATAID,
        } - disabled_data_ids
        # target = []
        kafka_queue = KafkaQueue.get_common_kafka_queue()
        for data_id in data_ids:
            topic_info = api.metadata.get_data_id(bk_data_id=data_id, with_rt_info=False)
            topic = topic_info["mq_config"]["storage_config"]["topic"]
            kafka_queue.set_topic(topic)
            consumer = kafka_queue.get_consumer()
            partitions = consumer.partitions_for_topic(topic) or {0}
            for partition in partitions:
                consumer.assign([partition])
