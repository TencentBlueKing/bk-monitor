from unittest.mock import Mock, call

import pytest

from bkmonitor.utils.user import extract_login_name_from_display_name, get_wxwork_mention_names


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

    def query_display_info(*, bk_usernames):
        return [
            {
                "bk_username": username,
                "display_name": f"xxx_login_{username.rsplit('_', 1)[-1]}(xxx_name)",
            }
            for username in bk_usernames
        ]

    query_display_info_mock = Mock(side_effect=query_display_info)
    monkeypatch.setattr("core.drf_resource.api.bk_login.batch_query_user_display_info", query_display_info_mock)

    result = get_wxwork_mention_names([*usernames, usernames[0], "all"])

    assert len(result) == 101
    assert result["xxx_id_0"] == "xxx_login_0"
    assert result["xxx_id_100"] == "xxx_login_100"
    assert query_display_info_mock.call_args_list == [
        call(bk_usernames=usernames[:100]),
        call(bk_usernames=usernames[100:]),
    ]
    assert "all" not in result
