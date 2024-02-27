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
from typing import List

import arrow

from alarm_backends.core.storage.kafka import KafkaQueue
from core.drf_resource import api


def oom_event_generator(ip, cloud_id):
    local_time = arrow.now().format("YYYY-MM-DD HH:mm:ss")
    utc_time = arrow.utcnow().format("YYYY-MM-DD HH:mm:ss")

    return {
        "isdst": 0,
        "server": "127.0.0.1",
        "time": local_time,
        "timezone": 8,
        "utctime": local_time,
        "utctime2": utc_time,
        "value": [
            {
                "event_desc": "",
                "event_raw_id": 11,
                "event_source_system": "",
                "event_time": local_time,
                "event_title": "",
                "event_type": "gse_basic_alarm_type",
                "extra": {
                    "bizid": 0,
                    "cloudid": cloud_id,
                    "host": ip,
                    "type": 9,
                    "total": 3,
                    "process": "oom/java/consul",
                    "message": "total-vm:44687536kB, anon-rss:32520504kB, file-rss:0kB, shmem-rss:0kB",
                    "oom_memcg": "oom_cgroup_path",
                    "task_memcg": "oom_cgroup_task",
                    "task": "process_name",
                    "constraint": "CONSTRAINT_MEMCG",
                },
            }
        ],
    }


def push_to_kafka(values: List[str], bk_data_id):
    kafka_queue = KafkaQueue.get_alert_kafka_queue()
    topic_info = api.metadata.get_data_id(bk_data_id=bk_data_id, with_rt_info=False)
    topic = topic_info["mq_config"]["storage_config"]["topic"]
    kafka_queue.put(values, topic)
    kafka_queue.close()
