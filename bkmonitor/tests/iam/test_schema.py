"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.permission import Permission
from bkmonitor.iam.action import ActionEnum as Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles


class TestSchemaDefinitions:
    """验证 schema 定义的正确性。"""

    def test_action_count(self):
        """所有 53 个 action 都已定义。"""
        actions = [v for v in vars(Actions).values() if hasattr(v, "id")]
        assert len(actions) == 55

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


class TestStaticDefinitions:
    def test_product_uses_authoritative_static_definitions(self):
        from bkmonitor.iam import definitions
        schema = Permission(username="offline", bk_tenant_id="system").schema
        assert schema is definitions
        assert (len(schema.actions), len(schema.resource_types), len(schema.roles)) == (55, 4, 3)
        assert schema.actions["view_business"].name == "业务访问"
        assert schema.roles["space_viewer"].name == "业务查看"
        assert schema.resource_types["apm_application"].ancestor == "space"
        import pytest
        with pytest.raises(TypeError):
            schema.actions["extra"] = schema.actions["view_business"]

    def test_v4_model_uses_the_same_definitions_and_validates_bindings(self):
        from bkmonitor.iam.model_sync import expected_v4_model
        from bkmonitor.iam import definitions
        model = expected_v4_model()
        assert {a.id for a in model.actions} == set(definitions.v4_actions)
        assert {r.id for r in model.roles} == set(definitions.roles)
        assert {r.id for r in model.resource_types} == set(definitions.resource_types)
