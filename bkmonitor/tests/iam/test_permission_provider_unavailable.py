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
# Permission 层 ProviderUnavailable / ProviderError 兜底测试
#
# 背景（08-31 评审建议 R3）：
#   IAM V4 URL 缺失场景下，V4 client 会把网络异常转成 ProviderUnavailable
#   （ProviderError 的子类）。历史上 Permission 层几个走 self._fw.* 的入口
#   要么完全没 catch，要么只 catch PermissionDenied，导致视图层直接 500。
#
# 本文件断言 Permission 层四个入口的降级行为：
#   1. is_allowed        —— _is_allowed_fw 单资源路径
#   2. batch_is_allowed  —— 走 _fw.batch_by_resource
#   3. get_apply_url     —— 走 _fw.get_apply_url
#   4. get_apply_data    —— 走 _fw.get_apply_data
#
# 每个入口都要满足：
#   * 不冒泡 500（catch ProviderError 及其子类 ProviderUnavailable）
#   * 有 log.exception（供运维追查）
#   * 语义降级：is_allowed → False / raise PermissionDenied；
#              batch_is_allowed → 该 (action, resource) 记为 False；
#              get_apply_url → ""；
#              get_apply_data → (None, "")
# ==============================================================================

from unittest.mock import MagicMock, patch

import pytest

from bkmonitor.iam.iam_engine.core.exceptions import ProviderError, ProviderUnavailable


# ------------------------------------------------------------------
# 测试脚手架：直接 mock get_framework 返回值，避免依赖 refactor 目录的 fixture
# ------------------------------------------------------------------


class _FakeResource:
    """占位 Resource：Permission 只用到 .type / .id 两个属性。"""

    def __init__(self, type_: str, id_: str):
        self.type = type_
        self.id = id_


@pytest.fixture
def fake_fw():
    """构造一个 mock 的 IAMFramework，返回 (mock_fw, permission_instance_factory)。

    每个测试可自定义 mock_fw.is_allowed / batch_by_resource / get_apply_url /
    get_apply_data 的 side_effect，然后调 permission_factory() 拿到装好 fw 的
    Permission 实例。
    """
    mock_fw = MagicMock()
    # 默认值：让不涉及的路径不炸
    mock_fw.is_allowed.return_value = True
    mock_fw.batch_by_resource.return_value = MagicMock(items=())
    mock_fw.get_apply_url.return_value = "http://iam.invalid/apply"
    mock_fw.get_apply_data.return_value = {"actions": []}

    with patch("bkmonitor.iam.permission.get_framework", return_value=mock_fw):
        # patch 生效期间，任何新建的 Permission(self._fw = get_framework()) 都会拿到 mock
        from bkmonitor.iam.permission import Permission

        def _make_permission():
            return Permission(username="tester", bk_tenant_id="system")

        yield mock_fw, _make_permission


# ------------------------------------------------------------------
# 1. is_allowed（单资源）
# ------------------------------------------------------------------


class TestIsAllowedProviderUnavailableFallback:
    """单资源鉴权：ProviderUnavailable / ProviderError 都不应冒泡 500。"""

    def test_provider_unavailable_returns_false_when_no_raise(self, fake_fw, caplog):
        mock_fw, make_permission = fake_fw
        mock_fw.is_allowed.side_effect = ProviderUnavailable("v4 down: base_url empty")

        perm = make_permission()
        with caplog.at_level("ERROR", logger="bkmonitor.iam.permission"):
            result = perm.is_allowed("view_business", raise_exception=False)

        assert result is False
        # 必须有 log.exception 供运维追查
        assert any("ProviderError" in r.getMessage() for r in caplog.records), (
            "ProviderUnavailable 必须走 log.exception 分支，否则运维完全看不到平台故障"
        )

    def test_provider_error_returns_false_when_no_raise(self, fake_fw):
        """ProviderError（非 Unavailable 子类）也走同一兜底路径。"""
        mock_fw, make_permission = fake_fw
        mock_fw.is_allowed.side_effect = ProviderError("some backend error")

        perm = make_permission()
        assert perm.is_allowed("view_business", raise_exception=False) is False

    def test_provider_unavailable_raises_permission_denied_when_raise_true(self, fake_fw):
        """raise_exception=True 时降级为 PermissionDenied（DRF 层能识别的 403），
        绝不上抛 ProviderUnavailable 让 DRF 冒泡为 500。"""
        from core.errors.iam import PermissionDeniedError

        mock_fw, make_permission = fake_fw
        mock_fw.is_allowed.side_effect = ProviderUnavailable("v4 down")
        # _build_permission_denied 会调 get_apply_data → get_apply_url，
        # 已经在同一 mock 上兜底，返回 mock 值即可。

        perm = make_permission()
        with pytest.raises(PermissionDeniedError):
            perm.is_allowed("view_business", raise_exception=True)


# ------------------------------------------------------------------
# 2. batch_is_allowed
# ------------------------------------------------------------------


class TestBatchIsAllowedProviderUnavailableFallback:
    def test_provider_unavailable_marks_all_as_false(self, fake_fw, caplog):
        """batch_by_resource 抛 ProviderUnavailable：当前 (action, 分组) 全标 False，
        不冒泡到视图层。"""
        mock_fw, make_permission = fake_fw
        mock_fw.batch_by_resource.side_effect = ProviderUnavailable("v4 down")

        perm = make_permission()
        with caplog.at_level("ERROR", logger="bkmonitor.iam.permission"):
            result = perm.batch_is_allowed(
                actions=["view_business"],
                resources=[[_FakeResource("space", "2")], [_FakeResource("space", "3")]],
            )

        # 两个资源都应有条目，且值为 False
        assert result["2"]["view_business"] is False
        assert result["3"]["view_business"] is False
        assert any("ProviderError" in r.getMessage() for r in caplog.records)

    def test_provider_unavailable_on_one_action_does_not_break_others(self, fake_fw):
        """多 action 场景下：一个 action 抛 ProviderUnavailable 不影响其它 action
        的正常返回。"""
        mock_fw, make_permission = fake_fw

        call_state = {"count": 0}

        def _side_effect(request):
            call_state["count"] += 1
            if request.action_id == "view_business":
                raise ProviderUnavailable("v4 down")
            # 其他 action 正常返回
            item = MagicMock(resource_id="2", allowed=True)
            return MagicMock(items=[item])

        mock_fw.batch_by_resource.side_effect = _side_effect

        perm = make_permission()
        result = perm.batch_is_allowed(
            actions=["view_business", "manage_business"],
            resources=[[_FakeResource("space", "2")]],
        )
        # view_business 被兜底为 False，manage_business 正常
        assert result["2"]["view_business"] is False
        assert result["2"]["manage_business"] is True


# ------------------------------------------------------------------
# 3. get_apply_url
# ------------------------------------------------------------------


class TestGetApplyUrlProviderUnavailableFallback:
    def test_provider_unavailable_returns_empty_string(self, fake_fw, caplog):
        """URL 缺失导致 get_apply_url 抛异常时降级为空字符串，前端可据此隐藏
        '去申请'按钮，比整块 500 好得多。"""
        mock_fw, make_permission = fake_fw
        mock_fw.get_apply_url.side_effect = ProviderUnavailable("v4 down")

        perm = make_permission()
        with caplog.at_level("ERROR", logger="bkmonitor.iam.permission"):
            url = perm.get_apply_url(["view_business"], resources=[_FakeResource("space", "2")])

        assert url == ""
        assert any("get_apply_url" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------------
# 4. get_apply_data
# ------------------------------------------------------------------


class TestGetApplyDataProviderUnavailableFallback:
    def test_apply_data_error_falls_back_to_none(self, fake_fw, caplog):
        """_fw.get_apply_data 抛 ProviderUnavailable 时 apply_data 降级为 None；
        apply_url 独立走 get_apply_url 路径。"""
        mock_fw, make_permission = fake_fw
        mock_fw.get_apply_data.side_effect = ProviderUnavailable("v4 down")
        mock_fw.get_apply_url.return_value = "http://iam/still-alive"

        perm = make_permission()
        with caplog.at_level("ERROR", logger="bkmonitor.iam.permission"):
            data, url = perm.get_apply_data(["view_business"], resources=[_FakeResource("space", "2")])

        assert data is None
        # apply_url 分支独立，仍能拿到 URL
        assert url == "http://iam/still-alive"
        assert any("get_apply_data" in r.getMessage() for r in caplog.records)

    def test_both_apply_data_and_apply_url_unavailable(self, fake_fw):
        """极端场景：apply_data 和 apply_url 都不可达，两者都返回降级值，
        整个流程仍不冒泡 500。"""
        mock_fw, make_permission = fake_fw
        mock_fw.get_apply_data.side_effect = ProviderUnavailable("v4 down")
        mock_fw.get_apply_url.side_effect = ProviderUnavailable("v4 down")

        perm = make_permission()
        data, url = perm.get_apply_data(["view_business"], resources=[_FakeResource("space", "2")])

        assert data is None
        assert url == ""
