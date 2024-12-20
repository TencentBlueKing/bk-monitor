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
import time
from typing import List

from kafka.consumer.fetcher import ConsumerRecord

from alarm_backends.core.alert import Event
from alarm_backends.service.alert.builder.processor import AlertBuilder
from alarm_backends.service.scheduler.app import app
from core.prometheus import metrics


@app.task(ignore_result=True, queue="celery_alert_builder")
def run_alert_builder(topic_data_id, bootstrap_server, events: List[ConsumerRecord]):
    builder = AlertBuilder()
    exc = None
    builder.logger.info("[alert.builder] start, total(%s) events", len(events))
    valid_events = []
    start = time.time()
    try:
        for event in events:
            try:
                topic = event.topic
                data_id = topic_data_id.get(f"{bootstrap_server}|{topic}")
                value = json.loads(event.value)
                value.update({"data_id": data_id, "topic": topic})
                valid_events.append(Event(value))
            except Exception as e:
                builder.logger.warning("[alert.builder] ignore event: %s, reason: %s", event, e)
                continue
        builder.process(valid_events)
    except Exception as e:
        builder.logger.exception("[alert.builder ERROR] detail: %s", e)
        exc = e
    builder.logger.info("[alert.builder] end, event processed(%s/%s)", len(valid_events), len(events))
    if events:
        metrics.ALERT_PROCESS_TIME.observe((time.time() - start) / len(events))
    # 记录拉取并处理的事件数量
    metrics.ALERT_PROCESS_PULL_EVENT_COUNT.labels(status=metrics.StatusEnum.from_exc(exc), exception=exc).inc(
        len(events)
    )
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_alert_builder")
def dedupe_events_to_alerts(events: List[Event]):
    builder = AlertBuilder()
    try:
        builder.dedupe_events_to_alerts(events)
    except Exception as e:
        builder.logger.exception("[alert.builder dedupe_events_to_alerts] failed detail: %s", e)

    metrics.report_all()
