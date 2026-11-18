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
