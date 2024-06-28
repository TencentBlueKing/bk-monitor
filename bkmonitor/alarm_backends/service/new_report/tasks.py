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
import datetime
import logging

import arrow

from alarm_backends.core.i18n import i18n
from alarm_backends.service.new_report.factory import ReportFactory
from alarm_backends.service.scheduler.app import app
from bkmonitor.models import Report, ReportChannel
from bkmonitor.report.utils import (
    create_send_record,
    get_last_send_record_map,
    is_run_time,
    parse_frequency,
)
from bkmonitor.utils.time_tools import localtime

logger = logging.getLogger("bkmonitor.cron_report")


@app.task(ignore_result=True, queue="celery_report_cron")
def send_report(report, channels=None):
    """
    发送邮件订阅
    """
    logger.info(f"[send_report] start to send report({report.id}), current time: {arrow.now()}")
    ReportFactory.get_handler(report).run(channels)


@app.task(ignore_result=True, queue="celery_report_cron")
def new_report_detect():
    """
    检测邮件订阅
    """
    reports = Report.objects.filter(is_enabled=True)
    last_send_record_map = get_last_send_record_map(reports)
    for report in reports:
        # 判断订阅是否有效
        if Report.is_invalid(report.end_time, report.frequency):
            logger.info(f"[new_report_detect] report({report.id}) is invalid.")
            continue
        # 判断订阅是否到执行时间
        i18n.set_biz(report.bk_biz_id)
        frequency = report.frequency
        last_send_time = (
            localtime(last_send_record_map[report.id]["send_time"])
            if last_send_record_map[report.id]["send_time"]
            else None
        )
        if (
            frequency["type"] != 5
            and last_send_time
            and last_send_time.strftime("%Y-%m-%d") >= datetime.datetime.today().strftime("%Y-%m-%d")
        ):
            logger.info(f"[new_report_detect] report({report.id}) is not 5 type and already send today.")
            continue
        run_time_strings = parse_frequency(frequency, last_send_time)
        logger.info(
            f"[new_report_detect] report({report.id}) last_send_time: {last_send_time},"
            f" run_time_strings:{run_time_strings}"
        )
        if not is_run_time(frequency, run_time_strings):
            logger.info(f"[new_report_detect] report({report.id}) is not at sending time.")
            continue
        # 根据渠道分别发送，记录最新发送轮次
        send_round = report.send_round + 1 if report.send_round else 1
        report.send_round = send_round
        report.save(update_fields=["send_round"])
        channels = ReportChannel.objects.filter(report_id=report.id)
        create_send_record(channels, send_round)
        # 异步执行订阅发送任务
        send_report.delay(report)
