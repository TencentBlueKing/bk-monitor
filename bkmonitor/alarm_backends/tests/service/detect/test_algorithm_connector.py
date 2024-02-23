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

import pytest

from alarm_backends.core.control.item import Item
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.tests.service.detect import DataPoint
from bkmonitor.models import CacheNode

pytestmark = pytest.mark.django_db


@pytest.fixture()
def item():
    get_node_by_strategy_id(0)
    CacheNode.refresh_from_settings()

    class Strategy:
        config = {"detect": [{"level": 1, "connector": "and"}, {"level": 2, "connector": ""}]}
        id = 1
        bk_biz_id = 2
        snapshot_key = ""

    return Item(
        {
            "id": 1,
            "name": "avg(测试指标)",
            "query_configs": [],
            "algorithms": [
                {"level": 1, "type": "Threshold", "config": [[{"method": "gt", "threshold": 2}]]},
                {"level": 1, "type": "Threshold", "config": [[{"method": "lte", "threshold": 4}]]},
                {"level": 2, "type": "Threshold", "config": [[{"method": "gte", "threshold": 4}]]},
                {"level": 2, "type": "Threshold", "config": [[{"method": "lt", "threshold": 6}]]},
            ],
        },
        Strategy,
    )


class TestAlgorithmConnector:
    def test_and(self, item):
        datapoints = [DataPoint(i, 100000000, "percent", item) for i in range(1, 8)]
        outputs = item.detect(datapoints)
        assert len(outputs) == 3

    def test_or(self, item):
        datapoints = [DataPoint(i, 100000000, "percent", item) for i in range(1, 8)]
        item.algorithm_connectors.update({1: "or", 2: "or"})
        outputs = item.detect(datapoints)
        assert len(outputs) == 7
