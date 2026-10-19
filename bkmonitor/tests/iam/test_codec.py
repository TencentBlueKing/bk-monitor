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
# 运行时 NameCodec 编解码链路的单元测试
#
# 覆盖：
#   1. IdentityCodec 全恒等
#   2. MonitorV4Codec 双射 & 边界（space 加前缀、非 space 恒等、decode 兜底）
# ==============================================================================

from bkmonitor.iam.backends.v4.codec import MonitorV4Codec
from iam_engine.provider.codec import IdentityCodec, NameCodec


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
# MonitorV4Codec
# ==============================================================================


class TestMonitorV4Codec:
    """MonitorV4Codec 只对 space 加 "space|" 前缀。"""

    def setup_method(self):
        self.c: NameCodec = MonitorV4Codec()

    # ---- space ----

    def test_space_encode(self):
        assert self.c.encode_resource_id("space", "3") == "space|3"

    def test_space_encode_negative(self):
        assert self.c.encode_resource_id("space", "-42") == "space|-42"

    def test_space_encode_idempotent(self):
        assert self.c.encode_resource_id("space", "space|3") == "space|3"

    def test_space_decode(self):
        assert self.c.decode_resource_id("space", "space|3") == "3"
        assert self.c.decode_resource_id("space", "space|-42") == "-42"

    def test_space_decode_no_prefix_fallback(self):
        assert self.c.decode_resource_id("space", "3") == "3"

    def test_space_round_trip(self):
        for biz_id in ["3", "-42", "999999", "-1"]:
            assert self.c.decode_resource_id("space", self.c.encode_resource_id("space", biz_id)) == biz_id

    # ---- 非 space 资源类型：恒等 ----

    def test_apm_application_identity(self):
        assert self.c.encode_resource_id("apm_application", "42") == "42"
        assert self.c.decode_resource_id("apm_application", "42") == "42"

    def test_grafana_dashboard_identity(self):
        assert self.c.encode_resource_id("grafana_dashboard", "1|abc-uid") == "1|abc-uid"
        assert self.c.decode_resource_id("grafana_dashboard", "1|abc-uid") == "1|abc-uid"
        assert self.c.encode_resource_id("grafana_dashboard", "folder:1|100") == "folder:1|100"

    def test_rum_application_identity(self):
        assert self.c.encode_resource_id("rum_application", "17") == "17"

    # ---- 其他符号：全恒等 ----

    def test_action_identity(self):
        assert self.c.encode_action("view_business") == "view_business"
        assert self.c.decode_action("view_business") == "view_business"

    def test_resource_type_identity(self):
        assert self.c.encode_resource_type("space") == "space"
        assert self.c.decode_resource_type("space") == "space"

    def test_role_identity(self):
        assert self.c.encode_role("space_admin") == "space_admin"
        assert self.c.decode_role("space_admin") == "space_admin"
