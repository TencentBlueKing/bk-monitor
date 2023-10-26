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
from django.utils.functional import cached_property
from monitor_web.statistics.v2.base import BaseCollector

from bkmonitor.models import ReportContents, ReportItems, ReportStatus
from core.statistics.metric import Metric, register


class MailReportCollector(BaseCollector):
    """
    邮件订阅
    """

    @cached_property
    def all_items(self):
        return ReportItems.objects.all().values("id", "is_enabled", "receivers", "mail_title")

    @cached_property
    def report_status_count(self):
        return ReportStatus.objects.all().values("report_item", "mail_title", "is_success")

    @register(labelnames=("graph_type", "status"))
    def mail_report_item_count(self, metric: Metric):
        """
        邮件订阅配置数
        """
        contents = ReportContents.objects.all().values("report_item", "graphs")
        report_item_graphs_mappings = {}
        for content in contents:
            report_item_graphs_mappings[content["report_item"]] = content["graphs"]

        for item in self.all_items:
            metric.labels(
                graph_type="dashboard" if report_item_graphs_mappings[item["id"]][0].endswith("*") else "panel",
                status="enabled" if item["is_enabled"] else "disabled",
            ).inc()

    @register(labelnames=("report_item_id", "report_mail_title"))
    def mail_report_receiver_count(self, metric: Metric):
        """
        邮件订阅接收人数
        """
        for item in self.all_items:
            for user in item["receivers"]:
                if user["type"] != "user" or not user["is_enabled"]:
                    continue
                metric.labels(report_item_id=item["id"], report_mail_title=item["mail_title"]).inc()

    @register(labelnames=("report_item_id", "report_mail_title", "is_success"))
    def mail_report_send_count(self, metric: Metric):
        """
        邮件订阅发送数量
        """
        for item in self.report_status_count:
            metric.labels(
                report_item_id=item["report_item"], report_mail_title=item["mail_title"], is_success=item["is_success"]
            ).inc()
