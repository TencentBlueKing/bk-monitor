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

from core.errors.strategy import CreateStrategyError
from bkmonitor.models import StrategyModel
from bkmonitor.models import DefaultStrategyBizAccessModel
from monitor_web.strategies.loader import (
    GseDefaultAlarmStrategyLoader,
)
from monitor_web.strategies.default_settings.gse import v1

pytestmark = pytest.mark.django_db


class TestOsDefaultAlarmStrategyLoader:
    def test_has_default_strategy_for_v1(self):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is False

    def test_has_default_strategy_for_v1__have_strategy(self, add_strategy_model):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is True

    def test_get_versions_of_access__empty(self):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == set()

    def test_get_versions_of_access__exist(self, add_default_strategy_biz_access):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == {"v2"}

    def test_check_before_set_cache(self):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.check_before_set_cache()
        assert actual is True

    def test_has_default_strategy(self):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 1
        assert strategies_list[0]["version"] == "v1"
        assert (
            len(getattr(strategies_list[0]["module"], loader.STRATEGY_ATTR_NAME))
            == len(v1.DEFAULT_GSE_PROCESS_EVENT_STRATEGIES)
            == 2
        )

    def test_get_notice_group(self):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        config_type = "business"
        notice_group_ids = loader.get_notice_group(config_type)
        assert notice_group_ids[0] > 0
        notice_group_ids_2 = loader.get_notice_group(config_type)
        assert notice_group_ids == notice_group_ids_2

    def test_load_strategies(self, monkeypatch_api_cmdb_get_business, monkeypatch_api_cmdb_get_blueking_biz):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 1
        items = [strategies_list[0]]
        for item in items:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            strategy_config_list = loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert total == 2
            assert len(strategy_config_list) == len(strategy_config_list) == 2
            assert strategy_config_list[0]["notice"]["user_groups"] == loader.get_notice_group(strategies[0]["type"])
            assert strategy_config_list[1]["notice"]["user_groups"] == loader.get_notice_group(strategies[1]["type"])

    def test_load_strategies__repeat_loading(
        self, monkeypatch_api_cmdb_get_business, monkeypatch_api_cmdb_get_blueking_biz
    ):
        bk_biz_id = 2
        loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()

        for item in strategies_list:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert total == 2

        with pytest.raises(CreateStrategyError):
            module = strategies_list[0]["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)

    def test_run(self, add_metric_list_cache):
        bk_biz_id = 2
        assert GseDefaultAlarmStrategyLoader.CACHE == set()
        GseDefaultAlarmStrategyLoader.CACHE = set()

        os_loader_1 = GseDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_1.run()
        assert GseDefaultAlarmStrategyLoader.CACHE == {2}
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "gse"

        os_loader_2 = GseDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_2.run()
        assert GseDefaultAlarmStrategyLoader.CACHE == {2}
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "gse"

    def test_run__have_strategy(self, add_strategy_model):
        bk_biz_id = 2
        GseDefaultAlarmStrategyLoader.CACHE = set()
        os_loader = GseDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()

        assert GseDefaultAlarmStrategyLoader.CACHE == {2}
        assert StrategyModel.objects.all().count() == 2
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "gse"
