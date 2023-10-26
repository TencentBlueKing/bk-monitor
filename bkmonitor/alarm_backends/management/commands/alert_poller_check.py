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
import json

from django.core.management.base import BaseCommand

from alarm_backends.core.cache.key import ALERT_HOST_DATA_ID_KEY


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--host", help="list poll tasks for this host, default list all tasks")

    def handle(self, *args, **options):
        target_host = options.get("host") or "all"
        print("list poll tasks for host(%s)" % target_host)
        ip_topics = ALERT_HOST_DATA_ID_KEY.client.hgetall(ALERT_HOST_DATA_ID_KEY.get_key())
        for ip, topics in ip_topics.items():
            data_topic_info = []
            topics = json.loads(topics)
            for topic in topics:
                topic_info = "---------------" + "|".join(map(str, topic.values()))
                data_topic_info.append(topic_info)
            info = '\n'.join(data_topic_info)
            if target_host == "all":
                print(f"host({ip}):\n{info}")
            elif target_host == ip:
                print(f"host({ip}):\n{info}")
                break
        print("poll tasks check done!!")
