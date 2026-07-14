"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.records import DataRecord

from .config import FORMAT_RAW_DATA, STANDARD_DATA, STRATEGY_CONFIG_V3


class TestRecords:
    def test_record(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG_V3)

        strategy_id = 1
        strategy = Strategy(strategy_id)

        record = DataRecord(strategy.items[0], FORMAT_RAW_DATA)
        record.clean()
        record.data.pop("access_time", None)
        record.data.pop("dimension_fields", None)
        assert record.data == STANDARD_DATA

    def test_partial_query_flag_is_propagated_only_for_partial_data(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG_V3)
        item = Strategy(1).items[0]

        item.query.is_partial = True
        partial_record = DataRecord(item, FORMAT_RAW_DATA).clean()
        assert partial_record.data["is_partial"] is True

        item.query.is_partial = False
        complete_record = DataRecord(item, FORMAT_RAW_DATA).clean()
        assert "is_partial" not in complete_record.data
