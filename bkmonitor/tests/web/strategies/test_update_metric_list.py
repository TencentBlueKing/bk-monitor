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
import mock
from django.test import TestCase
from monitor_web.strategies.metric_list_cache import (
    BkFtaAlertCacheManager,
    BkMonitorAlertCacheManager,
)

from bkmonitor.models import AlertConfig
from bkmonitor.models import EventPluginV2 as EventPlugin
from bkmonitor.models import QueryConfigModel, StrategyModel
from bkmonitor.models.metric_list_cache import MetricListCache


class TestUpdateMetricListResource(TestCase):
    def setUp(self):  # NOCC:invalid-name(设计如此:)
        MetricListCache.objects.all().delete()
        StrategyModel.objects.all().delete()
        QueryConfigModel.objects.all().delete()
        EventPlugin.objects.all().delete()

        EventPlugin.objects.create(plugin_id="test", version="1.0.0")

    def tearDown(self):  # NOCC:invalid-name(设计如此:)
        MetricListCache.objects.all().delete()
        StrategyModel.objects.all().delete()
        QueryConfigModel.objects.all().delete()
        EventPlugin.objects.all().delete()
        AlertConfig.objects.all().delete()

    def alert_configs(self):
        return [
            {
                "is_enabled": True,
                "create_user": "admin",
                "update_user": "admin",
                "plugin_id": "test",
                "name": "服务实例告警",
                "rules": [{"key": "alarm_type", "value": ["服务实例告警"], "method": "eq", "condition": ""}],
                "is_manual": False,
                "order": 0,
            },
            {
                "is_enabled": True,
                "create_user": "admin",
                "update_user": "admin",
                "plugin_id": "test",
                "name": "服务实例告警1",
                "rules": [{"key": "alarm_type", "value": ["服务实例告警1"], "method": "eq", "condition": ""}],
                "is_manual": False,
                "order": 1,
            },
        ]

    def test_default_alert_config(self):
        """
        全业务数据同步测试
        :return:
        """
        configs = self.alert_configs()
        config_objs = [AlertConfig(**config) for config in configs]
        AlertConfig.objects.bulk_create(config_objs)
        alert_info_patch = mock.patch(
            "monitor_web.strategies.metric_list_cache.BkFtaAlertCacheManager.search_alerts",
            return_value={
                "alert_tags": {"测试告警": {"key"}},
                "alert_target_types": {"测试告警": {"SERVICE", "HOST"}},
                "alert_plugins": {"测试告警": {"bkmonitor"}},
            },
        )
        alert_info_patch.start()
        BkFtaAlertCacheManager(bk_biz_id=0).run()
        metrics = MetricListCache.objects.all()
        self.assertEqual(metrics.count(), 4)
        alert_info_patch.stop()

    def test_sync_alert_config(self):
        """
        单业务告警数据同步
        :return:
        """
        alert_info_patch = mock.patch(
            "monitor_web.strategies.metric_list_cache.BkFtaAlertCacheManager.search_alerts",
            return_value={
                "alert_tags": {"测试告警": {"key"}},
                "alert_target_types": {"测试告警": {"SERVICE", "HOST"}},
                "alert_plugins": {"测试告警": {"bkmonitor"}},
            },
        )
        alert_info_patch.start()
        BkFtaAlertCacheManager(bk_biz_id=2).run()
        metrics = MetricListCache.objects.all()
        self.assertEqual(metrics.filter(bk_biz_id=2).count(), 2)
        alert_info_patch.stop()

    def test_sync_default_alert_config(self):
        """
        业务发现的告警名称全业务已经存在
        :return:
        """
        configs = self.alert_configs()
        config_objs = [AlertConfig(**config) for config in configs]
        AlertConfig.objects.bulk_create(config_objs)
        alert_info_patch = mock.patch(
            "monitor_web.strategies.metric_list_cache.BkFtaAlertCacheManager.search_alerts",
            return_value={
                "alert_tags": {"服务实例告警1": {"key"}},
                "alert_target_types": {"服务实例告警1": {"SERVICE", "HOST"}},
                "alert_plugins": {"服务实例告警1": {"bkmonitor"}},
            },
        )
        alert_info_patch.start()
        BkFtaAlertCacheManager(bk_biz_id=0).run()
        BkFtaAlertCacheManager(bk_biz_id=2).run()
        metrics = MetricListCache.objects.all()
        self.assertEqual(metrics.filter(bk_biz_id=0).count(), 4)

        # 业务发现的告警名称全业务已经存在， 不会重复刷新
        self.assertEqual(metrics.filter(bk_biz_id=2).count(), 0)

    def test_sync_strategy_metric(self):
        s = StrategyModel.objects.create(id=1, name="test", scenario="host_process", bk_biz_id=2)
        QueryConfigModel.objects.create(
            strategy_id=s.id,
            item_id=1,
            config={"agg_dimension": ["ip"]},
            data_type_label="log",
            data_source_label="bk_monitor",
        )

        BkMonitorAlertCacheManager().run()
        self.assertEqual(MetricListCache.objects.filter(result_table_id="strategy").count(), 0)

        BkMonitorAlertCacheManager(2).run()

        self.assertEqual(
            MetricListCache.objects.filter(result_table_id="strategy", data_type_label="alert", bk_biz_id=2).count(), 1
        )
