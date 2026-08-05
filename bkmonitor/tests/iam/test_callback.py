"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.iam_engine.provider.codec import IdentityCodec
from bkmonitor.iam.iam_v4.callback.services import CallbackService
from bkmonitor.iam.iam_v4.codec import V4NameCodec


class TestCallbackServicesIdentityCodec:
    """使用恒等 codec 验证注册/分发机制本身（不涉及方言）。"""

    def _fresh_service(self) -> CallbackService:
        return CallbackService(codec=IdentityCodec())

    def test_register_and_list_instance(self):
        svc = self._fresh_service()

        @svc.list_instance("test_type")
        def _fake_list(filter_data, page):
            return {
                "count": 2,
                "results": [
                    {"id": "1", "display_name": "space-1"},
                    {"id": "2", "display_name": "space-2"},
                ],
            }

        @svc.fetch_instance_info("test_type")
        def _fake_fetch(ids, requires):
            return [{"id": i, "display_name": f"name-{i}"} for i in ids]

        result = svc.dispatch_list_instance("test_type", {}, {"page": 1, "page_size": 10})
        assert result["count"] == 2
        assert len(result["results"]) == 2
        # 恒等 codec：id 保持不变
        assert result["results"][0]["id"] == "1"

        result = svc.dispatch_fetch_instance_info("test_type", ["1", "2"], ["display_name"])
        assert len(result) == 2
        assert {r["id"] for r in result} == {"1", "2"}

    def test_unregistered_type(self):
        svc = self._fresh_service()
        assert svc.dispatch_list_instance("unknown_type", {}, {}) == {"count": 0, "results": []}
        assert svc.dispatch_fetch_instance_info("unknown_type", ["1"], []) == []


class TestCallbackServicesWithV4Codec:
    """使用 V4NameCodec 验证 codec 编解码在装饰器里的正确性。

    v4 codec 规则：
      - space         : 出参 encode 加 "space|" 前缀；入参 decode 去前缀
      - 其他资源类型   : 恒等
    """

    def _fresh_service(self) -> CallbackService:
        return CallbackService(codec=V4NameCodec())

    def test_space_list_encodes_id(self):
        """list_instance 返回的 space id 应该被加上 space| 前缀。"""
        svc = self._fresh_service()

        @svc.list_instance("space")
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
        """fetch_instance_info：入参 ids 应被 decode 为业务 ID；出参再 encode 回方言。"""
        svc = self._fresh_service()

        received_ids: list[str] = []

        @svc.fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            received_ids.extend(ids)
            return [{"id": i, "display_name": f"biz-{i}"} for i in ids]

        # 平台传入方言 id
        result = svc.dispatch_fetch_instance_info("space", ["space|3", "space|-42"], [])
        # handler 内部拿到的应是纯业务 ID
        assert received_ids == ["3", "-42"]
        # handler 出参应被再次 encode 为方言 ID 返回给平台
        assert [r["id"] for r in result] == ["space|3", "space|-42"]

    def test_space_fetch_tolerates_no_prefix(self):
        """无前缀的历史 ID：decode 时按业务 ID 兜底返回，不报错。"""
        svc = self._fresh_service()

        received_ids: list[str] = []

        @svc.fetch_instance_info("space")
        def _fake_fetch(ids, requires):
            received_ids.extend(ids)
            return [{"id": i, "display_name": f"biz-{i}"} for i in ids]

        result = svc.dispatch_fetch_instance_info("space", ["3"], [])
        assert received_ids == ["3"]
        # 出参再 encode，仍然拼上前缀
        assert result[0]["id"] == "space|3"

    def test_non_space_resource_is_identity(self):
        """apm_application / grafana_dashboard / rum_application 恒等，不加前缀。"""
        svc = self._fresh_service()

        @svc.list_instance("apm_application")
        def _fake_list_apm(filter_data, page):
            return {"count": 1, "results": [{"id": "42", "display_name": "apm-42"}]}

        @svc.fetch_instance_info("grafana_dashboard")
        def _fake_fetch_grafana(ids, requires):
            return [{"id": i, "display_name": f"dash-{i}"} for i in ids]

        r1 = svc.dispatch_list_instance("apm_application", {}, {})
        assert r1["results"][0]["id"] == "42"  # 不加前缀

        r2 = svc.dispatch_fetch_instance_info("grafana_dashboard", ["1|abc-uid"], [])
        assert r2[0]["id"] == "1|abc-uid"  # 复合 ID 原样返回

    def test_list_instance_decodes_parent_id(self):
        """list_instance 时，filter.parent.id 应被 decode 为业务 ID 传给 handler。"""
        svc = self._fresh_service()

        received_filter: dict = {}

        @svc.list_instance("apm_application")
        def _fake_list(filter_data, page):
            received_filter.update(filter_data)
            return {"count": 0, "results": []}

        svc.dispatch_list_instance(
            "apm_application",
            {"parent": {"type": "space", "id": "space|3"}},
            {},
        )
        # handler 拿到的 parent.id 应已去前缀
        assert received_filter["parent"]["id"] == "3"

    def test_set_codec_hot_swap(self):
        """set_codec 后，已注册的 handler wrapper 立即用新 codec（属性访问，非闭包晚绑定）。"""
        svc = CallbackService(codec=IdentityCodec())

        @svc.list_instance("space")
        def _fake_list(filter_data, page):
            return {"count": 1, "results": [{"id": "3", "display_name": "x"}]}

        # 初始恒等：id 不变
        assert svc.dispatch_list_instance("space", {}, {})["results"][0]["id"] == "3"
        # 热更 codec
        svc.set_codec(V4NameCodec())
        assert svc.dispatch_list_instance("space", {}, {})["results"][0]["id"] == "space|3"


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
        assert call_count == 1  # 缓存命中，不再调 API
