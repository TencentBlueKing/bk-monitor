"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam.iam_v4.callback import services


class TestCallbackServices:
    """验证回调 handler 注册分发机制。"""

    def test_register_and_list_instance(self):
        def fake_list(filter_data, page):
            return {
                "count": 2,
                "results": [
                    {"id": "1", "display_name": "space-1"},
                    {"id": "2", "display_name": "space-2"},
                ],
            }

        def fake_fetch(ids, requires):
            return [{"id": i, "display_name": f"name-{i}"} for i in ids]

        services.register_handler("test_type", fake_list, fake_fetch)

        result = services.list_instance("test_type", {}, {"page": 1, "page_size": 10})
        assert result["count"] == 2
        assert len(result["results"]) == 2

        result = services.fetch_instance_info("test_type", ["1", "2"], ["display_name"])
        assert len(result) == 2

    def test_unregistered_type(self):
        """未注册的资源类型返回空。"""
        result = services.list_instance("unknown_type", {}, {})
        assert result == {"count": 0, "results": []}

        result = services.fetch_instance_info("unknown_type", ["1"], [])
        assert result == []


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
