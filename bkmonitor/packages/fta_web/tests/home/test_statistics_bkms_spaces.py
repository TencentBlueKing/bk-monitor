from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fta_web.home import resources as module
from monitor_web.commons.biz import resources as commons


@pytest.mark.parametrize("external", [False, True])
def test_statistics_cache_and_search_use_same_visible_spaces(monkeypatch, external):
    spaces = [
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -101,
            "space_type_id": "bkci",
            "space_id": "bkms-off",
            "space_name": "project-off",
            "status": "disabled",
        },
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -102,
            "space_type_id": "bkci",
            "space_id": "bkms-on",
            "space_name": "project-on",
            "status": "normal",
        },
        {
            "bk_tenant_id": "system",
            "bk_biz_id": -103,
            "space_type_id": "bkci",
            "space_id": "other-off",
            "space_name": "project-other",
            "status": "disabled",
        },
    ]
    permission = Mock()
    permission.filter_space_list_by_action.return_value = spaces
    monkeypatch.setattr(commons, "Permission", Mock(return_value=permission))
    request = SimpleNamespace(external_user="external-tester") if external else None
    monkeypatch.setattr(commons, "get_request", lambda **kwargs: request)
    monkeypatch.setattr(commons, "get_request_username", lambda: "tester")
    monkeypatch.setattr(commons.SpaceApi, "list_spaces_dict", Mock(return_value=spaces))
    external_permission = Mock()
    external_permission.return_value.values_list.return_value.distinct.return_value = [-101, -102, -103]
    monkeypatch.setattr(commons.ExternalPermission.objects, "filter", external_permission)

    def list_spaces(**kwargs):
        return commons.ListSpacesResource().perform_request(
            {"bk_tenant_id": kwargs.get("bk_tenant_id", "system"), "show_all": False, "show_detail": False}
        )

    reader = Mock(side_effect=list_spaces)
    monkeypatch.setattr(module, "resource", SimpleNamespace(commons=SimpleNamespace(list_spaces=reader)))
    monkeypatch.setattr(
        module, "api", SimpleNamespace(bk_login=SimpleNamespace(list_tenant=lambda: [{"id": "system"}]))
    )
    cached = module.StatisticsResource.get_space_data_by_cache()
    reader.assert_called_once_with()
    queried = module.StatisticsResource.get_space_data_by_api()
    assert cached["allowed_biz_ids"] == queried["allowed_biz_ids"] == {-102, -103}
    assert cached["biz_id__space_map"] == {}
    assert module.StatisticsResource._filter_by_search_keyword(
        {"search": "project"}, queried["allowed_biz_ids"], queried["biz_id__space_map"]
    ) == {-102, -103}

    spaces[0]["status"] = "normal"
    assert module.StatisticsResource.get_space_data_by_cache()["allowed_biz_ids"] == {-101, -102, -103}
    assert module.StatisticsResource.get_space_data_by_api()["allowed_biz_ids"] == {-101, -102, -103}
