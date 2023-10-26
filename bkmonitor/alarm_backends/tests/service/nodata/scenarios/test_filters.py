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


from django.test import TestCase

from alarm_backends.service.nodata.scenarios.filters import DimensionRangeFilter
from alarm_backends.tests.service.nodata.mock import *  # noqa
from alarm_backends.tests.service.nodata.mock_settings import *  # noqa


class TestFilters(TestCase):
    def setUp(self):
        self.filter = DimensionRangeFilter()

    def test_filters__simple_condition(self):
        item_config = {
            "id": 11,
            "name": "item1",
            "query_configs": [
                {
                    "agg_method": "REAL_TIME",
                    "agg_condition": [{"key": "bk_target_ip", "method": "eq", "value": "127.0.0.1"}],
                }
            ],
        }
        item = MockItem(item_config=item_config, data_sources=[])
        dimension = {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}
        self.assertFalse(self.filter.filter(dimension, item))

        dimension = {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": "0"}
        self.assertTrue(self.filter.filter(dimension, item))

    def test_filters_not_exist_condition(self):
        item_config = {
            "id": 11,
            "name": "item1",
            "query_configs": [{"agg_condition": [{"key": "not_exist_dimension", "method": "eq", "value": "1"}]}],
        }
        item = MockItem(item_config=item_config, data_sources=[])
        dimension = {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}
        self.assertFalse(self.filter.filter(dimension, item))

    def test_filters_none_condition(self):
        item_config = {"id": 11, "name": "item1", "query_configs": [{"agg_condition": []}]}
        item = MockItem(item_config=item_config, data_sources=[])
        dimension = {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}
        self.assertFalse(self.filter.filter(dimension, item))
