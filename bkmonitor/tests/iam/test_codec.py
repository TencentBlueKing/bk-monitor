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
# NameCodec 与 PermissionProvider 基类编解码链路的单元测试
#
# 覆盖：
#   1. IdentityCodec 全恒等
#   2. V4NameCodec 双射 & 边界（space 加前缀、非 space 恒等、decode 兜底）
#   3. PermissionProvider 基类：is_allowed / batch_by_resource / batch_by_action /
#      get_apply_url 出站 encode + 入站 decode 走通
# ==============================================================================

from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.iam_engine.provider.base import PermissionProvider
from bkmonitor.iam.iam_engine.provider.codec import IdentityCodec, NameCodec
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_v4.codec import V4NameCodec


# ==============================================================================
# IdentityCodec
# ==============================================================================


class TestIdentityCodec:
    """默认恒等 codec：所有 encode/decode 都返回原值。"""

    def setup_method(self):
        self.c: NameCodec = IdentityCodec()

    def test_action(self):
        assert self.c.encode_action("view_business") == "view_business"
        assert self.c.decode_action("view_business") == "view_business"

    def test_resource_type(self):
        assert self.c.encode_resource_type("space") == "space"
        assert self.c.decode_resource_type("space") == "space"

    def test_resource_id(self):
        assert self.c.encode_resource_id("space", "3") == "3"
        assert self.c.decode_resource_id("space", "3") == "3"
        assert self.c.encode_resource_id("apm_application", "42") == "42"

    def test_role(self):
        assert self.c.encode_role("space_admin") == "space_admin"
        assert self.c.decode_role("space_admin") == "space_admin"


# ==============================================================================
# V4NameCodec
# ==============================================================================


class TestV4NameCodec:
    """V4NameCodec 只对 space 加 "space|" 前缀。"""

    def setup_method(self):
        self.c: NameCodec = V4NameCodec()

    # ---- space ----

    def test_space_encode(self):
        assert self.c.encode_resource_id("space", "3") == "space|3"

    def test_space_encode_negative(self):
        """非 bkcc 空间（负数 bk_biz_id）也能加前缀，首字符变为字母。"""
        assert self.c.encode_resource_id("space", "-42") == "space|-42"

    def test_space_encode_idempotent(self):
        """已带前缀不应再套一层（幂等，防御性）。"""
        assert self.c.encode_resource_id("space", "space|3") == "space|3"

    def test_space_decode(self):
        assert self.c.decode_resource_id("space", "space|3") == "3"
        assert self.c.decode_resource_id("space", "space|-42") == "-42"

    def test_space_decode_no_prefix_fallback(self):
        """无前缀的历史 ID：视作业务 ID 原样返回。"""
        assert self.c.decode_resource_id("space", "3") == "3"

    def test_space_round_trip(self):
        for biz_id in ["3", "-42", "999999", "-1"]:
            assert self.c.decode_resource_id("space", self.c.encode_resource_id("space", biz_id)) == biz_id

    # ---- 非 space 资源类型：恒等 ----

    def test_apm_application_identity(self):
        assert self.c.encode_resource_id("apm_application", "42") == "42"
        assert self.c.decode_resource_id("apm_application", "42") == "42"

    def test_grafana_dashboard_identity(self):
        # 业务侧已是复合 ID，恒等即可
        assert self.c.encode_resource_id("grafana_dashboard", "1|abc-uid") == "1|abc-uid"
        assert self.c.decode_resource_id("grafana_dashboard", "1|abc-uid") == "1|abc-uid"
        assert self.c.encode_resource_id("grafana_dashboard", "folder:1|100") == "folder:1|100"

    def test_rum_application_identity(self):
        assert self.c.encode_resource_id("rum_application", "17") == "17"

    # ---- 其他符号：全恒等（继承自 IdentityCodec） ----

    def test_action_identity(self):
        assert self.c.encode_action("view_business") == "view_business"
        assert self.c.decode_action("view_business") == "view_business"

    def test_resource_type_identity(self):
        assert self.c.encode_resource_type("space") == "space"
        assert self.c.decode_resource_type("space") == "space"

    def test_role_identity(self):
        assert self.c.encode_role("space_admin") == "space_admin"
        assert self.c.decode_role("space_admin") == "space_admin"


# ==============================================================================
# PermissionProvider 基类的编解码模板方法
#
# 用一个"记录方言层入参、返回可控出参"的假 Provider，验证：
#   - 出站：接口层收到的业务 ID 到达方言层时已是方言 ID
#   - 入站：方言层返回的方言 ID 在接口层拿到时已还原为业务 ID
# ==============================================================================


class _RecordingCodec(IdentityCodec):
    """恒等基础上，把 encode/decode 加上明显的前缀 D:/B:，方便断言。"""

    def encode_action(self, action_id: str) -> str:
        return f"D:{action_id}"

    def decode_action(self, dialect_action_id: str) -> str:
        assert dialect_action_id.startswith("D:")
        return dialect_action_id[2:]

    def encode_resource_type(self, rt_id: str) -> str:
        return f"D:{rt_id}" if rt_id else ""

    def decode_resource_type(self, dialect_rt_id: str) -> str:
        return dialect_rt_id[2:] if dialect_rt_id.startswith("D:") else dialect_rt_id

    def encode_resource_id(self, rt_id: str, business_id: str) -> str:
        return f"D:{business_id}"

    def decode_resource_id(self, rt_id: str, dialect_id: str) -> str:
        assert dialect_id.startswith("D:")
        return dialect_id[2:]


class _RecordingProvider(PermissionProvider):
    """记录方言层收到的入参，用于断言基类是否正确 encode。"""

    name = "recording"
    codec_class = _RecordingCodec

    def __init__(self, schema: SchemaRegistry) -> None:
        super().__init__(schema)
        self.last_is_allowed = None
        self.last_batch_by_resource = None
        self.last_batch_by_action = None
        self.last_apply_url = None

    def _is_allowed_dialect(self, request):
        self.last_is_allowed = request
        return True

    def _batch_by_resource_dialect_page(self, request):
        self.last_batch_by_resource = request
        # 返回每个 dialect_resource_id → True
        return [(rid, True) for rid in request.resource_ids]

    def _batch_by_action_dialect_page(self, request):
        self.last_batch_by_action = request
        return [(aid, True) for aid in request.action_ids]

    def _get_apply_url_dialect(self, request):
        self.last_apply_url = request
        return "https://example.com/apply"

    def plan_migration(self, schema):  # pragma: no cover
        raise NotImplementedError

    def apply_migration(self, plan, *, dry_run=False, allow_destructive=False):  # pragma: no cover
        raise NotImplementedError

    def health_check(self):  # pragma: no cover
        return {"status": "ok", "provider": self.name}


def _fresh_provider() -> _RecordingProvider:
    schema = SchemaRegistry()
    try:
        schema.freeze()
    except Exception:
        pass
    return _RecordingProvider(schema)


class TestPermissionProviderEncoding:
    """验证基类模板方法出站 encode + 入站 decode 的正确性。"""

    def test_is_allowed_encodes_action_and_resource(self):
        p = _fresh_provider()
        p.is_allowed(
            AuthRequest(
                subject=Subject(id="alice"),
                action_id="view_business",
                resource=ResourceInstance(type="space", id="3"),
            )
        )
        req = p.last_is_allowed
        assert req is not None
        assert req.action_id == "D:view_business"
        assert req.resource is not None
        assert req.resource.type == "D:space"
        assert req.resource.id == "D:3"

    def test_is_allowed_without_resource(self):
        p = _fresh_provider()
        p.is_allowed(
            AuthRequest(
                subject=Subject(id="alice"),
                action_id="view_global_setting",
            )
        )
        req = p.last_is_allowed
        assert req is not None
        assert req.action_id == "D:view_global_setting"
        assert req.resource is None

    def test_batch_by_resource_encodes_and_decodes(self):
        p = _fresh_provider()
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="alice"),
                action_id="view_business",
                resources=(
                    ResourceInstance(type="space", id="3"),
                    ResourceInstance(type="space", id="5"),
                ),
            )
        )
        # 方言层收到的是方言 ID
        assert p.last_batch_by_resource is not None
        assert p.last_batch_by_resource.action_id == "D:view_business"
        assert p.last_batch_by_resource.resource_type == "D:space"
        assert p.last_batch_by_resource.resource_ids == ("D:3", "D:5")
        # 上层拿到的是业务 ID
        ids = [item.resource_id for item in result.items]
        assert ids == ["3", "5"]
        assert all(item.action_id == "view_business" for item in result.items)
        assert all(item.resource_type == "space" for item in result.items)

    def test_batch_by_action_encodes_and_decodes(self):
        p = _fresh_provider()
        result = p.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id="alice"),
                action_ids=("view_business", "manage_rule"),
                resource=ResourceInstance(type="space", id="3"),
            )
        )
        # 方言层收到的是方言 ID
        assert p.last_batch_by_action is not None
        assert p.last_batch_by_action.action_ids == ("D:view_business", "D:manage_rule")
        assert p.last_batch_by_action.resource is not None
        assert p.last_batch_by_action.resource.type == "D:space"
        assert p.last_batch_by_action.resource.id == "D:3"
        # 上层拿到的是业务 ID
        aids = [item.action_id for item in result.items]
        assert aids == ["view_business", "manage_rule"]
        assert all(item.resource_id == "3" for item in result.items)

    def test_get_apply_url_encodes(self):
        p = _fresh_provider()
        p.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id="alice"),
                action_ids=("view_business",),
                resources=(ResourceInstance(type="space", id="3"),),
            )
        )
        req = p.last_apply_url
        assert req is not None
        assert req.action_ids == ("D:view_business",)
        assert len(req.resources) == 1
        r = req.resources[0]
        assert r.type == "D:space"
        assert r.id == "D:3"

    def test_batch_by_resource_empty(self):
        """空 resources 直接返回空 result，不触发方言层。"""
        p = _fresh_provider()
        result = p.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id="alice"),
                action_id="view_business",
                resources=(),
            )
        )
        assert len(result.items) == 0
        assert p.last_batch_by_resource is None
