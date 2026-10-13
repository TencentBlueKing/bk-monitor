"""Original public V3 builders use the native product query, not a V4 catalog."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from iam import Resource

from bkmonitor.iam.resource import ApmApplication, RumApplication, GrafanaDashboard, Business
from bkmonitor.iam import definitions
from monitor_web.iam.views import ApmApplicationProvider, RumApplicationProvider


@pytest.mark.parametrize("product,provider", [
    (ApmApplication, ApmApplicationProvider), (RumApplication, RumApplicationProvider),
])
@pytest.mark.parametrize("found", [True, False])
def test_application_constructor_preserves_native_sdk_attributes(monkeypatch, product, provider, found):
    row = {"application_id": 7, "app_name": "app", "bk_biz_id": 2} if found else None
    query = Mock()
    query.filter.return_value.values.return_value.first.return_value = row
    monkeypatch.setattr(provider, "get_queryset", lambda: query)
    provider._get_app_simple_info_by_id_or_none.cache_clear()
    resource = product.create_simple_instance("7", {"custom": "retained-if-missing"})
    assert isinstance(resource, Resource)
    assert resource.system == product.system_id
    assert resource.attribute == ({
        "id": "7", "name": "app", "bk_biz_id": "2", "_bk_iam_path_": "/space,2/",
    } if found else {"custom": "retained-if-missing"})
    assert query.filter.call_count == (1 if found else 2)
    query.filter.assert_called_with(application_id="7")
    provider._get_app_simple_info_by_id_or_none.cache_clear()


def test_grafana_public_constructor_keeps_original_uid_and_title(monkeypatch):
    from monitor_web.iam import views
    manager = Mock()
    manager.filter.return_value.only.return_value.first.return_value = SimpleNamespace(title="title", org_id=10)
    monkeypatch.setattr(views.Dashboard, "objects", manager)
    monkeypatch.setattr(views, "get_org_by_id", lambda id: {"name": "2"})
    resource = GrafanaDashboard.create_simple_instance("uid")
    assert isinstance(resource, Resource)
    assert resource.id == "uid"
    assert resource.attribute == {"id": "uid", "name": "title", "bk_biz_id": "2", "_bk_iam_path_": "/space,2/"}
    manager.filter.assert_called_once_with(uid="uid")


def test_batch_product_queries_share_native_provider_extension(monkeypatch):
    query = Mock()
    query.filter.return_value.values.return_value = [{"application_id": 7, "app_name": "name", "bk_biz_id": 2}]
    monkeypatch.setattr(RumApplicationProvider, "get_queryset", lambda: query)
    assert RumApplication.batch_get_display_names({"7"}) == {"7": "name"}
    assert RumApplication.batch_get_parent({"7"}) == {"7": "2"}
    assert Business.batch_get_parent({"2"}) == {}
    assert RumApplicationProvider.batch_get_parent.__func__ is ApmApplicationProvider.batch_get_parent.__func__


def test_runtime_model_metadata_is_derived_from_public_v3_definitions():
    from bkmonitor.iam.action import ActionEnum, ActionMeta, canonicalize_action_id
    from bkmonitor.iam.resource import ResourceEnum, ResourceMeta
    for action in vars(ActionEnum).values():
        if isinstance(action, ActionMeta):
            item = definitions.actions[canonicalize_action_id(action.id)]
            assert item.name == action.name
            assert item.description == action.description
            assert item.extensions["v3"] == {
                "action_id": action.id, "type": action.type, "version": action.version,
                "name_en": action.name_en, "description_en": action.description_en,
                "related_actions": action.related_actions,
            }
    for resource in vars(ResourceEnum).values():
        if isinstance(resource, type) and issubclass(resource, ResourceMeta):
            item = definitions.resource_types[resource.id]
            assert item.name == resource.name
            assert item.ancestor == (resource.parent_resource.id if resource.parent_resource else "")
            assert item.extensions["v3"]["related_instance_selections"] == resource.related_instance_selections
