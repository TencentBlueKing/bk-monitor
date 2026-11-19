from unittest.mock import Mock, call

import pytest
import requests

from bkmonitor.utils.user import (
    batch_get_user_display_names,
    extract_login_name_from_display_name,
    get_user_display_name,
    get_wxwork_mention_names,
)
from constants.common import DEFAULT_TENANT_ID
from core.errors.api import BKAPIError


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [
        ("xxx_login(xxx_name)", "xxx_login"),
        ("xxx_login", "xxx_login"),
        ("ｘｘｘ(xxx_login)", None),
        ("", None),
    ],
)
def test_extract_login_name_from_display_name(display_name, expected):
    assert extract_login_name_from_display_name(display_name) == expected


def test_get_wxwork_mention_names_does_not_query_in_single_tenant_mode(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = False
    query_display_info = Mock()
    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", query_display_info)

    assert get_wxwork_mention_names(["xxx_login", "all"]) == {
        "xxx_login": "xxx_login",
        "all": "all",
    }
    query_display_info.assert_not_called()


def test_get_wxwork_mention_names_queries_users_in_batches(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    usernames = [f"xxx_id_{index}" for index in range(101)]

    def query_display_info(*, bk_usernames, bk_tenant_id=None):
        return [
            {
                "bk_username": username,
                "display_name": f"xxx_login_{username.rsplit('_', 1)[-1]}(xxx_name)",
            }
            for username in bk_usernames
        ]

    query_display_info_mock = Mock(side_effect=query_display_info)
    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", query_display_info_mock)

    result = get_wxwork_mention_names([*usernames, usernames[0], "all"], bk_tenant_id="tenant_wx")

    assert len(result) == 101
    assert result["xxx_id_0"] == "xxx_login_0"
    assert result["xxx_id_100"] == "xxx_login_100"
    assert query_display_info_mock.call_args_list == [
        call(bk_usernames=usernames[:100], bk_tenant_id="tenant_wx"),
        call(bk_usernames=usernames[100:], bk_tenant_id="tenant_wx"),
    ]
    assert "all" not in result


def test_get_wxwork_mention_names_logs_users_without_login_name(settings, monkeypatch, caplog):
    """
    提取不到英文登录名的用户必须从 @ 名单缺席，且留下 warning 日志

    纯中文展示名（如「张三」）走的就是这条路径：该用户会静默缺席，调用方按
    mention_map.get(user, user) 回退成 UID，企微不会真正 @ 到人。
    若这条日志被删，现场「@ 了但没提醒」就完全没有线索。
    """
    settings.ENABLE_MULTI_TENANT_MODE = True
    monkeypatch.setattr(
        "core.drf_resource.api.bk_login.batch_query_user_display_info",
        lambda **kwargs: [
            {"bk_username": "xxx_id_ok", "display_name": "xxx_login(xxx_name)"},
            {"bk_username": "xxx_id_cn", "display_name": "张三"},
        ],
    )

    with caplog.at_level("WARNING"):
        result = get_wxwork_mention_names(["xxx_id_ok", "xxx_id_cn"], bk_tenant_id="tenant_wx")

    # 能提取登录名的进名单，中文展示名的缺席（由调用方回退 UID）
    assert result == {"xxx_id_ok": "xxx_login"}
    assert "xxx_id_cn" not in result

    # 缺席必须可观测，且日志里要能定位到具体用户与租户
    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "xxx_id_cn" in warnings[0].getMessage()
    assert "tenant_wx" in warnings[0].getMessage()


def test_get_user_display_name_short_circuits_empty_and_mismatched_username(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.ROLE = "worker"
    calls = []

    def _batch(bk_usernames=None, bk_tenant_id=None):
        calls.append((list(bk_usernames or []), bk_tenant_id))
        return [{"bk_username": "other_user", "display_name": "张冠李戴"}]

    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

    assert get_user_display_name("") == ""
    assert get_user_display_name(None) is None  # type: ignore[arg-type]
    assert calls == []

    # 返回记录 bk_username 与请求不一致时不应误取首元素
    assert get_user_display_name("uid_a", bk_tenant_id="tenant_a") == "uid_a"
    assert calls == [(["uid_a"], "tenant_a")]


def test_batch_get_user_display_names_isolates_bad_chunk_but_breaks_on_timeout(settings, monkeypatch):
    settings.ENABLE_MULTI_TENANT_MODE = True
    usernames = [f"u_{i}" for i in range(105)]

    # 场景 1：第 1 块抛非超时参数异常，第 2 块仍正常转换
    chunk_calls = []

    def _partial_error(bk_usernames=None, bk_tenant_id=None):
        names = list(bk_usernames or [])
        chunk_calls.append(len(names))
        if len(chunk_calls) == 1:
            raise BKAPIError(system_name="bk-user", url="display_info", result="bad param")
        return [{"bk_username": name, "display_name": f"名_{name}"} for name in names]

    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _partial_error)
    res = batch_get_user_display_names(usernames, bk_tenant_id="t1")
    assert chunk_calls == [100, 5]
    assert res["u_0"] == "u_0"
    assert res["u_100"] == "名_u_100"

    # 场景 2：第 1 块发生连接超时，立即中止后续分块避免叠加等待
    timeout_calls = []

    def _timeout_error(bk_usernames=None, bk_tenant_id=None):
        timeout_calls.append(len(list(bk_usernames or [])))
        raise requests.exceptions.ReadTimeout("read timed out")

    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _timeout_error)
    res_timeout = batch_get_user_display_names(usernames, bk_tenant_id=DEFAULT_TENANT_ID)
    assert timeout_calls == [100]
    assert res_timeout["u_100"] == "u_100"


def test_get_user_display_name_comma_branch_does_not_fall_back_to_default_tenant(settings, monkeypatch):
    """逗号分支与批量转换保持同一口径：无有效租户时回退原标识，不查默认租户"""
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.ROLE = "worker"
    calls = []

    def _batch(bk_usernames=None, bk_tenant_id=None):
        calls.append((list(bk_usernames or []), bk_tenant_id))
        return [{"bk_username": name, "display_name": f"名_{name}"} for name in bk_usernames or []]

    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _batch)

    # 1. 未传租户且无请求上下文：直接回退原值，不发起任何查询
    assert get_user_display_name("uid_a,uid_b") == "uid_a,uid_b"
    assert calls == []

    # 2. 传入有效租户时正常转换，且不分块落到默认租户
    assert get_user_display_name("uid_a,uid_b", bk_tenant_id="tenant_a") == "名_uid_a,名_uid_b"
    assert calls == [(["uid_a", "uid_b"], "tenant_a")]


def test_is_upstream_unavailable_error_matches_framework_bkapi_error_timeout():
    """框架把 ReadTimeout 转成 BKAPIError 后文本为中文「接口返回结果超时」，必须仍被识别为上游不可用"""
    from bkmonitor.utils.user import _is_upstream_unavailable_error

    # 框架 contrib/api.py 捕获 ReadTimeout 后实际抛出的形态
    framework_timeout = BKAPIError(
        system_name="bk-user",
        url="/api/v3/open/tenant/users/-/display_info/",
        result="接口返回结果超时",
    )
    assert _is_upstream_unavailable_error(framework_timeout) is True

    # 原生超时/连接异常仍然识别
    assert _is_upstream_unavailable_error(requests.exceptions.ReadTimeout("read timed out")) is True
    assert _is_upstream_unavailable_error(requests.exceptions.ConnectionError("connection aborted")) is True
    assert _is_upstream_unavailable_error(TimeoutError("timed out")) is True

    # 普通业务错误不应被误判为上游不可用，否则会提前中止后续分块
    assert _is_upstream_unavailable_error(BKAPIError(system_name="bk-user", url="x", result="bad param")) is False
    assert _is_upstream_unavailable_error(ValueError("invalid username")) is False


def test_batch_get_user_display_names_breaks_on_framework_timeout_error(settings, monkeypatch):
    """框架转换后的中文超时异常同样应触发分块中止，避免后续分块叠加等待"""
    settings.ENABLE_MULTI_TENANT_MODE = True
    usernames = [f"u_{i}" for i in range(105)]
    timeout_calls = []

    def _framework_timeout(bk_usernames=None, bk_tenant_id=None):
        timeout_calls.append(len(list(bk_usernames or [])))
        raise BKAPIError(system_name="bk-user", url="display_info", result="接口返回结果超时")

    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", _framework_timeout)

    res = batch_get_user_display_names(usernames, bk_tenant_id="t1")

    # 只尝试第 1 块即中止，第 2 块不应再发起
    assert timeout_calls == [100]
    assert res["u_0"] == "u_0"
    assert res["u_100"] == "u_100"
