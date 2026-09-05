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
# 阶段 1 · 评论 1 后半 —— V4Client 传输层异常兜底
#
# 覆盖：Timeout / HTTPError 之外的 `RequestException` 子类
# （MissingSchema / InvalidURL / ConnectionError / SSLError 等）都必须被
# V4Client 内部转换成 ProviderUnavailable，绝不冒泡到视图层变成 500。
#
# 具体触发场景：BK_IAM_V4_API_BASE_URL 为空 → base_url="" → requests 抛
# MissingSchema。这条兜底是"迁移期忘配 URL 也不炸"的最后一道防线。
# ==============================================================================

import pytest
import requests

from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.iam_v4.client import V4Client


def _client(base_url: str = "") -> V4Client:
    return V4Client(
        base_url=base_url,
        system_id="bk_monitor_v4",
        app_code="test_app",
        app_secret="test_secret",
        timeout=1,
    )


class TestV4ClientMissingSchema:
    """base_url 为空时最直接会触发的场景。"""

    def test_post_missing_schema_raises_provider_unavailable(self):
        client = _client(base_url="")
        with pytest.raises(ProviderUnavailable) as exc:
            client._post("/api/v1/foo", {})
        assert "transport error" in str(exc.value)
        assert isinstance(exc.value.__cause__, requests.exceptions.MissingSchema)

    def test_get_missing_schema_raises_provider_unavailable(self):
        client = _client(base_url="")
        with pytest.raises(ProviderUnavailable) as exc:
            client._get("/api/v1/foo")
        assert isinstance(exc.value.__cause__, requests.exceptions.MissingSchema)

    def test_put_missing_schema_raises_provider_unavailable(self):
        client = _client(base_url="")
        with pytest.raises(ProviderUnavailable) as exc:
            client._put("/api/v1/foo", {})
        assert isinstance(exc.value.__cause__, requests.exceptions.MissingSchema)

    def test_delete_missing_schema_raises_provider_unavailable(self):
        client = _client(base_url="")
        with pytest.raises(ProviderUnavailable) as exc:
            client._delete("/api/v1/foo")
        assert isinstance(exc.value.__cause__, requests.exceptions.MissingSchema)


class TestV4ClientConnectionError:
    """网络断开 / DNS 失败 → ConnectionError，也应该走兜底。"""

    def test_connection_error_raises_provider_unavailable(self, mocker):
        client = _client(base_url="http://iam.example.com")
        mocker.patch(
            "bkmonitor.iam.iam_v4.client.requests.post",
            side_effect=requests.exceptions.ConnectionError("dns failure"),
        )
        with pytest.raises(ProviderUnavailable) as exc:
            client._post("/api/v1/foo", {})
        assert "transport error" in str(exc.value)
        assert isinstance(exc.value.__cause__, requests.exceptions.ConnectionError)


class TestV4ClientTimeoutStillMapped:
    """回归保护：Timeout 分支未被 RequestException 兜底吞掉。"""

    def test_timeout_still_raises_provider_unavailable(self, mocker):
        client = _client(base_url="http://iam.example.com")
        mocker.patch(
            "bkmonitor.iam.iam_v4.client.requests.get",
            side_effect=requests.Timeout(),
        )
        with pytest.raises(ProviderUnavailable) as exc:
            client._get("/api/v1/foo")
        # Timeout 走的是专门分支，msg 用 "timeout" 关键字
        assert "timeout" in str(exc.value).lower()


class TestV4ClientHTTPErrorStillMapped:
    """回归保护：HTTPError 分支仍然是 ProviderUnavailable(code=...)，未被兜底覆盖。"""

    def test_http_error_still_raises_with_status_code(self, mocker):
        client = _client(base_url="http://iam.example.com")
        fake_resp = mocker.MagicMock()
        fake_resp.status_code = 502
        fake_resp.text = "bad gateway"
        fake_resp.raise_for_status.side_effect = requests.HTTPError(response=fake_resp)
        mocker.patch("bkmonitor.iam.iam_v4.client.requests.post", return_value=fake_resp)

        with pytest.raises(ProviderUnavailable) as exc:
            client._post("/api/v1/foo", {})
        assert exc.value.code == 502
