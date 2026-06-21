"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
    OsDefaultAlarmStrategyLoader,
)
from monitor_web.strategies.default_settings.os import v1

pytestmark = pytest.mark.django_db


class TestOsDefaultAlarmStrategyLoader:
    def test_has_default_strategy_for_v1(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is False

    def test_has_default_strategy_for_v1__have_strategy(self, add_strategy_model):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.has_default_strategy_for_v1()
        assert actual is True

    def test_get_versions_of_access__empty(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == set()

    def test_get_versions_of_access__exist(self, add_default_strategy_biz_access):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.get_versions_of_access()
        assert actual == {"v2"}

    def test_check_before_set_cache(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        actual = loader.check_before_set_cache()
        assert actual is True

    def test_has_default_strategy(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 1
        assert strategies_list[0]["version"] == "v1"
        assert (
            len(getattr(strategies_list[0]["module"], loader.STRATEGY_ATTR_NAME)) == len(v1.DEFAULT_OS_STRATEGIES) == 12
        )

    def test_get_notice_group(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        config_type = None
        notice_group_ids = loader.get_notice_group(config_type)
        assert notice_group_ids[0] > 0
        notice_group_ids_2 = loader.get_notice_group(config_type)
        assert notice_group_ids == notice_group_ids_2

    def test_load_strategy__no_metrics(self):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 1
        items = [strategies_list[0]]
        for item in items:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert total == 0

    def test_load_strategies__have_metrics(self, add_metric_list_cache):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()
        assert len(strategies_list) == 1
        items = [strategies_list[0]]
        for item in items:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            strategy_config_list = loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert strategy_config_list[0]["notice"]["user_groups"] == loader.get_notice_group(
                strategies[0].get("type")
            )
            assert total == 1

    def test_load_strategies__repeat_loading(self, add_metric_list_cache):
        bk_biz_id = 2
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        strategies_list = loader.get_default_strategy()

        for item in strategies_list:
            module = item["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            strategy_config_list = loader.load_strategies(strategies)
            total = StrategyModel.objects.all().count()
            assert strategy_config_list[0]["notice"]["user_groups"] == loader.get_notice_group(
                strategies[0].get("type")
            )
            assert total == 1

        with pytest.raises(CreateStrategyError):
            module = strategies_list[0]["module"]
            strategies = getattr(module, loader.STRATEGY_ATTR_NAME)
            loader.load_strategies(strategies)

    def test_run(self, add_metric_list_cache):
        bk_biz_id = 2
        assert OsDefaultAlarmStrategyLoader.CACHE == set()
        OsDefaultAlarmStrategyLoader.CACHE = set()

        os_loader_1 = OsDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_1.run()
        assert OsDefaultAlarmStrategyLoader.CACHE == {2}
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "os"

        os_loader_2 = OsDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader_2.run()
        assert OsDefaultAlarmStrategyLoader.CACHE == {2}
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "os"

    def test_run__have_strategy(self, add_strategy_model):
        bk_biz_id = 2
        OsDefaultAlarmStrategyLoader.CACHE = set()
        os_loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()

        assert OsDefaultAlarmStrategyLoader.CACHE == {2}
        assert StrategyModel.objects.all().count() == 2
        models = DefaultStrategyBizAccessModel.objects.all()
        assert len(models) == 1
        assert models[0].bk_biz_id == 2
        assert models[0].version == "v1"
        assert models[0].access_type == "os"

    def test_run__metrics_not_ready_skip_access(self):
        """指标未就绪时 load 产出 0 条策略，不应误写接入记录，保证后续指标就绪后仍可补建。

        覆盖多租户系统事件场景：custom 指标可能异步晚于业务激活就绪，
        若先标记接入会因幂等跳过而永久漏建。
        """
        bk_biz_id = 2
        OsDefaultAlarmStrategyLoader.CACHE = set()
        os_loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        os_loader.run()

        # 无匹配指标 -> 未创建任何策略
        assert StrategyModel.objects.all().count() == 0
        # 关键：未创建策略时不登记接入记录，下次指标就绪后仍可补建
        assert DefaultStrategyBizAccessModel.objects.all().count() == 0
        # 关键：未创建策略时也不写内存 CACHE，保证同进程内指标就绪后仍可重试（Blocking：避免缓存提前挡住重试）
        assert bk_biz_id not in OsDefaultAlarmStrategyLoader.CACHE

    def test_load_strategies__multi_tenant_custom_event(self):
        """多租户 custom event 系统事件主链路。

        覆盖最关键的新逻辑：
        - 多租户下按 bk_biz_id 过滤查询 custom event 指标；
        - 按 custom_event_name 建索引并匹配策略（而非 metric_field/__INDEX__）；
        - 生成的 metric_id 带 .OOM 而非退化成整表 __INDEX__；
        - 最终 query_config 落到 agg_method=COUNT + 主机维度 agg_dimension。
        """
        import importlib
        from unittest import mock

        from django.test import override_settings

        from monitor_web.strategies.default_settings.os import v2 as os_v2

        bk_biz_id = 2

        # 构造一个 V4 分业务系统事件指标（custom 源、event 类型）
        metric = mock.Mock()
        metric.data_source_label = "custom"
        metric.data_type_label = "event"
        metric.result_table_id = "base_tenant_2_event"
        metric.metric_field = "OOM"
        metric.metric_field_name = "OOM异常告警"
        metric.extend_fields = {"custom_event_name": "OOM"}
        metric.default_condition = []
        metric.default_dimensions = []
        metric.collect_interval = 1
        metric.unit = ""

        # loader 在单租户下实例化，避免触发多租户租户映射查询；load 时再切多租户走 custom event 分支
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)

        captured = []

        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(os_v2)
            oom_strategy = next(s for s in os_v2.DEFAULT_OS_STRATEGIES if s["metric_field"] == "OOM")
            with (
                mock.patch(
                    "monitor_web.strategies.loader.os_loader.MetricListCache.objects.filter",
                    side_effect=[[], [metric]],
                ) as filter_mock,
                mock.patch(
                    "monitor_web.strategies.loader.os_loader.resource.strategies.save_strategy_v2",
                    side_effect=lambda **kwargs: captured.append(kwargs),
                ),
                mock.patch.object(OsDefaultAlarmStrategyLoader, "get_notice_group", return_value=[1]),
            ):
                result = loader.load_strategies([oom_strategy])

        # 还原全局模块，避免 reload 污染其它用例
        importlib.reload(os_v2)

        assert len(result) == 1
        # 多租户 custom event 查询带 bk_biz_id 过滤（第 2 次 filter 为 custom event 查询）
        custom_call = filter_mock.call_args_list[1]
        assert custom_call.kwargs["bk_biz_id"] == bk_biz_id
        assert custom_call.kwargs["data_source_label"] == "custom"
        assert custom_call.kwargs["data_type_label"] == "event"

        query_config = captured[0]["items"][0]["query_configs"][0]
        # metric_id 带 custom_event_name(.OOM)，未退化为整表 __INDEX__
        assert query_config["metric_id"].endswith(".OOM")
        assert "__INDEX__" not in query_config["metric_id"]
        # custom event 检测语义：按事件名过滤 + COUNT 聚合 + 主机维度 group by
        assert query_config["custom_event_name"] == "OOM"
        assert query_config["agg_method"] == "COUNT"
        assert query_config["agg_dimension"] == ["bk_target_ip", "bk_target_cloud_id"]
