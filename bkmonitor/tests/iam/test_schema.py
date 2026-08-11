"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles


class TestSchemaDefinitions:
    """验证 schema 定义的正确性。"""

    def test_action_count(self):
        """所有 53 个 action 都已定义。"""
        actions = [v for v in vars(Actions).values() if hasattr(v, "id")]
        assert len(actions) == 53

    def test_action_ids_unique(self):
        """Action ID 没有重复。"""
        ids = [v.id for v in vars(Actions).values() if hasattr(v, "id")]
        assert len(ids) == len(set(ids))

    def test_every_action_has_resource_type(self):
        """每个 action 的 resource_type 字段不为 None（空字符串表示无资源类型）。"""
        for v in vars(Actions).values():
            if hasattr(v, "resource_type"):
                assert v.resource_type is not None, f"{v.id} has None resource_type"

    def test_resource_type_count(self):
        assert len([v for v in vars(ResourceTypes).values() if hasattr(v, "id")]) == 4

    def test_resource_type_hierarchy(self):
        """验证祖先链正确。"""
        rts = {v.id: v for v in vars(ResourceTypes).values() if hasattr(v, "id")}
        assert rts["space"].ancestor == ""
        assert rts["apm_application"].ancestor == "space"
        assert rts["grafana_dashboard"].ancestor == "space"
        assert rts["rum_application"].ancestor == "space"

    def test_role_count(self):
        assert len([v for v in vars(Roles).values() if hasattr(v, "id")]) == 3

    def test_role_action_bindings(self):
        """space_admin 应包含最多 action。"""
        assert len(Roles.SPACE_ADMIN.actions) > len(Roles.SPACE_OPERATOR.actions)
        assert len(Roles.SPACE_OPERATOR.actions) > len(Roles.SPACE_VIEWER.actions)


class TestSchemaRegistry:
    """验证 SchemaRegistry 正确加载并 freeze。"""

    def test_registry_loaded(self):
        fw = get_framework()
        schema = fw.schema
        assert len(list(schema.all_actions())) == 53
        assert len(list(schema.all_resource_types())) == 4
        assert len(list(schema.all_roles())) == 3

    def test_action_lookup(self):
        fw = get_framework()
        action = fw.schema.get_action("view_business")
        assert action.name == "业务访问"
        assert action.resource_type == "space"

    def test_role_lookup(self):
        fw = get_framework()
        role = fw.schema.get_role("space_viewer")
        assert role.name == "业务查看"

    def test_resolve_ancestor_types(self):
        fw = get_framework()
        chain = fw.schema.resolve_ancestor_types("apm_application")
        assert chain == ["space"]


class TestProviderBatching:
    """验证 PermissionProvider 基类的分片 + 编解码逻辑。"""

    @staticmethod
    def _make_fake(**kwargs):
        """构造一个"就地实现方言层 + 恒等 codec"的最小 Provider，验证基类分片。"""
        from bkmonitor.iam.iam_engine.provider.base import PermissionProvider
        from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry

        class FakeProvider(PermissionProvider):
            name = "fake"

            def _is_allowed_dialect(self, request):  # pragma: no cover
                return True

            def _batch_by_resource_dialect_page(self, request):
                # 返回 [(dialect_resource_id, allowed), ...]
                return [(rid, True) for rid in request.resource_ids]

            def _batch_by_action_dialect_page(self, request):
                # 返回 [(dialect_action_id, allowed), ...]
                return [(aid, True) for aid in request.action_ids]

            def _get_apply_url_dialect(self, request):  # pragma: no cover
                return ""

            def plan_migration(self, schema, *, scope="full"):  # pragma: no cover
                raise NotImplementedError

            def apply_migration(self, plan, *, dry_run=False, allow_destructive=False):  # pragma: no cover
                raise NotImplementedError

            def health_check(self):  # pragma: no cover
                return {"status": "ok", "provider": self.name}

        # 用一个空 SchemaRegistry（本组测试不涉及 schema 反查）
        schema = SchemaRegistry()
        try:
            schema.freeze()
        except Exception:
            # 若已 freeze / 无需 freeze，忽略
            pass
        p = FakeProvider(schema)
        for k, v in kwargs.items():
            setattr(p, k, v)
        return p

    # ---- batch_by_resource ----

    def test_batch_by_resource_serial(self):
        from bkmonitor.iam.iam_engine.core.types import (
            BatchByResourceRequest,
            ResourceInstance,
            Subject,
        )

        p = self._make_fake(CHUNK_SIZE=3, MAX_WORKERS=1)
        resources = tuple(ResourceInstance(type="space", id=str(i)) for i in range(10))
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="test"),
                action_id="view",
                resources=resources,
            )
        )
        assert len(result.items) == 10
        assert all(item.allowed for item in result.items)
        # 结果保序：resource_id 与请求顺序一致
        assert [item.resource_id for item in result.items] == [str(i) for i in range(10)]

    def test_batch_by_resource_single_chunk(self):
        """不超过 CHUNK_SIZE 时不走并行路径。"""
        from bkmonitor.iam.iam_engine.core.types import (
            BatchByResourceRequest,
            ResourceInstance,
            Subject,
        )

        p = self._make_fake(CHUNK_SIZE=20, MAX_WORKERS=8)
        resources = tuple(ResourceInstance(type="space", id=str(i)) for i in range(3))
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="test"),
                action_id="view",
                resources=resources,
            )
        )
        assert len(result.items) == 3

    def test_batch_by_resource_empty(self):
        from bkmonitor.iam.iam_engine.core.types import (
            BatchByResourceRequest,
            Subject,
        )

        p = self._make_fake()
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="test"),
                action_id="view",
                resources=(),
            )
        )
        assert len(result.items) == 0

    def test_batch_by_resource_parallel(self):
        """MAX_WORKERS > 1 且分片 > 1 时走并行路径，结果保序。"""
        from bkmonitor.iam.iam_engine.core.types import (
            BatchByResourceRequest,
            ResourceInstance,
            Subject,
        )

        p = self._make_fake(CHUNK_SIZE=3, MAX_WORKERS=4)
        resources = tuple(ResourceInstance(type="space", id=str(i)) for i in range(9))
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="test"),
                action_id="view",
                resources=resources,
            )
        )
        assert len(result.items) == 9
        assert all(item.allowed for item in result.items)
        assert [item.resource_id for item in result.items] == [str(i) for i in range(9)]

    # ---- batch_by_action ----

    def test_batch_by_action_serial(self):
        from bkmonitor.iam.iam_engine.core.types import BatchByActionRequest, Subject

        p = self._make_fake(CHUNK_SIZE=3, MAX_WORKERS=1)
        action_ids = [f"action_{i}" for i in range(10)]
        result = p.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id="test"),
                action_ids=tuple(action_ids),
            )
        )
        assert len(result.items) == 10
        assert all(item.allowed for item in result.items)

    def test_batch_by_action_empty(self):
        from bkmonitor.iam.iam_engine.core.types import BatchByActionRequest, Subject

        p = self._make_fake()
        result = p.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id="test"),
                action_ids=(),
            )
        )
        assert len(result.items) == 0

    def test_batch_by_action_parallel(self):
        from bkmonitor.iam.iam_engine.core.types import BatchByActionRequest, Subject

        p = self._make_fake(CHUNK_SIZE=3, MAX_WORKERS=4)
        action_ids = [f"action_{i}" for i in range(9)]
        result = p.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id="test"),
                action_ids=tuple(action_ids),
            )
        )
        assert len(result.items) == 9
        assert all(item.allowed for item in result.items)


class TestProviderVisibility:
    """验证 schema.visibility.is_visible_to 的 4 种分支。"""

    @staticmethod
    def _entity(extensions=None):
        """构造一个最小的持有 extensions 的 schema 实体（用 ActionDef 代表即可）。"""
        from bkmonitor.iam.iam_engine.schema.definitions import ActionDef

        return ActionDef(id="a", name="A", extensions=extensions or {})

    def test_no_extensions_visible_to_all(self):
        """默认（不设置任何 extensions）→ 对所有 provider 可见（向后兼容）。"""
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        entity = self._entity()
        assert is_visible_to(entity, "v4") is True
        assert is_visible_to(entity, "v3") is True
        assert is_visible_to(entity, "anything") is True

    def test_only_providers_whitelist(self):
        """only_providers 白名单：不在名单里的 provider 不可见。"""
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        entity = self._entity({"only_providers": ("v4",)})
        assert is_visible_to(entity, "v4") is True
        assert is_visible_to(entity, "v3") is False

    def test_exclude_providers_blacklist(self):
        """exclude_providers 黑名单：在名单里的 provider 不可见。"""
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        entity = self._entity({"exclude_providers": ("v3",)})
        assert is_visible_to(entity, "v4") is True
        assert is_visible_to(entity, "v3") is False

    def test_both_are_independent(self):
        """同时设置 only + exclude：两者独立判断，任一命中即拒绝。"""
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        entity = self._entity({"only_providers": ("v4", "v3"), "exclude_providers": ("v3",)})
        # v4：在 only 里 + 不在 exclude 里 → 可见
        assert is_visible_to(entity, "v4") is True
        # v3：在 only 里但也在 exclude 里 → 不可见（exclude 命中）
        assert is_visible_to(entity, "v3") is False
        # x：不在 only 里 → 不可见（only 命中）
        assert is_visible_to(entity, "x") is False

    def test_empty_tuples_treated_as_unset(self):
        """空 tuple 视为未设置：不参与过滤。"""
        from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to

        entity = self._entity({"only_providers": (), "exclude_providers": ()})
        assert is_visible_to(entity, "v4") is True
        assert is_visible_to(entity, "v3") is True
