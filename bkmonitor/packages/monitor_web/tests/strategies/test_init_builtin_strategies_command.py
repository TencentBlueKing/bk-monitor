"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import override_settings

pytestmark = pytest.mark.django_db

CMD = "init_builtin_strategies"


def _common_patches(run_build_in, *, list_tenant=None, list_spaces=None, derive_tenant=None):
    """命令内部为函数体内 import（from X import Y），patch 到各自源模块即可在调用时生效。"""
    patches = [
        mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in),
        mock.patch("bkmonitor.utils.tenant.set_local_tenant_id", mock.Mock()),
        mock.patch("bkmonitor.utils.user.set_local_username", mock.Mock()),
        mock.patch("bkmonitor.utils.user.get_admin_username", mock.Mock(return_value="admin")),
    ]
    if list_tenant is not None:
        patches.append(mock.patch("core.drf_resource.api.bk_login.list_tenant", mock.Mock(return_value=list_tenant)))
    if list_spaces is not None:
        patches.append(mock.patch("bkm_space.api.SpaceApi.list_spaces", mock.Mock(side_effect=list_spaces)))
    if derive_tenant is not None:
        patches.append(
            mock.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", mock.Mock(side_effect=derive_tenant))
        )
    return patches


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_all_tenants_all_biz_calls_run_build_in_per_mode():
    """不传参：遍历所有租户的全部业务，host/k8s 各调一次 run_build_in，过滤掉非正业务(<=0)。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))

    def list_spaces(bk_tenant_id):
        return {
            "t1": [SimpleNamespace(bk_biz_id=2), SimpleNamespace(bk_biz_id=0), SimpleNamespace(bk_biz_id=-3)],
            "t2": [SimpleNamespace(bk_biz_id=20)],
        }[bk_tenant_id]

    with ExitStack() as stack:
        for p in _common_patches(run_build_in, list_tenant=[{"id": "t1"}, {"id": "t2"}], list_spaces=list_spaces):
            stack.enter_context(p)
        call_command(CMD)

    # 只处理正业务 2/20；负数与 0 业务被过滤；每业务 host+k8s 各一次
    assert set(calls) == {(2, "host"), (2, "k8s"), (20, "host"), (20, "k8s")}


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_explicit_biz_ids_derive_tenant_and_respect_modes():
    """显式业务列表：按业务推导租户(不跨租户重复)，--modes 控制加载模式。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))

    with ExitStack() as stack:
        for p in _common_patches(run_build_in, derive_tenant=lambda biz: f"tenant_of_{biz}"):
            stack.enter_context(p)
        call_command(CMD, bk_biz_ids="2,20", modes="host")

    assert set(calls) == {(2, "host"), (20, "host")}


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_dry_run_does_not_call_run_build_in():
    """dry-run：只打印不加载。"""
    run_build_in = mock.Mock()
    with ExitStack() as stack:
        for p in _common_patches(
            run_build_in, list_tenant=[{"id": "t1"}], list_spaces=lambda bk_tenant_id: [SimpleNamespace(bk_biz_id=2)]
        ):
            stack.enter_context(p)
        call_command(CMD, dry_run=True)
    run_build_in.assert_not_called()


@override_settings(ENABLE_DEFAULT_STRATEGY=False)
def test_disabled_default_strategy_skips():
    """ENABLE_DEFAULT_STRATEGY=False 时直接跳过，不触碰任何加载。"""
    run_build_in = mock.Mock()
    with mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in):
        call_command(CMD)
    run_build_in.assert_not_called()


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_bad_tenant_skipped_others_continue():
    """单个租户取管理员/设置上下文失败 -> 跳过该租户、继续其余（不漏覆盖不被单点失败拖垮）。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))

    def get_admin(bk_tenant_id):
        if bk_tenant_id == "t_bad":
            raise ValueError("no admin for tenant")
        return "admin"

    def list_spaces(bk_tenant_id):
        return {"t_bad": [SimpleNamespace(bk_biz_id=2)], "t_ok": [SimpleNamespace(bk_biz_id=20)]}[bk_tenant_id]

    with ExitStack() as stack:
        stack.enter_context(mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in))
        stack.enter_context(mock.patch("bkmonitor.utils.tenant.set_local_tenant_id", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.set_local_username", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.get_admin_username", mock.Mock(side_effect=get_admin)))
        stack.enter_context(
            mock.patch(
                "core.drf_resource.api.bk_login.list_tenant", mock.Mock(return_value=[{"id": "t_bad"}, {"id": "t_ok"}])
            )
        )
        stack.enter_context(mock.patch("bkm_space.api.SpaceApi.list_spaces", mock.Mock(side_effect=list_spaces)))
        call_command(CMD)

    # t_bad 取管理员失败被跳过（biz 2 不触发）；t_ok 正常处理（biz 20 host+k8s）
    assert set(calls) == {(20, "host"), (20, "k8s")}


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_bk_tenant_id_narrows_without_listing_all_tenants():
    """--bk-tenant-id：只处理该租户，不调用 list_tenant 枚举全部租户。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))
    list_tenant = mock.Mock(return_value=[{"id": "should-not-be-used"}])

    with ExitStack() as stack:
        stack.enter_context(mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in))
        stack.enter_context(mock.patch("bkmonitor.utils.tenant.set_local_tenant_id", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.set_local_username", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.get_admin_username", mock.Mock(return_value="admin")))
        stack.enter_context(mock.patch("core.drf_resource.api.bk_login.list_tenant", list_tenant))
        stack.enter_context(
            mock.patch("bkm_space.api.SpaceApi.list_spaces", mock.Mock(return_value=[SimpleNamespace(bk_biz_id=7)]))
        )
        call_command(CMD, bk_tenant_id="only_t", modes="host")

    assert set(calls) == {(7, "host")}
    list_tenant.assert_not_called()


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_explicit_biz_filtered_by_bk_tenant_id_not_overridden():
    """--bk-tenant-id 对显式业务作过滤、不覆盖：不属于该租户的业务被跳过（防跨租户写）。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))
    derive = {2: "tA", 20: "tB"}

    with ExitStack() as stack:
        for p in _common_patches(run_build_in, derive_tenant=lambda biz: derive[biz]):
            stack.enter_context(p)
        call_command(CMD, bk_biz_ids="2,20", bk_tenant_id="tA", modes="host")

    # 只有真正属于 tA 的 biz 2 被处理；biz 20(tB) 被过滤掉，不会挂到 tA 上下文里建策略
    assert set(calls) == {(2, "host")}


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_tenant_list_spaces_failure_skipped_others_continue():
    """全量枚举时单租户 list_spaces 失败 -> 跳过该租户、继续其余（枚举阶段也容错）。"""
    calls = []
    run_build_in = mock.Mock(side_effect=lambda biz, mode="host": calls.append((biz, mode)))

    def list_spaces(bk_tenant_id):
        if bk_tenant_id == "t_bad":
            raise RuntimeError("list_spaces boom")
        return [SimpleNamespace(bk_biz_id=20)]

    with ExitStack() as stack:
        stack.enter_context(mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in))
        stack.enter_context(mock.patch("bkmonitor.utils.tenant.set_local_tenant_id", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.set_local_username", mock.Mock()))
        stack.enter_context(mock.patch("bkmonitor.utils.user.get_admin_username", mock.Mock(return_value="admin")))
        stack.enter_context(
            mock.patch(
                "core.drf_resource.api.bk_login.list_tenant", mock.Mock(return_value=[{"id": "t_bad"}, {"id": "t_ok"}])
            )
        )
        stack.enter_context(mock.patch("bkm_space.api.SpaceApi.list_spaces", mock.Mock(side_effect=list_spaces)))
        call_command(CMD, modes="host")

    # t_bad 枚举失败被跳过；t_ok 的 biz 20 正常处理
    assert set(calls) == {(20, "host")}


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_invalid_modes_rejected():
    """--modes 含非法值直接报错、不加载（避免 typo 静默 no-op）。"""
    run_build_in = mock.Mock()
    with mock.patch("monitor_web.strategies.built_in.run_build_in", run_build_in):
        call_command(CMD, modes="host,hots")
    run_build_in.assert_not_called()


# ---- 前置清障（--rename-legacy-os-strategies）----


def _make_strategy(bk_biz_id, name, metric_id, data_type_label, result_table_id, scenario="os"):
    """造一条策略 + 其查询配置，用于前置清障识别测试。"""
    from bkmonitor.models import QueryConfigModel, StrategyModel

    strategy = StrategyModel.objects.create(bk_biz_id=bk_biz_id, name=name, scenario=scenario, type="monitor")
    QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=strategy.id,
        alias="a",
        data_source_label="bk_monitor",
        data_type_label=data_type_label,
        metric_id=metric_id,
        config={"result_table_id": result_table_id},
    )
    return strategy


def _rename_patches():
    """前置清障路径只依赖 ORM + 租户/管理员上下文；biz 为造的测试号，需打桩租户解析。"""
    return [
        mock.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", mock.Mock(return_value="t1")),
        mock.patch("bkmonitor.utils.tenant.set_local_tenant_id", mock.Mock()),
        mock.patch("bkmonitor.utils.user.set_local_username", mock.Mock()),
        mock.patch("bkmonitor.utils.user.get_admin_username", mock.Mock(return_value="admin")),
    ]


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_rename_legacy_only_canonical_named_dirty_v1_and_idempotent():
    """前置清障：只改"脏 v1 形态(bk_monitor/event/system.event) + 名恰为内置 canonical"的 7 类系统事件
    （4 GSE + os_restart + proc_port + ping-gse，按 plan D2/D3 全含）；
    用户改过名的脏 v1、以及新建版本(time_series 重定向形态)都不动；且幂等。"""
    from bkmonitor.models import StrategyModel

    biz = 990001
    # A：脏 v1 Agent心跳丢失，占用 canonical 名 -> 应改名（GSE 事件在 MT 悬空静默、需腾名供 v2 补建）
    a = _make_strategy(biz, "Agent心跳丢失", "bk_monitor.agent-gse", "event", "system.event")
    # B：脏 v1 os_restart 但用户已改名 -> 名非 canonical，不动
    b = _make_strategy(biz, "标准化-主机重启", "bk_monitor.os_restart", "event", "system.event")
    # C：新建 v3 os_restart（重定向后 time_series/system.env），名为 canonical -> 不是脏 v1 形态，不动
    c = _make_strategy(biz, "主机重启", "bk_monitor.os_restart", "time_series", "system.env")
    # D：脏 v1 PING不可达告警(bk_monitor/event/system.event) -> 应改名（腾名供 v4 补建）
    d = _make_strategy(biz, "PING不可达告警", "bk_monitor.ping-gse", "event", "system.event")
    # E：脏 v1 主机重启(bk_monitor/event/system.event)，名为 canonical -> 应改名（腾名供 v3，D2/D3）
    e = _make_strategy(biz, "主机重启", "bk_monitor.os_restart", "event", "system.event")

    with ExitStack() as stack:
        for p in _rename_patches():
            stack.enter_context(p)
        call_command(CMD, bk_biz_ids=str(biz), rename_legacy_os_strategies=True)

        assert StrategyModel.objects.get(id=a.id).name == "Agent心跳丢失 [v1-已失效]"
        assert StrategyModel.objects.get(id=b.id).name == "标准化-主机重启"  # 未动（用户改名，名非 canonical）
        assert StrategyModel.objects.get(id=c.id).name == "主机重启"  # 新版 time_series 形态，未动
        assert StrategyModel.objects.get(id=d.id).name == "PING不可达告警 [v1-已失效]"  # 应改名（腾名供 v4）
        assert StrategyModel.objects.get(id=e.id).name == "主机重启 [v1-已失效]"  # 应改名（腾名供 v3，D2/D3）

        # 幂等：再跑一次，A 已非 canonical 名 -> 不再改、不双后缀
        call_command(CMD, bk_biz_ids=str(biz), rename_legacy_os_strategies=True)
        assert StrategyModel.objects.get(id=a.id).name == "Agent心跳丢失 [v1-已失效]"


@override_settings(ENABLE_DEFAULT_STRATEGY=True)
def test_rename_legacy_dry_run_does_not_write():
    """--rename-legacy-os-strategies --dry-run：只列不改。"""
    from bkmonitor.models import StrategyModel

    biz = 990002
    a = _make_strategy(biz, "OOM异常告警", "bk_monitor.oom-gse", "event", "system.event")

    with ExitStack() as stack:
        for p in _rename_patches():
            stack.enter_context(p)
        call_command(CMD, bk_biz_ids=str(biz), rename_legacy_os_strategies=True, dry_run=True)

    assert StrategyModel.objects.get(id=a.id).name == "OOM异常告警"  # dry-run 未改
