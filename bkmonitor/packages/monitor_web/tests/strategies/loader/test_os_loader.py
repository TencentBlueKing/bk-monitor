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
                    # 多租户 3 次查询：related_id=system 时序 / custom event / process.port 时序
                    side_effect=[[], [metric], []],
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

    def test_run__atomic_rollback_on_partial_failure(self, add_metric_list_cache):
        """单版本加载中途 save 失败时，已创建策略与接入记录整体回滚，且不写 CACHE。

        锁住 base.run() 的 transaction.atomic 修复：save_strategy_v2 非幂等、逐条创建，
        部分成功后失败若不回滚，会残留半套策略，下次重试撞已存在策略而永久失败。
        django_db（savepoint 模式）下嵌套 atomic 抛异常回滚到 savepoint，故可验证。
        """
        from unittest import mock

        from bkmonitor.models.metric_list_cache import MetricListCache
        from core.drf_resource import resource

        bk_biz_id = 2
        OsDefaultAlarmStrategyLoader.CACHE = set()

        # 追加第 2 条可匹配 v1 的时序指标（system.io util），确保 load_strategies 会走到第 2 次 save
        MetricListCache.objects.create(
            bk_biz_id=0,
            category_display="物理机",
            collect_config="",
            collect_config_ids="",
            collect_interval=1,
            data_source_label="bk_monitor",
            data_target="host_target",
            data_type_label="time_series",
            default_condition=[],
            default_dimensions=["bk_target_ip", "bk_target_cloud_id"],
            description="磁盘IO使用率",
            dimensions=[{"id": "bk_target_ip", "is_dimension": True, "name": "目标IP", "type": "string"}],
            extend_fields={},
            metric_field="util",
            metric_field_name="磁盘IO使用率",
            plugin_type="",
            related_id="system",
            related_name="system",
            result_table_id="system.io",
            result_table_label="os",
            result_table_label_name="操作系统",
            result_table_name="磁盘IO",
            unit="percent",
            unit_conversion=1.0,
            use_frequency=6,
        )

        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)

        # patch 前捕获原始实现：第 1 条真实创建（使回滚有可回滚对象），第 2 条抛普通异常
        # （RuntimeError 而非 IntegrityError，避免污染 savepoint 外层事务）
        real_save = resource.strategies.save_strategy_v2
        call_state = {"n": 0}

        def save_side_effect(**kwargs):
            call_state["n"] += 1
            if call_state["n"] == 1:
                return real_save(**kwargs)
            raise RuntimeError("boom")

        with mock.patch(
            "core.drf_resource.resource.strategies.save_strategy_v2",
            side_effect=save_side_effect,
        ):
            loader.run()

        # 走到了第 2 次 save 并触发失败
        assert call_state["n"] == 2
        # 第 2 条失败 -> 整个 v1 事务回滚，第 1 条已创建的策略也被回滚
        assert StrategyModel.objects.all().count() == 0
        # 失败版本不登记接入记录
        assert DefaultStrategyBizAccessModel.objects.all().count() == 0
        # 不写 CACHE，保证同进程下一次可干净重试
        assert bk_biz_id not in OsDefaultAlarmStrategyLoader.CACHE

    def test_load_strategies__multi_tenant_os_restart_and_proc_port(self):
        """多租户主机重启/进程端口走时序链路（非 custom event）。

        - 主机重启 system.env.uptime：套 OsRestart 检测算法，保留真实时序 metric_id（非 bk_monitor.os_restart）；
        - 进程端口 process.port.alive：降级版普通 Threshold(alive < 1)，不套 ProcPort（多租户无相关维度）。
        """
        import importlib
        from unittest import mock

        from django.test import override_settings

        from monitor_web.strategies.default_settings.os import v3 as os_v3

        bk_biz_id = 2

        def _ts_metric(result_table_id, metric_field, metric_field_name, unit):
            m = mock.Mock()
            m.data_source_label = "bk_monitor"
            m.data_type_label = "time_series"
            m.result_table_id = result_table_id
            m.metric_field = metric_field
            m.metric_field_name = metric_field_name
            m.extend_fields = {}
            m.default_condition = []
            m.default_dimensions = []
            m.collect_interval = 1
            m.unit = unit
            return m

        uptime_metric = _ts_metric("system.env", "uptime", "系统启动时间", "s")
        alive_metric = _ts_metric("process.port", "alive", "端口存活", "none")

        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        captured = []

        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(os_v3)
            os_restart_cfg = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "uptime")
            proc_port_cfg = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "alive")
            with (
                mock.patch(
                    "monitor_web.strategies.loader.os_loader.MetricListCache.objects.filter",
                    # 多租户 3 次查询：related_id=system(含 system.env) / custom event / process.port
                    side_effect=[[uptime_metric], [], [alive_metric]],
                ),
                mock.patch(
                    "monitor_web.strategies.loader.os_loader.resource.strategies.save_strategy_v2",
                    side_effect=lambda **kwargs: captured.append(kwargs),
                ),
                mock.patch.object(OsDefaultAlarmStrategyLoader, "get_notice_group", return_value=[1]),
            ):
                result = loader.load_strategies([os_restart_cfg, proc_port_cfg])

        importlib.reload(os_v3)

        assert len(result) == 2
        by_rt = {c["items"][0]["query_configs"][0]["result_table_id"]: c for c in captured}

        # 主机重启：OsRestart 检测算法 + 真实时序 metric_id（未重定向到 bk_monitor.os_restart）
        os_qc = by_rt["system.env"]["items"][0]["query_configs"][0]
        assert os_qc["metric_field"] == "uptime"
        assert os_qc["metric_id"] == "bk_monitor.system.env.uptime"
        assert os_qc["agg_method"] == "MAX"
        assert os_qc["data_type_label"] == "time_series"
        assert by_rt["system.env"]["items"][0]["algorithms"][0]["type"] == "OsRestart"

        # 进程端口：降级版 Threshold(alive < 1)，未套 ProcPort
        pp_qc = by_rt["process.port"]["items"][0]["query_configs"][0]
        assert pp_qc["metric_field"] == "alive"
        assert pp_qc["agg_method"] == "MAX"
        pp_algo = by_rt["process.port"]["items"][0]["algorithms"][0]
        assert pp_algo["type"] == "Threshold"
        assert pp_algo["config"] == [[{"threshold": 1, "method": "lt"}]]
