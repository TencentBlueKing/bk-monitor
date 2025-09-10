# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time

from django.core.management.base import BaseCommand
from elasticsearch_dsl import Q

from alarm_backends.constants import CONST_ONE_DAY, NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache.key import ALERT_BUILD_QOS_COUNTER
from bkmonitor.documents import AlertDocument
from bkmonitor.utils.common_utils import count_md5
from constants.alert import EventStatus


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--strategy", help="clear alert qos keys  for the input strategy")
        parser.add_argument("--severity", help="clear alert qos keys for the input severity")

    def handle(self, *args, **options):
        strategy = options.get("strategy") or "all"
        severity = options.get("severity") or "all"
        print("clear alert qos key for strategy({}), severity({})".format(strategy, severity))
        current_time = int(time.time())
        end_time = current_time
        start_time = current_time - CONST_ONE_DAY
        search = (
            AlertDocument.search(start_time=start_time, end_time=end_time)
            .filter(Q("term", status=EventStatus.ABNORMAL) & Q('term', is_blocked=True))

        )
        if strategy != "all":
            search = search.filter("term", strategy_id=strategy)
        if severity != "all":
            search = search.filter("term", severity=severity)
        search = search.source(fields=["id", "strategy_id", "status", "severity", "alert_name",
                                       "event.bk_biz_id", "event.tags"])
        alerts = [hit.to_dict() for hit in search.params(size=5000).scan() if getattr(hit, "id", None)]
        alert_qos_keys = []
        redis_client = ALERT_BUILD_QOS_COUNTER.client
        for alert in alerts:
            signal = alert["status"]
            for tag in alert["event"]["tags"]:
                if tag["key"] == NO_DATA_TAG_DIMENSION:
                    signal = "no_data"
                    break
            strategy_id = alert.get("strategy_id") or 0
            qos_dimension = dict(strategy_id=strategy_id, signal=signal, severity=alert["severity"], alert_md5="")
            if not strategy_id:
                qos_dimension["alert_md5"] = count_md5(
                    dict(
                        bk_biz_id=alert["event"].get("bk_biz_id", 0),
                        alert_name=alert["alert_name"],
                        signal=alert["status"],
                        severity=alert["severity"],
                    )
                )
            alert_qos_keys.append(ALERT_BUILD_QOS_COUNTER.get_key(**qos_dimension))
        invalid_keys_count = 0
        for qos_key in set(alert_qos_keys):
            qos_ttl = redis_client.ttl(qos_key)
            if qos_ttl is None or qos_ttl < 0:
                # 如果没有设置过期时间，直接删除，重新处理
                redis_client.delete(qos_key)
                invalid_keys_count += 1

        print("clear alert qos key for strategy({}), severity({}) finished, "
              "total invalid keys count({})".format(strategy, severity, invalid_keys_count))
