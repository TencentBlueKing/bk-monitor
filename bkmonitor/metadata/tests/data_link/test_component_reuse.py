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
    ExistingComponentContext,
)
from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)


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
