"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

from unittest import mock
from django.test import TestCase

from bkmonitor.models import AIFeatureSettings, AlgorithmModel
from bkmonitor.models.strategy import AlgorithmChoiceConfig
from constants.aiops import AI_SETTING_APPLICATION_CONFIG_KEY
from monitor_web.aiops.ai_setting.resources import SaveAiSettingResource
from monitor_web.strategies.resources.v2 import ListIntelligentModelsResource

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
    "bk_biz_id": 2,
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
    databases = {"monitor_api", "default"}

    def setUp(self):
        AIFeatureSettings.objects.all().delete()
        AIFeatureSettings.objects.create(**APPLICATION_CONFIG_INIT_DATA)
        AIFeatureSettings.objects.create(**APPLICATION_CONFIG_INIT_CLOSE_DATA)

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
        close_delay.assert_called_with(3, ["host"])


class TestListIntelligentModelsResource(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        AIFeatureSettings.objects.all().delete()

    def _create_ai_setting(self, bk_biz_id, default_plan_id):
        config = deepcopy(APPLICATION_CONFIG_INIT_DATA["config"])
        config["kpi_anomaly_detection"] = {"default_plan_id": 1, "is_sdk_enabled": True}
        config["multivariate_anomaly_detection"]["host"].update(
            {
                "default_plan_id": default_plan_id,
                "default_sensitivity": 5,
                "exclude_target": [],
                "intelligent_detect": {},
                "is_enabled": True,
            }
        )
        AIFeatureSettings.objects.create(bk_biz_id=bk_biz_id, config=config)

    @staticmethod
    def _create_plan(plan_id, algorithm, *, is_default=False, name=None):
        AlgorithmChoiceConfig.objects.create(
            id=plan_id,
            alias=f"plan-{plan_id}",
            name=name or f"plan_name_{plan_id}",
            document="",
            description="",
            is_default=is_default,
            version_no="",
            instruction="",
            variable_info={},
            ts_freq=0,
            algorithm=algorithm,
            config={},
        )

    def test_list_multivariate_models_should_fallback_to_host_plan(self):
        self._create_ai_setting(bk_biz_id=10, default_plan_id=2001)
        self._create_plan(2001, AlgorithmModel.AlgorithmChoices.HostAnomalyDetection, name="host_scene_plan")

        result = ListIntelligentModelsResource().request(
            {"bk_biz_id": 10, "algorithm": AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection}
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 2001)
        self.assertTrue(result[0]["is_default"])

    def test_list_multivariate_models_should_keep_direct_algorithm_plan(self):
        self._create_ai_setting(bk_biz_id=11, default_plan_id=3001)
        self._create_plan(2002, AlgorithmModel.AlgorithmChoices.HostAnomalyDetection, name="host_scene_plan")
        self._create_plan(
            3001,
            AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection,
            is_default=True,
            name="multivariate_scene_plan",
        )

        result = ListIntelligentModelsResource().request(
            {"bk_biz_id": 11, "algorithm": AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection}
        )

        self.assertEqual([item["id"] for item in result], [3001])
        self.assertTrue(result[0]["is_default"])

    def test_list_host_models_should_fallback_to_multivariate_plan(self):
        self._create_ai_setting(bk_biz_id=12, default_plan_id=4001)
        self._create_plan(
            4001,
            AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection,
            is_default=True,
            name="multivariate_scene_plan",
        )

        result = ListIntelligentModelsResource().request(
            {"bk_biz_id": 12, "algorithm": AlgorithmModel.AlgorithmChoices.HostAnomalyDetection}
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 4001)
        self.assertTrue(result[0]["is_default"])
