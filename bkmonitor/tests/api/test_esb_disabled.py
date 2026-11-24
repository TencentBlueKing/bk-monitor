import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import ValidationError

from bk_monitor_base.config.blueking import BlueKingConfig
from bk_monitor_base.infras.third_party_api.cmdb.client import SearchBusiness as BaseSearchBusiness
from bk_monitor_base.infras.third_party_api.cmsi.client import SendMail as BaseSendMail
from bk_monitor_base.infras.third_party_api.job.client import GetJobInstanceStatus

from api.bk_login.default import BkUserApiResource, GetAllUserResource, GetUserInfo, LookupTenantUsersResource
from api.cmdb.client import SearchBusiness
from api.cmsi.default import SendMail
from api.job.default import GetJobInstanceStatusResource
from api.log_search.default import ESQuerySearchResource
from api.node_man.default import StartDebugResource
from api.sops.default import GetTaskStatusResource
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.local import local
from monitor_web.commons.user.views import UserViewSet
from monitor_web.notice_group.resources import front
from monitor_web.user_group import resources as user_groups


@override_settings(
    ESB_DISABLED=True,
    ENABLE_MULTI_TENANT_MODE=False,
    BK_COMPONENT_API_URL="https://gateway.example.com",
    CMDB_API_BASE_URL="",
    JOB_API_BASE_URL="",
    CMSI_API_BASE_URL="",
    BKSOPS_API_BASE_URL="",
    BKNODEMAN_API_BASE_URL="",
    BKLOGSEARCH_API_BASE_URL="",
    BKLOGSEARCH_API_GW_BASE_URL="",
)
@pytest.mark.parametrize(
    ("resource", "gateway"),
    [
        (SearchBusiness, "bk-cmdb"),
        (GetJobInstanceStatusResource, "bk-job"),
        (SendMail, "bk-cmsi"),
        (StartDebugResource, "bk-nodeman"),
        (GetTaskStatusResource, "bk-sops"),
        (ESQuerySearchResource, "bk-log-search"),
    ],
)
def test_single_tenant_gateway(resource, gateway):
    assert f"/api/{gateway}/" in resource().base_url


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False)
def test_existing_accounts_use_user_ids_and_chunk_large_groups():
    accounts = [f"user-{i}" for i in range(101)]

    def lookup(resource, params):
        assert resource._get_tenant_id() == "tenant-a"
        assert params["lookup_field"] == "bk_username"
        return [
            {"login_name": f"login-{name}", "bk_username": name, "display_name": name}
            for name in params["lookups"].split(",")
        ]

    with patch.object(LookupTenantUsersResource, "request", autospec=True, side_effect=lookup) as query:
        result = GetAllUserResource().request(exact_lookups=",".join(accounts), bk_tenant_id="tenant-a")
    assert query.call_count == 2
    assert result["count"] == len(accounts)
    assert [u["username"] for u in result["results"]] == accounts


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False)
def test_mixed_mail_recipients_get_one_delivery():
    with patch.object(SendMail, "send_request") as send:
        SendMail().perform_request({"receiver__username": "alice,guest@tai", "cc__username": "bob,carol"})
    send.assert_called_once_with(
        {"receiver__username": ["alice", "guest@tai"], "cc__username": ["bob", "carol"]}, ["alice", "guest@tai"]
    )


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=True)
def test_receiver_worker_uses_authenticated_tenant_for_every_batch():
    accounts = [f"user-{i}" for i in range(52)]
    main_thread = threading.get_ident()
    calls = []

    def lookup(resource, params):
        calls.append((threading.get_ident(), resource.get_headers()["X-Bk-Tenant-Id"]))
        return [{"bk_username": name, "display_name": f"Name {name}"} for name in params["lookups"].split(",")]

    cc = SimpleNamespace(
        get_app_by_id=lambda _: SimpleNamespace(maintainers=accounts),
        get_notify_roles=lambda: {"maintainers": "Maintainers"},
    )
    with (
        patch.object(
            local, "current_request", SimpleNamespace(user=SimpleNamespace(tenant_id="tenant-a")), create=True
        ),
        patch.object(front, "resource", SimpleNamespace(cc=cc)),
        patch("core.drf_resource.contrib.api.make_userinfo", return_value={"bk_username": "alice"}),
        patch.object(BkUserApiResource, "perform_request", lookup),
    ):
        result = front.GetReceiverResource().perform_request({"bk_biz_id": 1})
    assert len(calls) == 2
    assert all(thread != main_thread and tenant == "tenant-a" for thread, tenant in calls)
    assert {u["display_name"] for u in result[0]["children"][0]["members"]} == {f"Name {name}" for name in accounts}


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False)
def test_bulk_edit_preserves_saved_collaborator_and_resolves_virtual_account():
    saved = {"id": "collaborator", "type": "user", "display_name": "Collaborator"}
    arrange = SimpleNamespace(
        users=[saved],
        user_group_id=1,
        duty_rule_id=0,
        duty_users=[],
        duty_time=[],
        group_type="specified",
        group_number=1,
    )
    edit = user_groups.UserGroupBulkUpdateResource()
    edit.ids, edit.bk_biz_id = [1], 1
    edit.edit_data = {"users": ["collaborator", "virtual"]}

    def lookup(resource, params):
        assert params["lookups"] == "virtual"
        if resource.action.endswith("/virtual-users/-/lookup/"):
            return [{"bk_username": "virtual", "display_name": "Virtual"}]
        return []

    receivers = SimpleNamespace(notice_group=SimpleNamespace(get_receiver=lambda **kwargs: []))
    with (
        patch.object(user_groups, "resource", receivers),
        patch.object(user_groups.DutyArrange.objects, "filter", return_value=[arrange]),
        patch.object(user_groups.DutyArrange.objects, "bulk_update") as save,
        patch.object(BkUserApiResource, "perform_request", lookup),
    ):
        edit.update_users(partial=False)
        save.assert_called_once_with([arrange], ["users", "hash"])
        assert {u["id"]: u["display_name"] for u in arrange.users} == {
            "collaborator": "Collaborator",
            "virtual": "Virtual",
        }

        edit.update_users(partial=True)
        assert [u["id"] for u in arrange.users] == ["collaborator", "virtual"]
        save.reset_mock()

        # 另一个排班没有该协同账号，不能将其作为已保存成员跳过校验。
        arrange.users = []
        with patch.object(BkUserApiResource, "perform_request", return_value=[]), pytest.raises(ValidationError):
            edit.update_users(partial=False)
        save.assert_not_called()


@pytest.mark.parametrize("value", [None, "", "true", "false"])
def test_common_clients_respect_existing_mode(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("BKPAAS_ESB_ENABLED", raising=False)
    else:
        monkeypatch.setenv("BKPAAS_ESB_ENABLED", value)
    config = SimpleNamespace(blueking=BlueKingConfig(enable_multi_tenancy=False, api_configs={}))
    for client in (BaseSearchBusiness, BaseSendMail, GetJobInstanceStatus):
        url = client(config=config)._get_api_url({"bk_supplier_account": "0"})
        assert ("/api/c/compapi/" in url) == (value != "false")
        assert not config.blueking.enable_multi_tenancy


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=True)
def test_user_pages_are_isolated_by_request_tenant():
    def list_page(resource, params):
        tenant = resource._get_tenant_id()
        assert params == {"page": 1}
        return {"results": [{"bk_username": tenant, "display_name": tenant}], "count": 1}

    with patch.object(BkUserApiResource, "perform_request", list_page):
        for tenant in ("first", "second"):
            with patch("core.drf_resource.contrib.api.get_request_tenant_id", return_value=tenant):
                resource = GetAllUserResource()
                assert not hasattr(resource.request, "cached")
                assert resource.request(page=1)["results"][0]["username"] == tenant


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False)
def test_fuzzy_search_uses_tenant_openapi_and_paginates_matches():
    user = {"bk_username": "first-id", "login_name": "alice", "display_name": "A"}
    other = {"bk_username": "other-id", "login_name": "other", "display_name": "Other"}
    pages = [
        {"results": [user] + [other] * 999, "count": 1001},
        {"results": [{**other, "bk_username": "last-id", "display_name": "ALICE"}], "count": 1001},
    ]
    with patch.object(BkUserApiResource, "perform_request", side_effect=pages) as query:
        resource = GetAllUserResource()
        assert resource.action == "/api/v3/open/tenant/users/"
        result = resource.request(fuzzy_lookups="ali", page=2, page_size=1)
    assert result == {"count": 2, "results": [{"username": "last-id", "display_name": "ALICE", "logo": ""}]}
    assert [call.args[0] for call in query.call_args_list] == [{"page": n, "page_size": 1000} for n in (1, 2)]


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=True)
def test_selector_forwards_only_search_fields_and_uses_request_tenant():
    view = UserViewSet.as_view({"get": "list_users"})
    request = APIRequestFactory().get("/", {"page": "2", "page_size": "5", "app_code": "selector", "extra": "unused"})

    def list_page(resource, params):
        assert params == {"page": 2, "page_size": 5}
        assert resource.get_headers()["X-Bk-Tenant-Id"] == "current-tenant"
        return {"count": 0, "results": []}

    with (
        patch.object(
            GetAllUserResource, "perform_request", autospec=True, side_effect=GetAllUserResource.perform_request
        ) as lookup,
        patch("core.drf_resource.contrib.api.get_request_tenant_id", return_value="current-tenant"),
        patch("core.drf_resource.contrib.api.make_userinfo", return_value={"bk_username": "alice"}),
        patch.object(BkUserApiResource, "perform_request", list_page),
    ):
        response = view(request)
    assert response.status_code == 200
    assert lookup.call_args.args[1] == {"page": 2, "page_size": 5}
    assert {"bk_username", "bk_tenant_id"}.isdisjoint(UserViewSet.RequestSerializer().fields)


@pytest.mark.parametrize(("field", "value"), [("page", "bad"), ("page_size", ""), ("page", "0"), ("page_size", "-1")])
@override_settings(ESB_DISABLED=True)
def test_selector_rejects_invalid_pagination_before_lookup(field, value):
    view = UserViewSet.as_view({"get": "list_users"})
    request = APIRequestFactory().get("/", {"fuzzy_lookups": "alice", field: value})
    with patch.object(GetAllUserResource, "__call__") as lookup:
        assert view(request).status_code == 400
        lookup.assert_not_called()


@pytest.mark.parametrize("multi", [False, True])
def test_selector_preserves_legacy_query_parameters_with_default_esb(multi):
    view = UserViewSet.as_view({"get": "list_users"})
    request = APIRequestFactory().get("/", {"page": "1", "exact_lookups": "alice,bob", "app_code": "selector"})
    with (
        override_settings(ESB_DISABLED=False, ENABLE_MULTI_TENANT_MODE=multi),
        patch.object(GetAllUserResource, "__call__", return_value={"count": 0, "results": []}) as lookup,
    ):
        assert view(request).status_code == 200
        lookup.assert_called_once_with(page=["1"], exact_lookups=["alice,bob"])


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False)
def test_user_profile_preserves_saved_id():
    with patch.object(
        BkUserApiResource, "perform_request", return_value={"bk_username": "id", "login_name": "name"}
    ) as upstream:
        assert GetUserInfo().request(id="id")["username"] == "id"
    upstream.assert_called_once_with({"bk_username": "id"})


@pytest.mark.parametrize("multi", [False, True])
def test_existing_user_route_and_cache_with_default_esb(multi):
    with override_settings(ESB_DISABLED=False, ENABLE_MULTI_TENANT_MODE=multi):
        resource = GetAllUserResource()
        assert resource.cache_type is CacheType.USER and hasattr(resource.request, "cached")
        with patch.object(BkUserApiResource, "perform_request", return_value={"count": 1}) as legacy:
            result = resource.perform_request({"page": 1})
        if multi:
            assert result == {"count": 0, "results": []}
            legacy.assert_not_called()
        else:
            assert resource.action == "/list_users/" and result == {"count": 1}
            legacy.assert_called_once_with({"page": 1})


@pytest.mark.parametrize("multi", [False, True])
def test_unset_esb_switch_uses_final_django_tenant_mode(multi):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "settings",
        "ENABLE_MULTI_TENANT_MODE": str(multi).lower(),
        "BKPAAS_MULTI_TENANT_MODE": str(not multi).lower(),
    }
    env.pop("BKPAAS_ESB_ENABLED", None)
    script = """
from django.conf import settings
assert not settings.ESB_DISABLED
from blueapps.account.components.bk_token.verification_strategy import is_esb_enabled
print(is_esb_enabled())
"""
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2], env=env, text=True
    )
    assert output.splitlines()[-1] == str(not multi)


@pytest.mark.parametrize(("switch", "separator"), [(None, "//"), ("true", "//"), ("false", "/")])
def test_monitor_login_urls_with_trailing_slash(switch, separator):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "settings",
        "BK_API_URL_TMPL": "https://gw.example.test/{api_name}/",
    }
    if switch is None:
        env.pop("BKPAAS_ESB_ENABLED", None)
    else:
        env["BKPAAS_ESB_ENABLED"] = switch
    script = """
from django.conf import settings
template = settings.BK_API_URL_TMPL
from blueapps.account.components.bk_token.verification_strategy import get_apigw_url
for action in ("verify", "userinfo"):
    print(get_apigw_url("bk-login", f"/login/api/v3/open/bk-tokens/{action}/"))
"""
    output = subprocess.check_output(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2], env=env, text=True
    )
    assert output.splitlines()[-2:] == [
        f"https://gw.example.test/bk-login{separator}prod/login/api/v3/open/bk-tokens/{action}/"
        for action in ("verify", "userinfo")
    ]
