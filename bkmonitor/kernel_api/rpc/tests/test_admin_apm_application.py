import pytest

from kernel_api.rpc.functions.admin import apm as admin_apm
from kernel_api.rpc.registry import KernelRPCRegistry


@pytest.fixture
def applications(monkeypatch):
    from apm.models import ApmApplication

    ApmApplication.objects.bulk_create(
        [
            ApmApplication(bk_tenant_id="keyword-test", bk_biz_id=2, app_name="bkop", app_alias="运维环境trace"),
            ApmApplication(bk_tenant_id="keyword-test", bk_biz_id=2, app_name="worker", app_alias="BKOP 运维任务"),
            ApmApplication(bk_tenant_id="keyword-test", bk_biz_id=3, app_name="other-biz", app_alias="运维环境trace"),
            ApmApplication(
                bk_tenant_id="other-tenant", bk_biz_id=2, app_name="other-tenant", app_alias="运维环境trace"
            ),
        ]
    )
    monkeypatch.setattr(
        admin_apm, "_load_apm_datasource_maps", lambda _: {kind: {} for kind in admin_apm.DATASOURCE_TYPES}
    )
    monkeypatch.setattr(admin_apm, "_load_service_count_map", lambda _: {})
    return ApmApplication.objects.get(bk_tenant_id="keyword-test", bk_biz_id=2, app_name="bkop")


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize(
    ("filters", "expected_names"),
    [
        ({"keyword": "运维"}, {"bkop", "worker"}),
        ({"keyword": "  bKoP  "}, {"bkop", "worker"}),
        ({"keyword": "环境trace"}, {"bkop"}),
        ({"keyword": "missing"}, set()),
        ({"keyword": "  "}, {"bkop", "worker"}),
        ({"keyword": None}, {"bkop", "worker"}),
        ({"app_name": "运维"}, set()),
        ({"app_name": "bkop", "keyword": "运维"}, {"bkop"}),
        ({"app_name": "bkop", "keyword": "任务"}, set()),
    ],
)
def test_keyword_matches_name_or_alias_with_existing_scope(applications, filters, expected_names):
    result = admin_apm.list_apm_applications({"bk_tenant_id": "keyword-test", "bk_biz_id": 2, **filters})
    assert {item["app_name"] for item in result["data"]["items"]} == expected_names
    assert result["data"]["total"] == len(expected_names)


@pytest.mark.django_db(databases="__all__")
def test_keyword_combines_with_application_ids_and_paginates(applications):
    params = {"bk_tenant_id": "keyword-test", "bk_biz_id": 2, "keyword": "运维", "page_size": 1}
    first = admin_apm.list_apm_applications(params)["data"]
    second = admin_apm.list_apm_applications({**params, "page": 2})["data"]
    assert first["total"] == second["total"] == 2
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["application_id"] != second["items"][0]["application_id"]
    selected = admin_apm.list_apm_applications({**params, "application_ids": [applications.id]})["data"]
    assert selected["total"] == 1
    assert selected["items"][0]["app_name"] == "bkop"


def test_keyword_is_discoverable_in_rpc_contract():
    contract = KernelRPCRegistry.get_function_detail("admin.apm.application_list")
    assert "keyword" in contract["params_schema"]
    assert contract["example_params"]["keyword"] == "运维"
