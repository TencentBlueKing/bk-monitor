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

from bkmonitor.models.aiops import AIFeatureSettings

AI_SETTING_INIT_DATA = {
    "bk_biz_id": 1,
    "config": {
        "kpi_anomaly_detection": {},
        "multivariate_anomaly_detection": {
            "host": {
                "is_enabled": True,
                "intelligent_detect": {
                    "data_source_label": "bk_data",
                    "data_type_label": "time_series",
                    "result_table_id": "table_id",
                    "message": "create dataflow success",
                },
            }
        },
    },
}

HOST = [{"ip": "1.1.1.1", "bk_cloud_id": 0}, {"ip": "1.1.1.2", "bk_cloud_id": 0}]

PARAMS_ONE = {"bk_biz_id": 1, "host": HOST}

RETURN_POINTS = []

PARAMS_TWO = {"bk_biz_id": 2, "host": HOST}


class TestHostMonitorViewSet(TestCase):
    def setUp(self):
        AIFeatureSettings.objects.all().delete()
        AIFeatureSettings(**AI_SETTING_INIT_DATA)

    @mock.patch("bkmonitor.data_source.unify_query.query.UnifyQuery.query_data")
    @mock.patch("bkmonitor.data_source.data_source.BkdataTimeSeriesDataSource")
    def test_host_intelligen_anomaly(self, data_source, query_data):
        pass
