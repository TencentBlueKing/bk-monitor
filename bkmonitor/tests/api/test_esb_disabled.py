from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from bk_monitor_base.config.blueking import BlueKingConfig
from bk_monitor_base.infras.third_party_api.cmdb.client import SearchBusiness as BaseSearchBusiness
from bk_monitor_base.infras.third_party_api.cmsi.client import SendMail as BaseSendMail
from bk_monitor_base.infras.third_party_api.job.client import GetJobInstanceStatus

from api.bk_login.default import GetAllUserResource, LookupTenantUsersResource
from api.cmdb.client import SearchBusiness
from api.cmsi.default import SendMail
from api.job.default import GetJobInstanceStatusResource
from api.log_search.default import ESQuerySearchResource
from api.node_man.default import StartDebugResource
from api.sops.default import GetTaskStatusResource


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
def test_existing_accounts_use_login_names_and_chunk_large_groups():
    accounts = [f"user-{i}" for i in range(101)]

    def lookup(params):
        assert params["lookup_field"] == "login_name"
        return [
            {"login_name": name, "bk_username": f"id-{name}", "display_name": name}
            for name in params["lookups"].split(",")
        ]

    with patch.object(LookupTenantUsersResource, "request", side_effect=lookup) as query:
        result = GetAllUserResource().perform_request({"exact_lookups": ",".join(accounts)})
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
