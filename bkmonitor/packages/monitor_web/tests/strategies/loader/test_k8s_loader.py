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

from django.conf import settings

from api.kubernetes.default import FetchK8sClusterListResource
from core.errors.strategy import CreateStrategyError
from bkmonitor.models import StrategyModel, StrategyLabel, DefaultStrategyBizAccessModel
from monitor_web.strategies.loader import (
    K8sDefaultAlarmStrategyLoader,
)
from monitor_web.strategies.default_settings.k8s import v1, v2

pytestmark = pytest.mark.django_db


class TestK8sDefaultAlarmStrategyLoader:
    def test_has_default_strategy_for_v1(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is False

    def test_has_default_strategy_for_v1_have_label(self, add_strategy_label):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is True

    def test_get_versions_of_access__empty(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == set()

    def test_get_versions_of_access__exist(self, add_default_strategy_biz_access):
        """没有k8s系统内置label ."""
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == {"v2"}

    def test_check_before_set_cache__no_cluster(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.check_before_set_cache()
        assert actual is False

    def test_check_before_set_cache__have_cluster(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.check_before_set_cache()
        assert actual is True

    def test_has_default_strategy(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 2
        assert strategies_list[0]["version"] == "v1"
        assert (
            len(getattr(strategies_list[0]["module"], loader.STRATEGY_ATTR_NAME))
            == len(v1.DEFAULT_K8S_STRATEGIES)
            == 17
        )
        assert strategies_list[1]["version"] == "v2"
        assert (
            len(getattr(strategies_list[1]["module"], loader.STRATEGY_ATTR_NAME))
            == len(v2.DEFAULT_K8S_STRATEGIES)
            == 25
        )

    def test_get_notice_group(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        config_type = None
        notice_group_ids = loader.get_notice_group(config_type)
        assert notice_group_ids[0] > 0
        notice_group_ids_2 = loader.get_notice_group(config_type)
        assert notice_group_ids == notice_group_ids_2

    def test_load_strategies(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        notice_group_ids = loader.get_notice_group()
        strategies_list = loader.get_default_strategy()
        items = [strategies_list[0]]
        for item in items:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert total == len(v1.DEFAULT_K8S_STRATEGIES)

        items1 = [strategies_list[1]]
        for item in items1:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert total == len(v1.DEFAULT_K8S_STRATEGIES) + len(v2.DEFAULT_K8S_STRATEGIES)

    def test_load_strategy__repeat_loading(self):
        bk_biz_id = 2
        loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()

        for item in strategies_list:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            strategy_config_list = loader.load_strategies(strategies)
            assert strategy_config_list[0]["notice"]["user_groups"] == loader.get_notice_group(
                strategies[0].get("type")
            )
            assert strategy_config_list[1]["notice"]["user_groups"] == loader.get_notice_group(
                strategies[1].get("type")
            )

        total = StrategyModel.objects.all().count()
        assert total == len(v1.DEFAULT_K8S_STRATEGIES) + len(v2.DEFAULT_K8S_STRATEGIES)

        with pytest.raises(CreateStrategyError):
            module = strategies_list[0]["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)

    def test_run(self):
        bk_biz_id = 2
        assert K8sDefaultAlarmStrategyLoader.CACHE == set()

        os_loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()
        assert K8sDefaultAlarmStrategyLoader.CACHE == set()
        StrategyModel.objects.all().count() == 0

    def test_run(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        bk_biz_id = 2
        K8sDefaultAlarmStrategyLoader.CACHE = set()
        os_loader_1 = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_1.run()
        assert K8sDefaultAlarmStrategyLoader.CACHE == {2}
        StrategyModel.objects.all().count() == len(v1.DEFAULT_K8S_STRATEGIES) + len(v2.DEFAULT_K8S_STRATEGIES)
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 2
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "k8s"
        assert models[1].bk_biz_id == 2
        assert models[1].version == "v2"
        assert models[1].access_type == "k8s"

        os_loader_2 = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_2.run()
        assert K8sDefaultAlarmStrategyLoader.CACHE == {2}
        StrategyModel.objects.all().count() == len(v1.DEFAULT_K8S_STRATEGIES) + len(v2.DEFAULT_K8S_STRATEGIES)
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 2
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "k8s"
        assert models[1].bk_biz_id == 2
        assert models[1].version == "v2"
        assert models[1].access_type == "k8s"

    def test_run__have_strategy(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters, add_strategy_label):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        bk_biz_id = 2
        K8sDefaultAlarmStrategyLoader.CACHE = set()
        os_loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()
        assert K8sDefaultAlarmStrategyLoader.CACHE == {2}
        StrategyModel.objects.all().count() == len(v2.DEFAULT_K8S_STRATEGIES)
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 2
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "k8s"
        assert models[1].bk_biz_id == 2
        assert models[1].version == "v2"
        assert models[1].access_type == "k8s"

    def test_add_multiple_labels(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters, add_strategy_label):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        bk_biz_id = 2
        K8sDefaultAlarmStrategyLoader.CACHE = set()
        os_loader = K8sDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()

        models = StrategyLabel.objects.filter(bk_biz_id=bk_biz_id, label_name="/k8s_集群资源/")
        assert len(models) == 2
