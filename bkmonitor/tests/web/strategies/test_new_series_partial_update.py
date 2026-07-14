"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.strategies.resources.v2 import UpdatePartialStrategyV2Resource


def test_partial_update_preserves_new_series_threshold():
    serializer = UpdatePartialStrategyV2Resource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "ids": [1],
            "edit_data": {
                "algorithms": [
                    {
                        "type": "NewSeries",
                        "level": 1,
                        "config": {"detect_range": 86400, "threshold": -2},
                    }
                ]
            },
        }
    )

    serializer.is_valid(raise_exception=True)

    algorithm = serializer.validated_data["edit_data"]["algorithms"][0]
    assert algorithm["config"]["threshold"] == -2


def test_update_algorithms_preserves_threshold_when_saving():
    strategy = mock.MagicMock()
    strategy.id = 1
    item = mock.MagicMock()
    item.id = 2
    item.algorithms = []
    strategy.items = [item]
    strategy.to_dict.side_effect = lambda: {
        "items": [
            {
                "algorithms": [algorithm.to_dict() for algorithm in item.algorithms],
                "query_configs": [
                    {
                        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        "agg_interval": 60,
                        "agg_dimension": ["ip"],
                    }
                ],
            }
        ]
    }
    algorithms = [
        {
            "type": "NewSeries",
            "level": 1,
            "config": {"detect_range": 86400, "effective_delay": 86400, "max_series": 100000, "threshold": -2},
        }
    ]

    UpdatePartialStrategyV2Resource.update_algorithms(strategy, algorithms)

    assert item.algorithms[0].config["threshold"] == -2
    item.save_algorithms.assert_called_once_with()
