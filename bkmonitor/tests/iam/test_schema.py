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
from bkmonitor.iam.schema.actions import Actions
from bkmonitor.iam.schema.resource_types import ResourceTypes
from bkmonitor.iam.schema.roles import Roles


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


class TestBatchMixin:
    """验证 BatchMixin 分片逻辑。"""

    @staticmethod
    def _make_fake(cls=None, **kwargs):
        from bkmonitor.iam.iam_engine.provider.mixins import BatchMixin
        from bkmonitor.iam.iam_engine.core.types import ResourceAuthResult

        base = cls if cls is not None else BatchMixin

        class FakeProvider(base):
            def _batch_by_resource_page(self, subject, action_id, batch):
                return [
                    ResourceAuthResult(
                        action_id=action_id,
                        resource_type="space",
                        resource_id=r.id,
                        allowed=True,
                    )
                    for r in batch
                ]

            def _batch_by_action_page(self, subject, action_ids, resource):
                return [
                    ResourceAuthResult(
                        action_id=aid,
                        resource_type="",
                        resource_id="",
                        allowed=True,
                    )
                    for aid in action_ids
                ]

        p = FakeProvider()
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
        """MAX_WORKERS > 1 且分片 > 1 时走并行路径。"""
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

    # ---- batch_by_action ----

    def test_batch_by_action_serial(self):
        from bkmonitor.iam.iam_engine.core.types import BatchByActionRequest, Subject

        p = self._make_fake(CHUNK_SIZE=3, MAX_WORKERS=1)
        action_ids = [f"action_{i}" for i in range(10)]
        result = p.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id="test"),
                action_ids=action_ids,
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
                action_ids=[],
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
                action_ids=action_ids,
            )
        )
        assert len(result.items) == 9
        assert all(item.allowed for item in result.items)

    def test_chunked_batch_mixin_alias(self):
        """向后兼容别名。"""
        from bkmonitor.iam.iam_engine.provider.mixins import BatchMixin, ChunkedBatchMixin

        assert ChunkedBatchMixin is BatchMixin
