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
from django.test import TestCase

from alarm_backends.constants import LATEST_POINT_WITH_ALL_KEY
from alarm_backends.core.cache import key
from alarm_backends.core.detect_result import CheckResult
from alarm_backends.tests.core.detect_result.mock import *  # noqa
from alarm_backends.tests.core.detect_result.mock_settings import *  # noqa
from bkmonitor.models import CacheNode

STRATEGIES = [
    {
        "id": 1,
        "name": "test_strategy1",
        "items": [
            {
                "id": 11,
                "name": "test_item11",
                "algorithms": [
                    {"id": 111, "level": "1", "dimensions_md5": "dummy_dimensions_md5_111"},
                    {"id": 112, "level": "2", "dimensions_md5": "dummy_dimensions_md5_112"},
                ],
                "no_data_config": {"is_enabled": False, "continuous": 5},
            },
            {
                "id": 12,
                "name": "test_item12",
                "algorithms": [
                    {"id": 121, "algorithm_id": 121, "level": "1", "dimensions_md5": "dummy_dimensions_md5_121"},
                    {"id": 122, "algorithm_id": 122, "level": "2", "dimensions_md5": "dummy_dimensions_md5_122"},
                ],
                "no_data_config": {"is_enabled": True, "continuous": 5},
            },
        ],
    },
    {
        "id": 2,
        "name": "test_strategy2",
        "items": [
            {
                "id": 21,
                "name": "test_item21",
                "algorithms": [
                    {"id": 211, "level": "1", "dimensions_md5": "dummy_dimensions_md5_211"},
                    {"id": 212, "level": "2", "dimensions_md5": "dummy_dimensions_md5_212"},
                ],
                "no_data_config": {"is_enabled": False, "continuous": 5},
            },
            {
                "id": 22,
                "name": "test_item22",
                "algorithms": [
                    {"id": 221, "level": "1", "dimensions_md5": "dummy_dimensions_md5_221"},
                    {"id": 222, "level": "2", "dimensions_md5": "dummy_dimensions_md5_222"},
                ],
                "no_data_config": {"is_enabled": True, "continuous": 5},
            },
        ],
    },
]


class TestCleanResult(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        CacheNode.refresh_from_settings()
        redis_pipeline = CheckResult.pipeline()

        self.strategy_cache_patcher = patch(
            "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategies",
            MagicMock(return_value=STRATEGIES),
        )
        self.strategy_cache_patcher.start()

        self.strategies = STRATEGIES
        self.now_timestamp = arrow.utcnow().timestamp
        self.three_hours_ago = arrow.utcnow().replace(hours=-3).timestamp
        self.two_hours_ago = arrow.utcnow().replace(hours=-2).timestamp
        check_result_data = {
            "{}|{}".format(self.three_hours_ago, "ANOMALY"): self.three_hours_ago,
            "{}|{}".format(self.now_timestamp, "ANOMALY"): self.now_timestamp,
        }
        timestamps = [self.now_timestamp, self.three_hours_ago]
        for strategy in self.strategies:
            for item in strategy["items"]:
                last_checkpoints = {}
                level_list = set()
                for index, algorithm in enumerate(item["algorithms"]):
                    level_list.add(algorithm["level"])
                    cr = CheckResult(
                        strategy_id=strategy["id"],
                        item_id=item["id"],
                        dimensions_md5=algorithm["dimensions_md5"],
                        level=algorithm["level"],
                    )
                    # clean old data
                    key.CHECK_RESULT_CACHE_KEY.client.zremrangebyscore(cr.check_result_cache_key, 0, float("inf"))
                    cr.add_check_result_cache(**check_result_data)
                    cr.update_key_to_dimension(dimensions={})
                    last_checkpoints[(algorithm["dimensions_md5"], algorithm["level"])] = timestamps[index]
                for level in level_list:
                    last_checkpoints[(LATEST_POINT_WITH_ALL_KEY, level)] = self.now_timestamp

                for check_point_key_tuple, point_timestamp in list(last_checkpoints.items()):
                    _dimensions_md5, level = check_point_key_tuple
                    CheckResult.update_last_checkpoint_by_d_md5(
                        strategy["id"], item["id"], _dimensions_md5, point_timestamp, level
                    )
                CheckResult.expire_last_checkpoint_cache(strategy_id=strategy["id"], item_id=item["id"])

        redis_pipeline.execute()

    def tearDown(self):
        self.strategy_cache_patcher.stop()

    @patch(ALARM_BACKENDS_CLEAN_STRATEGY_CACHE_MANAGER_REFRESH, MagicMock(return_value=True))
    @patch(
        "alarm_backends.core.detect_result.clean.detect_result_point_required", MagicMock(return_value={"1.11.1": 1})
    )
    def test_clean_expired_detect_result(self):
        check_result_cache_key = key.CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=self.strategies[0]["id"],
            item_id=self.strategies[0]["items"][0]["id"],
            dimensions_md5=self.strategies[0]["items"][0]["algorithms"][0]["dimensions_md5"],
            level=self.strategies[0]["items"][0]["algorithms"][0]["level"],
        )
        all_members = key.CHECK_RESULT_CACHE_KEY.client.zrangebyscore(check_result_cache_key, 0, float("inf"))
        self.assertEqual(
            all_members,
            ["{}|{}".format(self.three_hours_ago, "ANOMALY"), "{}|{}".format(self.now_timestamp, "ANOMALY")],
        )
