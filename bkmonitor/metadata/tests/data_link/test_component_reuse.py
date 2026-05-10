"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from metadata.models.data_link.component_reuse import (
    ALL_DATA_LINK_COMPONENT_KINDS,
    REUSE_ENABLED_STRATEGIES,
    ExistingComponentContext,
    is_reuse_enabled_for,
)
from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.result_table import ResultTableOption


def _pool_with(overrides: dict | None = None):
    """构造一个覆盖所有已知 kind 的 pool，缺省值为空 list。

    注意 key 必须是 **类对象** 而非字符串，所以这里显式用 dict 形参而非 kwargs，
    避免把类名误写成 str。
    """
    pool = {kind: [] for kind in ALL_DATA_LINK_COMPONENT_KINDS}
    if overrides:
        pool.update(overrides)
    return pool


class TestExistingComponentContextClaim:
    """claim / leftover 行为单元测试。

    pool 元素使用 :class:`types.SimpleNamespace` 代替真实 ORM 实例，避免 Django
    模型字段赋值与 pytest-django DB 夹具相互耦合——claim/leftover 的行为逻辑
    只依赖 predicate 与 object identity，不依赖 ORM 语义。
    """

    def test_claim_single_match_removes_from_pool(self):
        target = SimpleNamespace(name="legacy", table_id="t1")
        other = SimpleNamespace(name="other", table_id="t2")
        ctx = ExistingComponentContext(
            data_link_name="dl_demo",
            components_by_kind=_pool_with({ResultTableConfig: [target, other]}),
        )

        claimed = ctx.claim(ResultTableConfig, lambda c: c.table_id == "t1")

        assert claimed is target
        assert ctx.leftover() == {ResultTableConfig: [other]}

    def test_claim_zero_match_returns_none_without_mutation(self):
        a = SimpleNamespace(name="a", table_id="t_a")
        ctx = ExistingComponentContext(
            data_link_name="dl_demo",
            components_by_kind=_pool_with({ResultTableConfig: [a]}),
        )

        claimed = ctx.claim(ResultTableConfig, lambda c: c.table_id == "t_not_exist")

        assert claimed is None
        assert ctx.leftover() == {ResultTableConfig: [a]}

    def test_claim_ambiguous_returns_none_without_mutation(self):
        a = SimpleNamespace(name="a", table_id="t_dup")
        b = SimpleNamespace(name="b", table_id="t_dup")
        ctx = ExistingComponentContext(
            data_link_name="dl_demo",
            components_by_kind=_pool_with({ResultTableConfig: [a, b]}),
        )

        claimed = ctx.claim(ResultTableConfig, lambda c: c.table_id == "t_dup")

        # 歧义情况下不应随机命中，完整保留 pool
        assert claimed is None
        assert ctx.leftover() == {ResultTableConfig: [a, b]}

    def test_claim_unknown_kind_raises(self):
        ctx = ExistingComponentContext(
            data_link_name="dl_demo",
            components_by_kind=_pool_with(),
        )

        class _UnknownKind:
            __name__ = "_UnknownKind"

        with pytest.raises(ValueError):
            ctx.claim(_UnknownKind, lambda c: True)  # type: ignore[arg-type]

    def test_leftover_filters_empty_kinds(self):
        rt = SimpleNamespace(name="a", table_id="t")
        binding = SimpleNamespace(name="b", table_id="t")
        ctx = ExistingComponentContext(
            data_link_name="dl_demo",
            components_by_kind=_pool_with({ResultTableConfig: [rt], VMStorageBindingConfig: [binding]}),
        )

        leftover = ctx.leftover()

        assert leftover == {ResultTableConfig: [rt], VMStorageBindingConfig: [binding]}
        # 未命中的 kind 不应出现在 leftover 结果中
        assert DataBusConfig not in leftover
        assert ConditionalSinkConfig not in leftover


@pytest.mark.django_db(databases="__all__")
class TestExistingComponentContextFromDatalink:
    def test_loads_all_kinds_scoped_by_datalink(self):
        data_link_name = "dl_from_datalink_test"
        namespace = "bkmonitor"
        bk_tenant_id = "system"

        # 属于当前 datalink 的组件
        rt = ResultTableConfig.objects.create(
            name="rt_a",
            namespace=namespace,
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            bk_biz_id=1,
            table_id="t_a",
        )
        binding = VMStorageBindingConfig.objects.create(
            name="bd_a",
            namespace=namespace,
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            bk_biz_id=1,
            table_id="t_a",
            vm_cluster_name="vm-plat",
            bkbase_result_table_name="bkm_t_a",
        )
        # 属于其他 datalink，不应被加载
        ResultTableConfig.objects.create(
            name="rt_unrelated",
            namespace=namespace,
            bk_tenant_id=bk_tenant_id,
            data_link_name="dl_other",
            bk_biz_id=1,
            table_id="t_other",
        )

        fake_datalink = SimpleNamespace(
            data_link_name=data_link_name,
            namespace=namespace,
            bk_tenant_id=bk_tenant_id,
        )

        ctx = ExistingComponentContext.from_datalink(fake_datalink)  # type: ignore[arg-type]

        leftover = ctx.leftover()
        assert set(leftover.keys()) == {ResultTableConfig, VMStorageBindingConfig}
        assert [c.pk for c in leftover[ResultTableConfig]] == [rt.pk]
        assert [c.pk for c in leftover[VMStorageBindingConfig]] == [binding.pk]

        # 所有已注册 kind 都应完成过一次查询（即便为空），未注册的 kind 不会出现
        for kind in ALL_DATA_LINK_COMPONENT_KINDS:
            assert kind in ctx._components_by_kind
        for kind in (
            ConditionalSinkConfig,
            DataBusConfig,
            DorisStorageBindingConfig,
            ESStorageBindingConfig,
        ):
            assert ctx._components_by_kind[kind] == []


class TestIsReuseEnabledFor:
    """:func:`is_reuse_enabled_for` 的灰度 ∩ 白名单闸门语义。

    关键回归：settings 里误配"未接入"的 strategy 时，必须返回 False 并输出 warning，
    而不是误判为 True 让 compose 分支收到它未声明的 ``existing_context`` 关键字。
    """

    def test_returns_true_when_both_settings_and_allowlist_match(self, settings, caplog):
        assert REUSE_ENABLED_STRATEGIES, "REUSE_ENABLED_STRATEGIES 不应为空，否则测试前提不成立"
        sample = next(iter(REUSE_ENABLED_STRATEGIES))
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = {sample}

        with caplog.at_level("WARNING", logger="metadata"):
            assert is_reuse_enabled_for(sample) is True
        assert caplog.records == []

    def test_returns_false_when_not_in_settings(self, settings):
        sample = next(iter(REUSE_ENABLED_STRATEGIES))
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
        assert is_reuse_enabled_for(sample) is False

    def test_returns_false_and_warns_when_strategy_not_implemented(self, settings, caplog):
        """settings 里配了"尚未接入"的 strategy -> 回退 + warning。"""
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = {"__not_implemented_strategy__"}

        with caplog.at_level("WARNING", logger="metadata"):
            assert is_reuse_enabled_for("__not_implemented_strategy__") is False

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings, "应输出一条提示'配了灰度但代码未接入'的 warning"
        assert "not been migrated yet" in warnings[0].getMessage()

    def test_returns_false_when_setting_missing(self, settings):
        """当 settings 完全没声明该开关时，也应安全回退 False。"""
        if hasattr(settings, "DATA_LINK_COMPONENT_REUSE_STRATEGIES"):
            del settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES
        sample = next(iter(REUSE_ENABLED_STRATEGIES))
        assert is_reuse_enabled_for(sample) is False

    @pytest.mark.django_db(databases="__all__")
    def test_returns_true_when_result_table_option_enabled(self, settings):
        """RT option=true 时，即使 strategy 灰度未开，也可以单表触发复用。"""
        sample = next(iter(REUSE_ENABLED_STRATEGIES))
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
        ResultTableOption.create_option(
            table_id="1001_demo.__default__",
            name=ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE,
            value=True,
            creator="pytest",
            bk_tenant_id="system",
        )

        assert is_reuse_enabled_for(sample, table_id="1001_demo.__default__", bk_tenant_id="system") is True

    @pytest.mark.django_db(databases="__all__")
    def test_returns_false_when_result_table_option_missing_or_false(self, settings):
        """单表开关不存在或不为 True 时，不影响原有默认关闭语义。"""
        sample = next(iter(REUSE_ENABLED_STRATEGIES))
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
        ResultTableOption.create_option(
            table_id="1001_demo.__default__",
            name=ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE,
            value=False,
            creator="pytest",
            bk_tenant_id="system",
        )

        assert is_reuse_enabled_for(sample, table_id="1001_missing.__default__", bk_tenant_id="system") is False
        assert is_reuse_enabled_for(sample, table_id="1001_demo.__default__", bk_tenant_id="system") is False
        assert is_reuse_enabled_for(sample, table_id=None, bk_tenant_id="system") is False

    @pytest.mark.django_db(databases="__all__")
    def test_result_table_option_cannot_enable_unimplemented_strategy(self, settings, caplog):
        """RT option 只能打开已接入复用的 strategy，不能绕过代码白名单。"""
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
        ResultTableOption.create_option(
            table_id="1001_demo.__default__",
            name=ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE,
            value=True,
            creator="pytest",
            bk_tenant_id="system",
        )

        with caplog.at_level("WARNING", logger="metadata"):
            assert (
                is_reuse_enabled_for(
                    "__not_implemented_strategy__", table_id="1001_demo.__default__", bk_tenant_id="system"
                )
                is False
            )

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings
        assert "not been migrated yet" in warnings[0].getMessage()
