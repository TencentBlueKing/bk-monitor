from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import yaml
from django.urls import resolve

from bkmonitor.space.space_api import InjectSpaceApi
from core.drf_resource.routers import ResourceRouter
from monitor_web.commons.biz import resources as module


@pytest.fixture
def spaces():
    return [
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -101,
            "space_type_id": "bkci",
            "space_id": "bkms-off",
            "status": "disabled",
        },
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -102,
            "space_type_id": "bkci",
            "space_id": "bkms-on",
            "status": "normal",
        },
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -103,
            "space_type_id": "bkci",
            "space_id": "other",
            "status": "disabled",
        },
        {"bk_tenant_id": "system", "bk_biz_id": 2, "space_type_id": "bkcc", "space_id": "2", "status": "disabled"},
    ]


def test_user_space_list_hides_only_disabled_bkms_and_restores(spaces, monkeypatch):
    permission = Mock()
    permission.filter_space_list_by_action.return_value = spaces
    monkeypatch.setattr(module, "Permission", Mock(return_value=permission))
    assert [space["bk_biz_id"] for space in module.ListSpacesResource.get_space_by_user("system", "tester")] == [
        -102,
        -103,
        2,
    ]
    spaces[0]["status"] = "normal"
    assert module.ListSpacesResource.get_space_by_user("system", "tester") == spaces


@pytest.mark.parametrize("block_rule", ["", "tester"])
def test_show_all_retains_disabled_bkms(spaces, monkeypatch, settings, block_rule):
    settings.BLOCK_SPACE_RULE = block_rule
    permission = Mock()
    permission.filter_space_list_by_action.return_value = spaces
    monkeypatch.setattr(module, "Permission", Mock(return_value=permission))
    monkeypatch.setattr(module, "get_request", lambda **kwargs: None)
    monkeypatch.setattr(module, "get_request_username", lambda: "tester")
    monkeypatch.setattr(module.SpaceApi, "list_spaces_dict", Mock(return_value=spaces))
    result = module.ListSpacesResource().perform_request(
        {"bk_tenant_id": "system", "show_all": True, "show_detail": False}
    )
    assert result == spaces
    assert result[0]["status"] == "disabled"


@pytest.mark.parametrize("show_all", [False, True])
def test_external_user_space_list_respects_visibility(spaces, monkeypatch, show_all):
    monkeypatch.setattr(module, "get_request", lambda **kwargs: SimpleNamespace(external_user="external-tester"))
    monkeypatch.setattr(module, "get_request_username", lambda: "tester")
    monkeypatch.setattr(module.SpaceApi, "list_spaces_dict", Mock(return_value=spaces))
    permission_filter = Mock()
    permission_filter.return_value.values_list.return_value.distinct.return_value = [-101, -102, -103, 2]
    monkeypatch.setattr(module.ExternalPermission.objects, "filter", permission_filter)
    result = module.ListSpacesResource().perform_request(
        {"bk_tenant_id": "system", "show_all": show_all, "show_detail": False}
    )
    assert [space["bk_biz_id"] for space in result] == ([-101, -102, -103, 2] if show_all else [-102, -103, 2])


def test_space_sql_includes_status(monkeypatch):
    cursor = MagicMock()
    cursor.description = [(name,) for name in ["id", "space_type_id", "space_id", "space_name", "space_uid", "status"]]
    cursor.fetchall.return_value = [(101, "bkci", "bkms-off", "off", "bkci__bkms-off", "disabled")]
    cursor.__enter__.return_value = cursor
    connection = SimpleNamespace(cursor=lambda: cursor)
    monkeypatch.setattr("bkmonitor.space.space_api.connections", {"monitor_api": connection})
    monkeypatch.setattr("bkmonitor.space.space_api.enrich_space_display_name", lambda space: None)
    result = InjectSpaceApi.list_spaces_dict(using_cache=False, filters={"status": "disabled"})
    assert "s.status," in cursor.execute.call_args.args[0]
    assert result[0]["status"] == "disabled"


def test_gateway_and_backend_route_agree(monkeypatch, settings):
    from pathlib import Path

    for name in ["DEFAULT_CRONTAB", "ACTION_TASK_CRONTAB", "LONG_TASK_CRONTAB"]:
        monkeypatch.setattr(settings, name, [], raising=False)
    from kernel_api.views.v3.meta import SetBkmsSpaceStatusViewSet
    from metadata.resources import SetBkmsSpaceStatusResource

    root = Path(__file__).resolve().parents[4]
    data = yaml.safe_load((root / "support-files/apigw/resources/internal/app/metadata.yaml").read_text())
    route = data["paths"]["/app/metadata/set_bkms_space_status/"]["post"]
    config = route["x-bk-apigateway-resource"]
    assert route["operationId"] == "metadata_set_bkms_space_status"
    assert config["backend"]["path"] == "/api/v3/meta/set_bkms_space_status/"
    assert config["authConfig"] == {
        "appVerifiedRequired": True,
        "userVerifiedRequired": False,
        "resourcePermissionRequired": True,
    }
    router = ResourceRouter()
    router.register("set_bkms_space_status", SetBkmsSpaceStatusViewSet)
    match = resolve("/set_bkms_space_status/", urlconf=tuple(router.urls))
    assert match.func.cls is SetBkmsSpaceStatusViewSet
    assert SetBkmsSpaceStatusViewSet.resource_routes[0].resource_class is SetBkmsSpaceStatusResource
