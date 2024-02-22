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
from copy import deepcopy

import mock
from django.test import TestCase

from constants.aiops import AI_SETTING_APPLICATION_CONFIG_KEY
from monitor.models import ApplicationConfig
from monitor_web.aiops.ai_setting.resources import SaveAiSettingResource

APPLICATION_CONFIG_INIT_DATA = {
    "bk_biz_id": 1,
    "config": {
        "kpi_anomaly_detection": {"is_enabled": False, "default_sensitivity": 5, "default_plan_id": 87},
        "multivariate_anomaly_detection": {
            "host": {
                "is_enabled": False,
                "default_sensitivity": 5,
                "exclude_target": [],
                "default_plan_id": 155,
                "plan_args": {"$metric_list": "system__cpu_detail__usage,system__load__load1", "$sensitivity": 5},
                "intelligent_detect": {
                    "data_flow_id": 1,
                    "data_source_label": "bk_data",
                    "data_type_label": "time_series",
                    "result_table_id": "table_id",
                    "metric_field": "value",
                    "extend_fields": {},
                    "agg_condition": [],
                    "agg_dimension": ["bk_biz_id", "ip", "bk_cloud_id"],
                    "plan_id": 155,
                    "agg_method": "",
                    "status": "success",
                    "message": "create dataflow success",
                },
            }
        },
    },
}

APPLICATION_CONFIG_INIT_CLOSE_DATA = {
    "bk_biz_id": 1,
    "config": {
        "kpi_anomaly_detection": {"is_enabled": False, "default_sensitivity": 5, "default_plan_id": 87},
        "multivariate_anomaly_detection": {
            "host": {
                "is_enabled": True,
                "default_sensitivity": 5,
                "exclude_target": [],
                "default_plan_id": 155,
                "plan_args": {"$metric_list": "system__cpu_detail__usage,system__load__load1", "$sensitivity": 5},
                "intelligent_detect": {
                    "data_flow_id": 1,
                    "data_source_label": "bk_data",
                    "data_type_label": "time_series",
                    "result_table_id": "table_id",
                    "metric_field": "value",
                    "extend_fields": {},
                    "agg_condition": [],
                    "agg_dimension": ["bk_biz_id", "ip", "bk_cloud_id"],
                    "plan_id": 155,
                    "agg_method": "",
                    "status": "success",
                    "message": "create dataflow success",
                },
            }
        },
    },
}

empty_template_ai_setting_data = {
    "key": AI_SETTING_APPLICATION_CONFIG_KEY,
    "kpi_anomaly_detection": {},
    "multivariate_anomaly_detection": {"host": {"is_enabled": True}},
}


class TestAiSettingViewSet(TestCase):
    def setUp(self):
        ApplicationConfig.objects.filter(key=AI_SETTING_APPLICATION_CONFIG_KEY).delete()
        ApplicationConfig.objects.create(**APPLICATION_CONFIG_INIT_DATA)
        ApplicationConfig.objects.create(**APPLICATION_CONFIG_INIT_CLOSE_DATA)

    @mock.patch("monitor_web.tasks.access_aiops_multivariate_anomaly_detection_by_bk_biz_id.delay")
    def test_save_ai_setting_existing(self, access_delay):
        data = deepcopy(empty_template_ai_setting_data)
        data["bk_biz_id"] = 1
        SaveAiSettingResource().request(data)
        access_delay.assert_called_with(1, ["host"])

    @mock.patch("monitor_web.tasks.access_aiops_multivariate_anomaly_detection_by_bk_biz_id.delay")
    def test_save_ai_setting_not_existing(self, access_delay):
        data = deepcopy(empty_template_ai_setting_data)
        data["bk_biz_id"] = 2
        SaveAiSettingResource().request(data)
        access_delay.assert_called_with(2, ["host"])

    @mock.patch("monitor_web.tasks.stop_aiops_multivariate_anomaly_detection_flow.delay")
    def test_close_access(self, close_delay):
        data = deepcopy(empty_template_ai_setting_data)
        data["bk_biz_id"] = 3
        data["multivariate_anomaly_detection"]["host"]["is_enabled"] = False
        SaveAiSettingResource().request(data)
        close_delay.assert_called_with([1])
