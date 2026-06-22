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
                    # 多租户 3 次查询：related_id=system 时序 / bk_monitor 源事件 / custom event
                    side_effect=[[], [], [metric]],
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
        # 多租户 custom event 查询带 bk_biz_id 过滤（第 3 次 filter 为 custom event 查询）
        custom_call = filter_mock.call_args_list[2]
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

    def test_run__notice_cache_cleared_on_version_rollback(self):
        """版本 atomic 回滚后必须清空 notice_group_cache。

        notice_group_cache 是 loader 实例级、跨版本循环存活；按版本 atomic 回滚会把该版本内新建的通知组
        DB 行一并回滚，但 Python 缓存仍留着其 id。若不清缓存，同一 run() 的后续版本会复用这个已失效的组
        id，建出的策略 notice.user_groups 静默指向不存在的组、告警发不出。
        """
        from unittest import mock

        bk_biz_id = 2
        OsDefaultAlarmStrategyLoader.CACHE = set()
        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)

        # 模拟某版本 load_strategies 先创建并缓存了通知组，随后抛错（触发 atomic 回滚）
        def _cache_then_boom(strategies):
            loader.notice_group_cache["business"] = 999
            raise RuntimeError("boom")

        with mock.patch.object(loader, "load_strategies", side_effect=_cache_then_boom):
            loader.run()

        # 回滚后缓存被清空（否则后续版本会复用失效 id 999）；该业务不写 CACHE，可干净重试
        assert loader.notice_group_cache == {}
        assert bk_biz_id not in OsDefaultAlarmStrategyLoader.CACHE

    def test_load_strategies__multi_tenant_builtin_proc_port_and_os_restart(self):
        """多租户主机重启/进程端口：策略由 v3（多租户专用、bk_monitor 源伪事件）声明，
        BaseAlarmMetricCacheManager 内置目录项，os_loader 经 EVENT_QUERY_CONFIG_MAP 重定向到底层
        时序表 + ProcPort/OsRestart 算法，与单租户一致。

        - 主机重启 os_restart -> 重定向 system.env.uptime + OsRestart 算法，metric_id 保留 bk_monitor.os_restart；
        - 进程端口 proc_port -> 重定向 system.proc_port.proc_exists（CMDB 内置进程采集，富维度）+ ProcPort 算法。
        关键：策略配置取自真实多租户导入态的 os.v3（reload 后），而非单租户态的 v1——后者多租户不声明这两条。
        """
        import importlib
        from unittest import mock

        from django.test import override_settings

        from monitor_web.strategies.default_settings.os import v3 as os_v3

        bk_biz_id = 2

        def _event_metric(metric_field, metric_field_name):
            m = mock.Mock()
            m.data_source_label = "bk_monitor"
            m.data_type_label = "event"
            # BaseAlarmMetricCacheManager 内置项 result_table_id 为 system.event；get_metric_id 对
            # bk_monitor event 仅按 metric_field 归一（忽略 result_table_id）。
            m.result_table_id = "system.event"
            m.metric_field = metric_field
            m.metric_field_name = metric_field_name
            m.extend_fields = {}
            m.default_condition = []
            m.default_dimensions = []
            m.collect_interval = 1
            m.unit = ""
            return m

        os_restart_metric = _event_metric("os_restart", "主机重启")
        proc_port_metric = _event_metric("proc_port", "进程端口")

        loader = OsDefaultAlarmStrategyLoader(bk_biz_id)
        captured = []

        try:
            with override_settings(ENABLE_MULTI_TENANT_MODE=True):
                importlib.reload(os_v3)
                # 真实多租户导入态下，v3 才声明 os_restart/proc_port（v1 在多租户不声明）
                os_restart_cfg = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "os_restart")
                proc_port_cfg = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "proc_port")
                with (
                    mock.patch(
                        "monitor_web.strategies.loader.os_loader.MetricListCache.objects.filter",
                        # 多租户 3 次查询：related_id=system 时序 / bk_monitor 源事件 / custom event
                        # 内置 proc_port/os_restart 由第 2 次（bk_monitor event）命中；custom 返回空
                        side_effect=[[], [os_restart_metric, proc_port_metric], []],
                    ),
                    mock.patch(
                        "monitor_web.strategies.loader.os_loader.resource.strategies.save_strategy_v2",
                        side_effect=lambda **kwargs: captured.append(kwargs),
                    ),
                    mock.patch.object(OsDefaultAlarmStrategyLoader, "get_notice_group", return_value=[1]),
                ):
                    result = loader.load_strategies([os_restart_cfg, proc_port_cfg])
        finally:
            importlib.reload(os_v3)

        assert len(result) == 2
        # EVENT_QUERY_CONFIG_MAP 重定向后 query_config 的 metric_field：os_restart->uptime / proc_port->proc_exists
        by_field = {c["items"][0]["query_configs"][0]["metric_field"]: c for c in captured}

        # 主机重启：重定向到 system.env.uptime + OsRestart 算法，metric_id 保留 bk_monitor.os_restart
        # （alarm_backends 据此补 "a <= 3600" 表达式）
        os_qc = by_field["uptime"]["items"][0]["query_configs"][0]
        assert os_qc["result_table_id"] == "system.env"
        assert os_qc["metric_id"] == "bk_monitor.os_restart"
        assert os_qc["data_type_label"] == "time_series"
        assert by_field["uptime"]["items"][0]["algorithms"][0]["type"] == "OsRestart"

        # 进程端口：重定向到 CMDB 内置进程采集 system.proc_port.proc_exists + ProcPort 算法，富维度齐全
        pp_qc = by_field["proc_exists"]["items"][0]["query_configs"][0]
        assert pp_qc["result_table_id"] == "system.proc_port"
        assert pp_qc["metric_id"] == "bk_monitor.proc_port"
        assert pp_qc["data_type_label"] == "time_series"
        assert "nonlisten" in pp_qc["agg_dimension"]
        assert "not_accurate_listen" in pp_qc["agg_dimension"]
        assert by_field["proc_exists"]["items"][0]["algorithms"][0]["type"] == "ProcPort"
