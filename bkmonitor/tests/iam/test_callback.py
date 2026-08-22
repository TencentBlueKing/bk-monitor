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
from bkmonitor.iam.adapters.v4.codec import MonitorV4Codec
from bkmonitor.iam.iam_engine.callback.registry import (
    _fetch_handlers,
    _list_handlers,
    register_fetch_instance_info,
    register_list_instance,
)
from bkmonitor.iam.iam_engine.callback.service import CallbackService
from bkmonitor.iam.iam_engine.provider.codec import IdentityCodec


@pytest.fixture(autouse=True)
def _clear_registry():
    """每个测试前后清理全局 handler 注册表，避免测试间污染。"""
    _list_handlers.clear()
    _fetch_handlers.clear()
    yield
    _list_handlers.clear()
    _fetch_handlers.clear()


class TestCallbackServicesIdentityCodec:
    """使用恒等 codec 验证注册/分发机制本身（不涉及方言）。"""

    def test_register_and_list_instance(self):
        svc = CallbackService(codec=IdentityCodec())

        @register_list_instance("test_type_identity")
        def _fake_list(filter_data, page):
            return {
                "count": 2,
                "results": [
                    {"id": "1", "display_name": "space-1"},
                    {"id": "2", "display_name": "space-2"},
                ],
            }

        @register_fetch_instance_info("test_type_identity")
        def _fake_fetch(ids, requires):
            return [{"id": i, "display_name": f"name-{i}"} for i in ids]

        result = svc.dispatch_list_instance("test_type_identity", {}, {"page": 1, "page_size": 10})
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["id"] == "1"

        result = svc.dispatch_fetch_instance_info("test_type_identity", ["1", "2"], ["display_name"])
        assert len(result) == 2
        assert {r["id"] for r in result} == {"1", "2"}

    def test_unregistered_type(self):
        svc = CallbackService(codec=IdentityCodec())
        assert svc.dispatch_list_instance("unknown_type", {}, {}) == {"count": 0, "results": []}
        assert svc.dispatch_fetch_instance_info("unknown_type", ["1"], []) == []


class TestCallbackServicesWithMonitorV4Codec:
    """使用 MonitorV4Codec 验证 codec 编解码在 dispatch 层的正确性。

    MonitorV4Codec 规则：
      - space: 出参 encode 加 "space|" 前缀；入参 decode 去前缀
      - 其他资源类型: 恒等
    """

    def test_space_list_encodes_id(self):
        svc = CallbackService(codec=MonitorV4Codec())

        @register_list_instance("space")
        def _fake_list(filter_data, page):
            return {
                "count": 2,
                "results": [
                    {"id": "3", "display_name": "biz-3"},
                    {"id": "-42", "display_name": "biz--42"},
                ],
            }

        result = svc.dispatch_list_instance("space", {}, {"page": 1, "page_size": 10})
        assert result["results"][0]["id"] == "space|3"
        assert result["results"][1]["id"] == "space|-42"

    def test_space_fetch_decodes_input_and_encodes_output(self):
        svc = CallbackService(codec=MonitorV4Codec())

        received_ids: list[str] = []

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            received_ids.extend(ids)
            return [{"id": i, "display_name": f"biz-{i}"} for i in ids]

        result = svc.dispatch_fetch_instance_info("space", ["space|3", "space|-42"], [])
        assert received_ids == ["3", "-42"]
        assert [r["id"] for r in result] == ["space|3", "space|-42"]

    def test_space_fetch_tolerates_no_prefix(self):
        svc = CallbackService(codec=MonitorV4Codec())

        received_ids: list[str] = []

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            received_ids.extend(ids)
            return [{"id": i, "display_name": f"biz-{i}"} for i in ids]

        result = svc.dispatch_fetch_instance_info("space", ["3"], [])
        assert received_ids == ["3"]
        assert result[0]["id"] == "space|3"

    def test_non_space_resource_is_identity(self):
        svc = CallbackService(codec=MonitorV4Codec())

        @register_list_instance("apm_application_test")
        def _fake_list_apm(filter_data, page):
            return {"count": 1, "results": [{"id": "42", "display_name": "apm-42"}]}

        @register_fetch_instance_info("grafana_dashboard_test")
        def _fake_fetch_grafana(ids, requires):
            return [{"id": i, "display_name": f"dash-{i}"} for i in ids]

        r1 = svc.dispatch_list_instance("apm_application_test", {}, {})
        assert r1["results"][0]["id"] == "42"

        r2 = svc.dispatch_fetch_instance_info("grafana_dashboard_test", ["1|abc-uid"], [])
        assert r2[0]["id"] == "1|abc-uid"

    def test_list_instance_decodes_parent_id(self):
        svc = CallbackService(codec=MonitorV4Codec())

        received_filter: dict = {}

        @register_list_instance("apm_parent_test")
        def _fake_list(filter_data, page):
            received_filter.update(filter_data)
            return {"count": 0, "results": []}

        svc.dispatch_list_instance(
            "apm_parent_test",
            {"parent": {"type": "space", "id": "space|3"}},
            {},
        )
        assert received_filter["parent"]["id"] == "3"

    def test_different_codec_instances_share_registry(self):
        """同一个 registry 可以被不同 codec 的 CallbackService 使用。"""
        svc_id = CallbackService(codec=IdentityCodec())
        svc_v4 = CallbackService(codec=MonitorV4Codec())

        @register_list_instance("space")
        def _fake_list(filter_data, page):
            return {"count": 1, "results": [{"id": "3", "display_name": "x"}]}

        r1 = svc_id.dispatch_list_instance("space", {}, {})
        assert r1["results"][0]["id"] == "3"  # 恒等

        r2 = svc_v4.dispatch_list_instance("space", {}, {})
        assert r2["results"][0]["id"] == "space|3"  # MonitorV4Codec 加前缀


class TestBkIamPathEncoding:
    """验证 _bk_iam_path_ 的 codec 编解码。"""

    def test_space_single_segment_encoded(self):
        """space 单段路径中的 id 应被 encode。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            return [{"id": "3", "_bk_iam_path_": "/space,3/"}]

        result = svc.dispatch_fetch_instance_info("space", ["space|3"], ["_bk_iam_path_"])
        assert result[0]["id"] == "space|3"
        assert result[0]["_bk_iam_path_"] == "/space,space|3/"

    def test_space_multi_segment_encoded(self):
        """多段路径中，每段的 id 都被 encode。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("apm_application")
        def _fake_fetch(ids, requires):
            return [{"id": "42", "_bk_iam_path_": "/space,3/apm_application,42/"}]

        result = svc.dispatch_fetch_instance_info("apm_application", ["42"], ["_bk_iam_path_"])
        assert result[0]["_bk_iam_path_"] == "/space,space|3/apm_application,42/"

    def test_non_space_path_identity(self):
        """非 space 段落的 id 保持恒等。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("grafana_dashboard")
        def _fake_fetch(ids, requires):
            return [{"id": "1|abc", "_bk_iam_path_": "/space,3/grafana_dashboard,1|abc/"}]

        result = svc.dispatch_fetch_instance_info("grafana_dashboard", ["1|abc"], ["_bk_iam_path_"])
        # space 段 encode，grafana_dashboard 段恒等
        assert result[0]["_bk_iam_path_"] == "/space,space|3/grafana_dashboard,1|abc/"

    def test_no_trailing_slash(self):
        """无尾部斜杠的路径也正确处理。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            return [{"id": "3", "_bk_iam_path_": "/space,3"}]

        result = svc.dispatch_fetch_instance_info("space", ["space|3"], ["_bk_iam_path_"])
        assert result[0]["_bk_iam_path_"] == "/space,space|3"

    def test_no_bk_iam_path_unchanged(self):
        """不带 _bk_iam_path_ 的 item 不应报错，id 正常 encode。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_list_instance("space")
        def _fake_list(filter_data, page):
            return {"count": 1, "results": [{"id": "3", "display_name": "x"}]}

        result = svc.dispatch_list_instance("space", {}, {})
        assert result["results"][0]["id"] == "space|3"
        assert "_bk_iam_path_" not in result["results"][0]

    def test_bk_iam_path_non_string_skipped(self):
        """_bk_iam_path_ 不是字符串时跳过，不抛异常。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            return [{"id": "3", "_bk_iam_path_": None}]

        result = svc.dispatch_fetch_instance_info("space", ["space|3"], [])
        assert result[0]["id"] == "space|3"
        assert result[0]["_bk_iam_path_"] is None

    def test_identity_codec_path_unchanged(self):
        """恒等 codec 下 _bk_iam_path_ 保持不变。"""
        svc = CallbackService(codec=IdentityCodec())

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            return [{"id": "3", "_bk_iam_path_": "/space,3/apm_application,42/"}]

        result = svc.dispatch_fetch_instance_info("space", ["3"], ["_bk_iam_path_"])
        assert result[0]["_bk_iam_path_"] == "/space,3/apm_application,42/"

    def test_path_single_segment_no_comma(self):
        """路径段不含逗号时原样保留（畸形输入防御）。"""
        svc = CallbackService(codec=MonitorV4Codec())

        @register_fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            return [{"id": "3", "_bk_iam_path_": "/top/"}]

        result = svc.dispatch_fetch_instance_info("space", ["space|3"], [])
        assert result[0]["_bk_iam_path_"] == "/top/"


class TestCallbackAuth:
    """验证回调鉴权 token 缓存机制。"""

    def test_token_cache_hit(self, monkeypatch):
        from bkmonitor.iam.iam_v4.callback import auth

        call_count = 0

        class FakeClient:
            def get_auth_token(self):
                nonlocal call_count
                call_count += 1
                return "test-token-123"

        monkeypatch.setattr(auth, "_CACHED_TOKEN", None)
        monkeypatch.setattr(auth, "_CACHED_TOKEN_EXPIRE_AT", 0)
        monkeypatch.setattr(auth, "_get_client", lambda: FakeClient())

        t1 = auth._get_system_token()
        assert t1 == "test-token-123"
        assert call_count == 1

        t2 = auth._get_system_token()
        assert t2 == "test-token-123"
        assert call_count == 1
