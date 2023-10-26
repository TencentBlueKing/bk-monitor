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
from django.core.management.base import BaseCommand

from alarm_backends.core.cache.key import STRATEGY_CHECKPOINT_KEY
from bkmonitor.documents import AlertDocument, ActionInstanceDocument


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument("-t", type=int, default=120, help="time window to check (in seconds)")

    def handle(self, *args, **options):
        time_window = options.get("t")
        keys = list(
            STRATEGY_CHECKPOINT_KEY.client.scan_iter(STRATEGY_CHECKPOINT_KEY.get_key(strategy_group_key="*"), count=100)
        )

        pipeline = STRATEGY_CHECKPOINT_KEY.client.pipeline(transaction=False)
        for key in keys:
            pipeline.ttl(key)

        if keys:
            results = pipeline.execute()
        else:
            results = []

        total_count = 0
        valid_count = 0

        for ttl in results:
            if not ttl:
                continue
            total_count += 1
            if (ttl + time_window - STRATEGY_CHECKPOINT_KEY.ttl) > 0:
                valid_count += 1

        update_rate = valid_count / total_count * 100 if total_count else 100
        if update_rate > 99:
            print(f"[Passed] checkpoint update rate: {update_rate}% ({valid_count}/{total_count})")
        else:
            print(
                f"[Failed] checkpoint update rate: {update_rate}% ({valid_count}/{total_count}), "
                f"which is not greater than 99%"
            )

        alert_search = AlertDocument.search().execute()
        if alert_search.hits.total.value > 0:
            print(f"[Passed] alert document has created, count: {alert_search.hits.total.value}")
        else:
            print(f"[Failed] alert document not created")

        action_search = ActionInstanceDocument.search().execute()
        if alert_search.hits.total.value > 0:
            print(f"[Passed] action document has created, count: {action_search.hits.total.value}")
        else:
            print(f"[Failed] action document not created")
