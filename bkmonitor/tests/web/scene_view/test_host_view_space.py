"""Host view configuration keeps its space while metric metadata uses the related business."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db.models import Q
from rest_framework.exceptions import NotFound

from bkm_space.errors import NoRelatedResourceError
from bkmonitor.share.handler import HostApiAuthChecker
from core.errors.share import ParamsPermissionDeniedError
from monitor_web.grafana.resources import unify_query as graph
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
    def filter(self, *conditions, **kwargs):
        def matches(row, condition):
            if isinstance(condition, Q):
                values = [matches(row, child) for child in condition.children]
                result = any(values) if condition.connector == Q.OR else all(values)
                return not result if condition.negated else result
            field, value = condition
            name, _, lookup = field.partition("__")
            actual = getattr(row, name)
            if lookup == "in":
                return actual in value
            if lookup == "startswith":
                return actual.startswith(value)
            return actual == value

        return Rows(row for row in self if matches(row, Q(*conditions, **kwargs)))

    def only(self, *_fields):
        return self

    def first(self):
        return self[0] if self else None

    def values(self, *fields):
        return [{field: getattr(row, field) for field in fields} for row in self]

    def values_list(self, *fields):
        return [tuple(getattr(row, field) for field in fields) for row in self]


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
                    unit="percentunit",
                    data_label="",
                    related_id="",
                    extend_fields={},
                )
            )
    metric_filter = Mock(side_effect=lambda *args, **kwargs: metric_rows.filter(*args, **kwargs))
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
    return SimpleNamespace(
        stored=stored, metric_rows=metric_rows, metric_filter=metric_filter, tenant=tenant, ipv6=ipv6
    )


@pytest.fixture
def graph_backend(host_views, monkeypatch):
    sources = []

    def data_source(**kwargs):
        sources.append(deepcopy(kwargs))
        return SimpleNamespace(**kwargs)

    query = Mock()
    query.query_data_with_stat.side_effect = lambda **_kwargs: {
        "series": [{"_time_": 60_000, "_result_": 75.0}],
        "series_stat": {},
    }
    query_factory = Mock(return_value=query)
    monkeypatch.setattr(graph, "UnifyQuery", query_factory)
    monkeypatch.setattr(graph, "load_data_source", lambda *_args: data_source)
    monkeypatch.setattr(graph, "get_cookies_filter", lambda: {})
    monkeypatch.setattr(graph, "safe_push_to_gateway", Mock())
    monkeypatch.setattr(graph, "unify_query_count", Mock())
    monkeypatch.setattr(graph, "model_to_dict", lambda metric: deepcopy(vars(metric)))
    monkeypatch.setattr(graph, "bk_biz_id_to_bk_tenant_id", host_views.tenant)
    monkeypatch.setattr(graph, "is_ipv6_biz", host_views.ipv6)
    monkeypatch.setattr(graph, "validate_bk_biz_id", host.validate_bk_biz_id, raising=False)
    return SimpleNamespace(query=query_factory, sources=sources)


def graph_params(space_id, query_configs):
    configs = deepcopy(query_configs)
    for config in configs:
        config["interval"] = 60
        config["group_by"] = []
        config["functions"] = []
        config["where"] = []
        config["filter_dict"] = {"targets": [{"bk_host_id": 101}]}
        for metric in config["metrics"]:
            metric["method"] = "AVG"
    return {
        "bk_biz_id": space_id,
        "query_configs": configs,
        "expression": "A",
        "function": {},
        "functions": [],
        "target": [],
        "post_query_filter_dict": {},
        "promql_multi_expression": [],
        "start_time": 0,
        "end_time": 120,
        "limit": 1000,
        "slimit": 1000,
        "down_sample_range": "",
        "format": "time_series",
        "type": "range",
        "query_method": "query_data_with_stat",
        "unit": "",
        "with_metric": True,
    }


def graph_config(table="system.cpu_summary", field="usage", **overrides):
    return {
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "table": table,
        "metrics": [{"field": field, "method": "AVG", "alias": "A"}],
        "filter_dict": {"targets": [{"bk_host_id": 101}]},
        **overrides,
    }


@pytest.mark.parametrize("view_id,panel_resource,order_resource", VIEW_RESOURCES)
@pytest.mark.parametrize("space_id", SPACES)
@pytest.mark.parametrize("metric_owner", [0, 2])
def test_panels_to_graph_preserves_metric_unit_and_request_scope(
    host_views, graph_backend, view_id, panel_resource, order_resource, space_id, metric_owner
):
    field = ("usage" if view_id == "host" else "cpu_usage_pct") if metric_owner == 0 else f"{view_id}_2"
    order = request(order_resource, {"bk_biz_id": space_id})
    for row in order:
        for panel in row["panels"]:
            if panel["id"].endswith(f".{field}"):
                panel["hidden"] = False
    request(
        view_resources.UpdateSceneViewResource,
        {
            "bk_biz_id": space_id,
            "scene_id": "host",
            "type": "detail",
            "id": view_id,
            "name": view_id,
            "config": {"order": order},
        },
    )
    rows = request(panel_resource, {"bk_biz_id": space_id})
    panel = next(panel for row in rows for panel in row["panels"] if panel["id"].endswith(f".{field}"))
    configs = panel["targets"][0]["data"]["query_configs"]
    params = graph_params(space_id, configs)
    original_scope = params["bk_biz_id"]

    result = graph.GraphUnifyQueryResource().perform_request(params)

    assert result["series"] and {series["unit"] for series in result["series"]} == {"percentunit"}
    assert len(result["metrics"]) == 1
    assert result["metrics"][0]["metric_field"] == field
    assert result["metrics"][0]["default_dimensions"] == ["bk_host_id"]
    assert params["bk_biz_id"] == original_scope == space_id
    assert graph_backend.query.call_args.kwargs["bk_biz_id"] == space_id
    assert graph_backend.sources[0]["bk_biz_id"] == space_id
    if space_id > 0:
        assert host_views.metric_filter.call_args.kwargs["bk_biz_id__in"] == [2, 0]
    else:
        assert host_views.metric_filter.call_args.kwargs["bk_biz_id"] == 2


def test_graph_metadata_does_not_include_other_business_or_tenant(host_views, graph_backend):
    other_tenant = deepcopy(host_views.metric_rows[0])
    other_tenant.bk_tenant_id = "other"
    other_tenant.metric_field = "other_tenant"
    host_views.metric_rows.append(other_tenant)
    configs = [graph_config(field=field) for field in ("host_2", "host_3", "other_tenant")]

    result = graph.GraphUnifyQueryResource().perform_request(graph_params(-101, configs))

    assert [metric["metric_field"] for metric in result["metrics"]] == ["host_2"]
    assert {series["unit"] for series in result["series"]} == {""}


@pytest.mark.parametrize(
    "overrides",
    [
        {"table": "custom.cpu"},
        {"data_source_label": "custom"},
        {"data_source_label": "bk_apm"},
        {"data_type_label": "log"},
        {"data_label": "system_alias"},
        {"data_source_label": "bk_log_search", "index_set_id": "logs"},
        {"table": "systematic.cpu"},
    ],
)
def test_non_host_graph_metadata_keeps_original_space(host_views, graph_backend, monkeypatch, overrides):
    config = graph_config(field="space_metric", **overrides)
    metric = deepcopy(host_views.metric_rows[0])
    metric.bk_biz_id = -101
    metric.metric_field = "space_metric"
    metric.result_table_id = config["table"]
    metric.data_source_label = config["data_source_label"]
    metric.data_type_label = config["data_type_label"]
    metric.data_label = config.get("data_label", "")
    metric.related_id = config.get("index_set_id", "")
    metric.unit = "space_unit"
    related_metric = deepcopy(metric)
    related_metric.bk_biz_id = 2
    related_metric.unit = "related_unit"
    host_views.metric_rows.extend([metric, related_metric])
    resolve = Mock(side_effect=AssertionError("Non-host metadata must keep its space"))
    monkeypatch.setattr(graph, "validate_bk_biz_id", resolve, raising=False)

    result = graph.GraphUnifyQueryResource().perform_request(graph_params(-101, [config]))

    assert [metric["unit"] for metric in result["metrics"]] == ["space_unit"]
    assert {series["unit"] for series in result["series"]} == {"space_unit"}
    assert host_views.metric_filter.call_args.kwargs["bk_biz_id__in"] == [-101, 0]
    resolve.assert_not_called()


def test_mixed_graph_metadata_keeps_each_query_in_its_business(host_views, graph_backend):
    metric = deepcopy(host_views.metric_rows[0])
    metric.bk_biz_id = -101
    metric.result_table_id = "custom.cpu"
    metric.metric_field = "space_metric"
    metric.unit = "space_unit"
    related_metric = deepcopy(metric)
    related_metric.bk_biz_id = 2
    related_metric.unit = "related_unit"
    host_views.metric_rows.extend([metric, related_metric])
    configs = [graph_config(field="host_2"), graph_config(table="custom.cpu", field="space_metric")]

    result = graph.GraphUnifyQueryResource().perform_request(graph_params(-101, configs))

    assert {(metric["metric_field"], metric["unit"]) for metric in result["metrics"]} == {
        ("host_2", "percentunit"),
        ("space_metric", "space_unit"),
    }
    assert {series["unit"] for series in result["series"]} == {""}
    assert all(source["bk_biz_id"] == -101 for source in graph_backend.sources)


def test_related_graph_metadata_is_limited_to_host_metric_categories(host_views, graph_backend):
    metric = deepcopy(host_views.metric_rows[1])
    metric.result_table_label = "application"
    metric.metric_field = "application_metric"
    host_views.metric_rows.append(metric)

    result = graph.GraphUnifyQueryResource().perform_request(
        graph_params(-101, [graph_config(field="application_metric")])
    )

    assert result["metrics"] == []
    assert {series["unit"] for series in result["series"]} == {""}


def test_original_space_system_application_metadata_takes_precedence(host_views, graph_backend):
    metric = deepcopy(host_views.metric_rows[0])
    metric.bk_biz_id = -101
    metric.result_table_label = "application"
    metric.metric_field = "application_metric"
    metric.unit = "space_unit"
    related_metric = deepcopy(metric)
    related_metric.bk_biz_id = 2
    related_metric.result_table_label = "os"
    related_metric.unit = "related_unit"
    host_views.metric_rows.extend([metric, related_metric])

    result = graph.GraphUnifyQueryResource().perform_request(
        graph_params(-101, [graph_config(field="application_metric")])
    )

    assert [metric["unit"] for metric in result["metrics"]] == ["space_unit"]
    assert result["metrics"][0]["default_dimensions"] == ["bk_target_ip", "bk_target_cloud_id"]
    assert {series["unit"] for series in result["series"]} == {"space_unit"}


@pytest.mark.parametrize("query_count", [1, 20])
def test_graph_metadata_queries_stay_bounded(host_views, graph_backend, query_count):
    configs = [graph_config(field="host_2") for _ in range(query_count)]

    result = graph.GraphUnifyQueryResource().perform_request(graph_params(-101, configs))

    assert [metric["metric_field"] for metric in result["metrics"]] == ["host_2"]
    assert host_views.metric_filter.call_count <= 2


def test_unrelated_graph_space_keeps_public_metadata_without_changing_scope(host_views, graph_backend):
    params = graph_params(-999, [graph_config()])

    result = graph.GraphUnifyQueryResource().perform_request(params)

    assert [metric["metric_field"] for metric in result["metrics"]] == ["usage"]
    assert {series["unit"] for series in result["series"]} == {"percentunit"}
    assert params["bk_biz_id"] == graph_backend.query.call_args.kwargs["bk_biz_id"] == -999
    assert host_views.metric_filter.call_args.kwargs["bk_biz_id__in"] == [-999, 0]


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


def share_checker(space_id):
    checker = object.__new__(HostApiAuthChecker)
    checker.bk_biz_id = space_id
    checker.bk_tenant_id = "tenant"
    checker.token = SimpleNamespace(namespaces=[f"biz#{space_id}"])
    checker.scope = {"version": 1, "target_type": "host", "bk_host_id": 101}
    checker.allowed_hosts = [SimpleNamespace(bk_host_id=101, ip="192.0.2.1", bk_cloud_id=0)]
    return checker


def share_query(view_id, space_id):
    panel = host.get_panels(SimpleNamespace(id=view_id, bk_biz_id=space_id))[0]
    query = deepcopy(panel["targets"][0]["data"]["query_configs"][0])
    query["filter_dict"]["targets"] = [{"bk_host_id": 101}]
    return query


@pytest.mark.parametrize("view_id", ["host", "process"])
@pytest.mark.parametrize("space_id", SPACES)
@pytest.mark.parametrize("metric_owner", [0, 2, 3])
def test_share_metric_whitelist_uses_related_business_without_changing_scope(
    host_views, view_id, space_id, metric_owner
):
    checker = share_checker(space_id)
    original_scope = deepcopy(checker.scope)
    query = share_query(view_id, space_id)
    if metric_owner:
        query["metrics"][0]["field"] = f"{view_id}_{metric_owner}"

    if metric_owner == 3:
        with pytest.raises(ParamsPermissionDeniedError):
            checker.query_configs_check([query])
    else:
        checker.query_configs_check([query])

    assert checker.bk_biz_id == space_id
    assert checker.token.namespaces == [f"biz#{space_id}"]
    assert checker.scope == original_scope
    assert host_views.metric_filter.call_args.kwargs["bk_biz_id__in"] == [0, 2]
    assert host_views.metric_filter.call_args.kwargs["bk_tenant_id"] == "tenant"


@pytest.mark.parametrize("view_id", ["host", "process"])
@pytest.mark.parametrize("space_id", SPACES)
def test_share_business_metrics_keep_host_target_restrictions(host_views, view_id, space_id):
    checker = share_checker(space_id)
    query = share_query(view_id, space_id)
    query["metrics"][0]["field"] = f"{view_id}_2"
    query["filter_dict"]["targets"] = [{"bk_host_id": 102}]

    with pytest.raises(ParamsPermissionDeniedError):
        checker.query_configs_check([query])

    assert checker.bk_biz_id == space_id
    assert checker.token.namespaces == [f"biz#{space_id}"]


def test_share_unrelated_space_returns_resource_unavailable(host_views):
    checker = share_checker(-999)

    with pytest.raises(NotFound) as error:
        checker.query_configs_check([])

    assert error.value.status_code == 404
    assert checker.bk_biz_id == -999
    assert checker.token.namespaces == ["biz#-999"]
    host_views.metric_filter.assert_not_called()
