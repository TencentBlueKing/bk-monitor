"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# MonitorV3Codec 单元测试
#
# 覆盖：
#   1. 迁移 action（_v2 后缀）：encode/decode 正确映射
#   2. 新增 action（identity）：恒等返回
#   3. 未知 action：恒等穿透
#   4. is_read_action：type="view" 判断
#   5. resource_type / resource_id / role：全部恒等
# ==============================================================================

from bkmonitor.iam.iam_engine.provider.codec import NameCodec
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.definitions.codec_v3 import MonitorV3Codec


def _build_test_schema() -> SchemaRegistry:
    """构建包含测试数据的冻结 SchemaRegistry（供 plan_migration 等需要 schema 的测试使用）。"""
    schema = SchemaRegistry()
    schema.register_action(
        ActionDef(
            id="view_business",
            name="业务访问",
            resource_type="space",
            extensions={"v3": {"action_id": "view_business_v2", "type": "view", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="manage_synthetic",
            name="拨测管理",
            resource_type="space",
            extensions={"v3": {"action_id": "manage_synthetic_v2", "type": "manage", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="using_dashboard_mcp",
            name="使用仪表盘MCP",
            resource_type="space",
            extensions={"v3": {"action_id": "using_dashboard_mcp", "type": "view", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="manage_incident",
            name="故障管理",
            resource_type="space",
            extensions={"v3": {"action_id": "manage_incident", "type": "manage", "version": 1}},
        )
    )
    schema.register_action(
        ActionDef(
            id="unknown_type_action",
            name="未知类型",
            resource_type="space",
            extensions={"v3": {"action_id": "unknown_type_action", "version": 1}},
        )
    )
    schema.register_resource_type(
        ResourceTypeDef(
            id="space",
            name="空间",
            extensions={"v3": {"system_id": "bk_monitorv3", "selection_mode": "instance"}},
        )
    )
    schema.freeze()
    return schema


# -- 从 _build_test_schema 对应的数据构建 codec 映射表 --

_TEST_ACTION_ID_MAP = {
    "view_business": "view_business_v2",
    "manage_synthetic": "manage_synthetic_v2",
}

_TEST_ACTION_TYPES = {
    "view_business": "view",
    "manage_synthetic": "manage",
    "using_dashboard_mcp": "view",
    "manage_incident": "manage",
}


class TestMonitorV3Codec:
    """MonitorV3Codec：从 action_id_map / action_types dict 构建映射表（无须 schema）。"""

    def setup_method(self):
        self.c: NameCodec = MonitorV3Codec(
            action_id_map=_TEST_ACTION_ID_MAP,
            action_types=_TEST_ACTION_TYPES,
        )

    # ---- 迁移 action 编码 ----

    def test_encode_migrated_action(self):
        """迁移 action（_v2 后缀）：业务 ID → V3 平台 ID。"""
        assert self.c.encode_action("view_business") == "view_business_v2"

    def test_decode_migrated_action(self):
        """迁移 action（_v2 后缀）：V3 平台 ID → 业务 ID。"""
        assert self.c.decode_action("view_business_v2") == "view_business"

    def test_encode_migrated_manage_action(self):
        """迁移的 manage 类型 action。"""
        assert self.c.encode_action("manage_synthetic") == "manage_synthetic_v2"

    def test_decode_migrated_manage_action(self):
        """迁移的 manage 类型 action 解码。"""
        assert self.c.decode_action("manage_synthetic_v2") == "manage_synthetic"

    # ---- 新增 action（identity） ----

    def test_encode_identity_action(self):
        """新增 action：业务 ID 与 V3 平台 ID 相同的，恒等返回。"""
        assert self.c.encode_action("using_dashboard_mcp") == "using_dashboard_mcp"

    def test_decode_identity_action(self):
        """新增 action 解码也恒等。"""
        assert self.c.decode_action("using_dashboard_mcp") == "using_dashboard_mcp"

    def test_encode_identity_manage_action(self):
        """新增 manage action 恒等。"""
        assert self.c.encode_action("manage_incident") == "manage_incident"

    # ---- round-trip ----

    def test_round_trip_migrated(self):
        """迁移 action 的 编码-解码 往返一致性。"""
        biz_ids = ["view_business", "manage_synthetic"]
        for biz_id in biz_ids:
            encoded = self.c.encode_action(biz_id)
            assert self.c.decode_action(encoded) == biz_id

    def test_round_trip_identity(self):
        """新增 action 的 编码-解码 往返一致性。"""
        biz_ids = ["using_dashboard_mcp", "manage_incident"]
        for biz_id in biz_ids:
            encoded = self.c.encode_action(biz_id)
            assert self.c.decode_action(encoded) == biz_id

    # ---- 未知 action 穿透 ----

    def test_encode_unknown_action(self):
        """schema 中不存在的 action：恒等穿透。"""
        assert self.c.encode_action("nonexistent_action") == "nonexistent_action"

    def test_decode_unknown_action(self):
        """schema 中不存在的 action 解码也恒等。"""
        assert self.c.decode_action("nonexistent_action_v2") == "nonexistent_action_v2"

    # ---- is_read_action ----

    def test_is_read_action_true(self):
        """type="view" 的 action。"""
        assert self.c.is_read_action("view_business") is True

    def test_is_read_action_false_for_manage(self):
        """type="manage" 的 action。"""
        assert self.c.is_read_action("manage_synthetic") is False

    def test_is_read_action_identity_view(self):
        """新增的 view action。"""
        assert self.c.is_read_action("using_dashboard_mcp") is True

    def test_is_read_action_unknown_type(self):
        """无 type 的 action 返回 False。"""
        assert self.c.is_read_action("unknown_type_action") is False

    def test_is_read_action_nonexistent(self):
        """不存在的 action 返回 False。"""
        assert self.c.is_read_action("nonexistent") is False

    # ---- resource_type / resource_id / role 恒等 ----

    def test_resource_type_identity(self):
        """V3 资源类型恒等映射。"""
        assert self.c.encode_resource_type("space") == "space"
        assert self.c.decode_resource_type("space") == "space"

    def test_resource_id_identity(self):
        """V3 资源 ID 恒等映射。"""
        assert self.c.encode_resource_id("space", "3") == "3"
        assert self.c.decode_resource_id("space", "3") == "3"

    def test_role_identity(self):
        """V3 角色恒等映射。"""
        assert self.c.encode_role("any_role") == "any_role"
        assert self.c.decode_role("any_role") == "any_role"

    # ---- 空映射表构造 ----

    def test_empty_mappings(self):
        """无映射时所有操作恒等。"""
        c = MonitorV3Codec(action_id_map={}, action_types={})
        assert c.encode_action("view_business") == "view_business"
        assert c.decode_action("view_business_v2") == "view_business_v2"
        assert c.is_read_action("view_business") is False

    # ---- 默认构造（使用模块级 Actions 映射表） ----

    def test_default_constructor(self):
        """无参构造使用从 Actions 类自动提取的映射表。"""
        c = MonitorV3Codec()
        # 至少能正常编解码，具体行为取决于 Actions 类定义
        assert c.encode_action("nonexistent_action") == "nonexistent_action"
        assert c.decode_action("nonexistent_action") == "nonexistent_action"
