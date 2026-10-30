"""Host view configuration keeps its space while metric metadata uses the related business."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import NotFound

from bkm_space.errors import NoRelatedResourceError
from monitor_web.scene_view.builtin import host
from monitor_web.scene_view.resources import host as host_resources
from monitor_web.scene_view.resources import view as view_resources


VIEW_RESOURCES = [
    ("host", host_resources.GetHostViewsPanelsResource, host_resources.GetHostViewsPanelsOrderResource),
    ("process", host_resources.GetProcessViewsPanelsResource, host_resources.GetProcessViewsPanelsOrderResource),
]
SPACES = (2, -101, -102)


def request(resource_class, params):
    serializer = resource_class.RequestSerializer(data=params)
    serializer.is_valid(raise_exception=True)
    return resource_class().perform_request(serializer.validated_data)


class Rows(list):
    def filter(self, **kwargs):
        def matches(row):
            for field, value in kwargs.items():
                name, _, lookup = field.partition("__")
                actual = getattr(row, name)
                if lookup == "in":
                    if actual not in value:
                        return False
                elif lookup == "startswith":
                    if not actual.startswith(value):
                        return False
                elif actual != value:
                    return False
            return True

        return Rows(row for row in self if matches(row))

    def only(self, *_fields):
        return self

    def first(self):
        return self[0] if self else None

    def values(self, *fields):
        return [{field: getattr(row, field) for field in fields} for row in self]


@pytest.fixture
def host_views(monkeypatch):
    stored = {}

    class View(SimpleNamespace):
        def save(self):
            stored[self.bk_biz_id, self.id] = self

    class ViewManager:
        def filter(self, **kwargs):
            return Rows(stored.values()).filter(**kwargs)

        def bulk_create(self, views):
            for view in views:
                view.save()

        def get(self, **kwargs):
            rows = self.filter(**kwargs)
            assert len(rows) == 1
            return rows[0]

    View.objects = ViewManager()

    def related_business(space_id):
        if space_id not in SPACES:
            raise NoRelatedResourceError("Space has no related business")
        return 2

    metric_rows = Rows()
    for view_id, table, label, field in (
        ("host", "system.cpu_summary", "os", "usage"),
        ("process", "system.proc", "host_process", "cpu_usage_pct"),
    ):
        for business in (0, 2, 3):
            metric_rows.append(
                SimpleNamespace(
                    bk_tenant_id="tenant",
                    bk_biz_id=business,
                    result_table_label=label,
                    result_table_id=table,
                    metric_field=field if business == 0 else f"{view_id}_{business}",
                    metric_field_name=f"{view_id}_{business}",
                    data_source_label="bk_monitor",
                    data_type_label="time_series",
                    default_dimensions=["bk_target_ip", "bk_target_cloud_id", "bk_host_id"],
                )
            )
    metric_filter = Mock(side_effect=lambda **kwargs: metric_rows.filter(**kwargs))
    tenant = Mock(return_value="tenant")
    ipv6 = Mock(side_effect=lambda business: business == 2)
    monkeypatch.setattr(host, "SceneViewModel", View)
    monkeypatch.setattr(view_resources, "SceneViewModel", View)
    monkeypatch.setattr(host.MetricListCache, "objects", SimpleNamespace(filter=metric_filter))
    monkeypatch.setattr(host, "bk_biz_id_to_bk_tenant_id", tenant)
    monkeypatch.setattr(host, "is_ipv6_biz", ipv6)
    monkeypatch.setattr(host_resources, "validate_bk_biz_id", related_business)
    monkeypatch.setattr(host, "validate_bk_biz_id", related_business, raising=False)
    monkeypatch.setattr(host.HostBuiltinProcessor, "builtin_views", None)
    monkeypatch.setattr(view_resources, "create_default_views", host.HostBuiltinProcessor.create_default_views)
    monkeypatch.setattr(view_resources, "create_or_update_view", host.HostBuiltinProcessor.create_or_update_view)
    monkeypatch.setattr(view_resources, "get_view_config", host.HostBuiltinProcessor.get_view_config)
    monkeypatch.setattr(view_resources, "post_handle_view_config", lambda *_args: None)
    monkeypatch.setattr(
        view_resources.GetSceneViewResource, "request", lambda self, params: request(type(self), params)
    )
    return SimpleNamespace(stored=stored, metric_filter=metric_filter, tenant=tenant, ipv6=ipv6)


@pytest.mark.parametrize("view_id,panel_resource,order_resource", VIEW_RESOURCES)
@pytest.mark.parametrize("space_id", SPACES)
def test_save_read_and_reset_are_isolated_by_original_space(
    host_views, view_id, panel_resource, order_resource, space_id
):
    defaults = {scope: request(order_resource, {"bk_biz_id": scope}) for scope in SPACES}
    default_panels = request(panel_resource, {"bk_biz_id": space_id})
    metric_id = next(panel["id"] for row in defaults[space_id] for panel in row["panels"] if "system." in panel["id"])
    custom_order = [{"id": "custom_group", "title": "Custom", "panels": [{"id": metric_id, "hidden": True}]}]

    def save(order):
        return request(
            view_resources.UpdateSceneViewResource,
            {
                "bk_biz_id": space_id,
                "scene_id": "host",
                "type": "detail",
                "id": view_id,
                "name": view_id,
                "config": {"order": deepcopy(order)},
            },
        )

    assert save(custom_order) == view_id
    assert request(order_resource, {"bk_biz_id": space_id})[0]["id"] == "custom_group"
    assert request(order_resource, {"bk_biz_id": space_id})[0]["panels"][0]["hidden"] is True
    assert request(panel_resource, {"bk_biz_id": space_id})[0]["panels"] == []
    for other in set(SPACES) - {space_id}:
        assert request(order_resource, {"bk_biz_id": other}) == defaults[other]

    assert save([]) == view_id
    assert request(order_resource, {"bk_biz_id": space_id}) == defaults[space_id]
    assert request(panel_resource, {"bk_biz_id": space_id}) == default_panels
    for other in set(SPACES) - {space_id}:
        assert request(order_resource, {"bk_biz_id": other}) == defaults[other]
    assert set(host_views.stored) == {(scope, view) for scope in SPACES for view in ("host", "process")}


@pytest.mark.parametrize("view_id", ["host", "process"])
@pytest.mark.parametrize("space_id", SPACES)
@pytest.mark.parametrize("ipv6_enabled", [False, True])
def test_metric_metadata_and_ipv6_mode_use_related_business(host_views, view_id, space_id, ipv6_enabled):
    host_views.ipv6.side_effect = lambda business: ipv6_enabled and business == 2
    panels = host.get_panels(SimpleNamespace(id=view_id, bk_biz_id=space_id))

    assert len(panels) == 2
    ignored_dimensions = ["bk_target_ip", "bk_target_cloud_id"] if ipv6_enabled else ["bk_host_id"]
    assert all(panel["targets"][0]["ignore_group_by"] == ignored_dimensions for panel in panels)
    assert host_views.metric_filter.call_args.kwargs["bk_biz_id__in"] == [0, 2]
    host_views.tenant.assert_called_once_with(2)
    assert [call.args for call in host_views.ipv6.call_args_list] == [(2,), (2,)]


@pytest.mark.parametrize("view_id,panel_resource,order_resource", VIEW_RESOURCES)
def test_unrelated_space_is_rejected_before_creating_views(host_views, view_id, panel_resource, order_resource):
    params = {"bk_biz_id": -999}
    for resource_class, request_params in (
        (panel_resource, params),
        (order_resource, params),
        (view_resources.GetSceneViewResource, {**params, "scene_id": "host", "type": "detail", "id": view_id}),
    ):
        with pytest.raises(NotFound) as error:
            request(resource_class, request_params)
        assert error.value.status_code == 404
        assert host_views.stored == {}
        host_views.metric_filter.assert_not_called()


@pytest.mark.parametrize("scene_id,view_id", [("custom", "host"), ("host", "custom")])
def test_generic_view_validation_preserves_other_scenes_and_ids(host_views, scene_id, view_id):
    serializer = view_resources.GetSceneViewResource.RequestSerializer(
        data={"bk_biz_id": -999, "scene_id": scene_id, "type": "detail", "id": view_id}
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["bk_biz_id"] == -999
