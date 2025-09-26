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


from django.test import TestCase

from alarm_backends.core.detect_result import CheckResult
from bkmonitor.models import CacheNode
from bkmonitor.utils.common_utils import count_md5

DIMENSION = {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0}


class TestDetectResult(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        CacheNode.refresh_from_settings()

    def test_md5_to_dimension_key(self):
        check_result = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION), level=2, service_type="detect"
        )
        dimension_key = "{service_type}.{strategy_id}.{item_id}".format(service_type="detect", strategy_id=1, item_id=1)
        self.assertTrue(check_result.md5_to_dimension_key.endswith(dimension_key))

    def test_get_dimension_by_key(self):
        check_result = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION), level=2, service_type="detect"
        )
        self.assertIsNone(
            CheckResult.get_dimension_by_key(
                service_type="detect", strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION)
            )
        )

        check_result.update_key_to_dimension(DIMENSION)
        check_result.pipeline().execute()
        self.assertEqual(
            CheckResult.get_dimension_by_key(
                service_type="detect", strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION)
            ),
            DIMENSION,
        )

    def test_remove_dimension_by_key(self):
        check_result = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION), level=2, service_type="detect"
        )
        check_result.update_key_to_dimension(DIMENSION)
        check_result.pipeline().execute()
        self.assertEqual(
            CheckResult.get_dimension_by_key(
                service_type="detect", strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION)
            ),
            DIMENSION,
        )

        CheckResult.remove_dimension_by_key(
            service_type="detect", strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION)
        )
        self.assertIsNone(
            CheckResult.get_dimension_by_key(
                service_type="detect", strategy_id=1, item_id=1, dimensions_md5=count_md5(DIMENSION)
            )
        )

    def test_get_dimension_keys(self):
        dimension1 = {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0}
        check_result1 = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(dimension1), level=2, service_type="detect"
        )
        check_result1.update_key_to_dimension(dimension1)
        redis_pipeline = check_result1.pipeline()

        dimension2 = {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": 0}
        check_result2 = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(dimension2), level=2, service_type="nodata"
        )
        check_result2.update_key_to_dimension(dimension2)

        dimension3 = {"bk_target_ip": "127.0.0.3", "bk_target_cloud_id": 0}
        check_result3 = CheckResult(
            strategy_id=1, item_id=1, dimensions_md5=count_md5(dimension3), level=2, service_type="nodata"
        )
        check_result3.update_key_to_dimension(dimension3)
        redis_pipeline.execute()

        self.assertEqual(
            CheckResult.get_dimensions_keys(service_type="nodata", strategy_id=1, item_id=1),
            [check_result2.dimensions_md5, check_result3.dimensions_md5],
        )
        self.assertEqual(
            CheckResult.get_dimensions_keys(service_type="detect", strategy_id=1, item_id=1),
            [check_result1.dimensions_md5],
        )
