"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models import Shield
from bkmonitor.models.issue import StrategyIssueConfig
from bkmonitor.models.strategy import StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from core.drf_resource import resource
from bkmonitor.strategy.strategy import StrategyConfig


class TestDeleteStrategyResource:
    def test_delete_strategy(self, mocker):
        shield_instance = Shield()
        shield_instance.dimension_config = {"strategy_id": 1, "level": [1, 2]}
        mocker.patch.object(Shield.objects, "filter", return_value=[shield_instance])
        mocker.patch.object(Shield, "delete")
        mocker.patch.object(StrategyConfig, "delete")
        mocker.patch.object(StrategyConfig, "get_object", return_value=None)
        resource.strategies.delete_strategy_config(bk_biz_id=2, id=1)

    def test_delete_by_strategy_ids_should_delete_issue_config(self, clean_model):
        StrategyModel.objects.create(id=1, name="test", scenario="os", bk_biz_id=2)
        StrategyIssueConfig.objects.create(
            strategy_id=1,
            bk_biz_id=2,
            aggregate_dimensions=[],
            conditions=[],
            alert_levels=[1],
        )

        Strategy.delete_by_strategy_ids([1])

        assert StrategyIssueConfig.objects.filter(strategy_id=1).count() == 0
