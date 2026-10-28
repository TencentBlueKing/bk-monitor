"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.test import override_settings

from bkmonitor.iam.my_perm import (
    IAM_MY_PERM_PATHS,
    get_iam_mode,
    get_iam_my_perm_url,
)

V3_HOST = "https://iam.example.com"
V4_HOST = "https://iamv4.example.com"


def fake_mode(mode):
    """构造 get_mode_provider 的替身，get_mode() 返回带 value 的 str 枚举。"""

    class _Mode:
        value = mode

    return mock.MagicMock(return_value=mock.MagicMock(get_mode=mock.MagicMock(return_value=_Mode())))


def test_v3_my_perm_uses_legacy_path():
    with (
        override_settings(BK_IAM_SAAS_HOST=V3_HOST),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v3")),
    ):
        assert get_iam_my_perm_url() == f"{V3_HOST}{IAM_MY_PERM_PATHS['v3']}"


def test_v4_my_perm_uses_v4_path():
    """V4 的「我的权限」路由是 /permission/my-own/overview，与 V3 的 /my-perm 不同。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=V4_HOST),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v4")),
    ):
        assert get_iam_my_perm_url() == f"{V4_HOST}{IAM_MY_PERM_PATHS['v4']}"


def test_union_mode_follows_v4_path():
    """union 是双栈迁移期，current 已是 v4，跳转应走 v4 路由。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=V4_HOST),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("union")),
    ):
        assert get_iam_my_perm_url() == f"{V4_HOST}{IAM_MY_PERM_PATHS['v4']}"


def test_empty_host_returns_empty_string():
    """基址缺失时返回空串，由前端决定降级行为。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=""),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v4")),
    ):
        assert get_iam_my_perm_url() == ""


def test_empty_host_skips_mode_detection():
    """基址为空时不应触发版本探测：未接入 IAM 的部署不必付出这个开销。"""
    provider = fake_mode("v4")
    with (
        override_settings(BK_IAM_SAAS_HOST=""),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", provider),
    ):
        assert get_iam_my_perm_url() == ""

    provider.assert_not_called()


def test_trailing_slash_in_host_not_duplicated():
    """基址带尾斜杠时不应拼出双斜杠。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=f"{V4_HOST}/"),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v4")),
    ):
        assert get_iam_my_perm_url() == f"{V4_HOST}{IAM_MY_PERM_PATHS['v4']}"


def test_host_with_path_prefix_keeps_path():
    """基址带路径前缀时（实际部署常见形态），前缀应保留并正确追加路由。"""
    host_with_path = "https://paas.example.com/o/bk_iam/"
    with (
        override_settings(BK_IAM_SAAS_HOST=host_with_path),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v4")),
    ):
        assert get_iam_my_perm_url() == f"https://paas.example.com/o/bk_iam{IAM_MY_PERM_PATHS['v4']}"


def test_mode_provider_failure_falls_back_to_v3():
    """版本探测异常不应导致上下文接口不可用，按 v3 处理。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=V3_HOST),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", side_effect=RuntimeError("boom")),
    ):
        assert get_iam_mode() == "v3"
        assert get_iam_my_perm_url() == f"{V3_HOST}{IAM_MY_PERM_PATHS['v3']}"


def test_mode_accepts_plain_string():
    """get_mode() 直接返回字符串时也应正确识别，不依赖枚举。"""
    with (
        override_settings(BK_IAM_SAAS_HOST=V4_HOST),
        mock.patch(
            "bkmonitor.iam.mode.get_mode_provider",
            mock.MagicMock(return_value=mock.MagicMock(get_mode=mock.MagicMock(return_value="V4"))),
        ),
    ):
        assert get_iam_mode() == "v4"
        assert get_iam_my_perm_url() == f"{V4_HOST}{IAM_MY_PERM_PATHS['v4']}"


def test_unadapted_mode_falls_back_to_v3_with_warning(caplog):
    """本模块不认识的版本兜底 v3 并留痕。

    引擎侧 get_mode() 只会返回 v3/v4/union，当前线上不存在第五种值，
    该分支是给「引擎换代新增协议、监控侧尚未适配」留的前向保护，此处用 mock 构造。
    """
    with (
        override_settings(BK_IAM_SAAS_HOST=V3_HOST),
        mock.patch("bkmonitor.iam.mode.get_mode_provider", fake_mode("v5")),
        caplog.at_level("WARNING"),
    ):
        assert get_iam_mode() == "v3"

    assert any("未适配的 IAM 鉴权版本" in record.message for record in caplog.records)


def test_invalid_mode_error_is_absorbed_and_falls_back_to_v3():
    """非法配置由引擎 fail-closed 抛错，本模块吞掉异常拼 v3 地址：跳转地址可用，权限判定不受影响。"""
    from iam_engine.core.exceptions import InvalidAuthModeError

    with (
        override_settings(BK_IAM_SAAS_HOST=V3_HOST),
        mock.patch(
            "bkmonitor.iam.mode.get_mode_provider",
            side_effect=InvalidAuthModeError("v5", "invalid IAM permission mode configured: v5"),
        ),
    ):
        assert get_iam_mode() == "v3"
        assert get_iam_my_perm_url() == f"{V3_HOST}{IAM_MY_PERM_PATHS['v3']}"
