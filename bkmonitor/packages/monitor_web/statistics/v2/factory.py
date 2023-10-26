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
import arrow
from monitor_web.statistics.v2.action_config import ActionConfigCollector
from monitor_web.statistics.v2.alert_action import AlertActionCollector
from monitor_web.statistics.v2.apm import APMCollector
from monitor_web.statistics.v2.bkcollector import BkCollectorCollector
from monitor_web.statistics.v2.business import BusinessCollector
from monitor_web.statistics.v2.collect_config import CollectConfigCollector
from monitor_web.statistics.v2.collect_plugin import CollectPluginCollector
from monitor_web.statistics.v2.custom_report import CustomReportCollector
from monitor_web.statistics.v2.event_plugin import EventPluginCollector
from monitor_web.statistics.v2.grafana import GrafanaCollector
from monitor_web.statistics.v2.host import HostCollector
from monitor_web.statistics.v2.k8s import K8SCollector
from monitor_web.statistics.v2.mail_report import MailReportCollector
from monitor_web.statistics.v2.monitor_metric import MonitorMetricCollector
from monitor_web.statistics.v2.observation_scene import ObservationSceneCollector
from monitor_web.statistics.v2.query import QueryCollector
from monitor_web.statistics.v2.shield import ShieldCollector
from monitor_web.statistics.v2.site import SiteCollector
from monitor_web.statistics.v2.statistics import StatisticCollector
from monitor_web.statistics.v2.storage import StorageCollector
from monitor_web.statistics.v2.strategy import StrategyCollector
from monitor_web.statistics.v2.uptimecheck import UptimeCheckCollector
from monitor_web.statistics.v2.user_group import UserGroupCollector

from bkmonitor.models import StatisticsMetric
from core.statistics.metric import Metric

INSTALLED_COLLECTORS = [
    UserGroupCollector,
    AlertActionCollector,
    MonitorMetricCollector,
    MailReportCollector,
    ObservationSceneCollector,
    EventPluginCollector,
    GrafanaCollector,
    ActionConfigCollector,
    BusinessCollector,
    ShieldCollector,
    StrategyCollector,
    UptimeCheckCollector,
    HostCollector,
    CollectConfigCollector,
    CollectPluginCollector,
    CustomReportCollector,
    QueryCollector,
    K8SCollector,
    BkCollectorCollector,
    SiteCollector,
    APMCollector,
    StorageCollector,
    StatisticCollector,
]


class CollectorFactory:
    @classmethod
    def export_json(cls):
        """
        输出指标JSON形式
        """
        metric_data = []
        timestamp = arrow.now().timestamp
        # 获取运营数据，更新时间大于1天前的直接忽略
        statistics = StatisticsMetric.objects.filter(update_time__gte=timestamp - 24 * 60 * 60)
        for stat in statistics:
            metrics = Metric.loads(stat.data)
            metric_data.extend(metrics.export_json())
        return metric_data

    @classmethod
    def export_text(cls):
        """
        输出指标文本形式
        """
        metric_text = []
        timestamp = arrow.now().timestamp
        # 获取运营数据，更新时间大于1天前的直接忽略
        statistics = StatisticsMetric.objects.filter(update_time__gte=timestamp - 24 * 60 * 60)
        for stat in statistics:
            metrics = Metric.loads(stat.data)
            metric_text.append(metrics.export_text())
        result = "\n".join(metric_text)
        return result
