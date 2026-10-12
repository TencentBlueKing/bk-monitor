from copy import deepcopy

import pytest
from django.utils import tree

from bkmonitor.data_source import filter_dict_to_q
from bkmonitor.data_source.data_source import conditions_to_q
from core.drf_resource import resource
from monitor_web.grafana.resources.log import LogQueryResource
from monitor_web.grafana.resources.unify_query import UnifyQueryRawResource


def log_params(**overrides):
    data = {
        "bk_biz_id": 2,
        "data_source_label": "custom",
        "data_type_label": "event",
        "result_table_id": "test_event",
        "start_time": 100,
        "end_time": 200,
        "group_by": ["bk_target_ip", "bk_target_cloud_id"],
        "filter_dict": {"event_name": "disk_event"},
        "where": [{"key": "status", "method": "eq", "value": ["active"]}],
        "query_string": "disk",
        "limit": 1,
        "offset": 1,
        **overrides,
    }
    serializer = LogQueryResource.RequestSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def matches(condition, record):
    """Evaluate equality fixtures against the real query builder's compiled conditions."""
    children = []
    for child in condition.children:
        if isinstance(child, tree.Node):
            children.append(matches(child, record))
        else:
            key, values = child
            field, lookup = key.rsplit("__", 1)
            assert lookup == "eq"
            children.append(str(record.get(field)) in [str(value) for value in values])
    result = all(children) if condition.connector == "AND" else any(children)
    return not result if condition.negated else result


@pytest.fixture
def log_backend(mocker):
    source = mocker.Mock(DEFAULT_TIME_FIELD="time")
    mocker.patch("monitor_web.grafana.resources.log.load_data_source", return_value=source)
    mocker.patch("monitor_web.grafana.resources.log.get_request_tenant_id", return_value="system")
    queries = []
    records = [
        {"id": "outside", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "2"},
        {"id": "first", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "1"},
        {"id": "second", "bk_target_ip": "192.0.2.20", "bk_target_cloud_id": "2"},
        {"id": "wrong-cloud", "bk_target_ip": "192.0.2.20", "bk_target_cloud_id": "1"},
        {"id": "wrong-event", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "1", "event_name": "other"},
        {"id": "recovered", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "1", "status": "recovered"},
    ]
    records = [{"time": 150, "event_name": "disk_event", "status": "active", **row} for row in records]

    def execute(table_id, query_body):
        queries.append(deepcopy(query_body))
        config = query_body["query_configs"][0]
        condition = filter_dict_to_q(config["filter_dict"]) & conditions_to_q(config["where"])
        selected = [row for row in records if matches(condition, row)]
        if config["metrics"]:
            return [{"_result_": len(selected)}]
        offset = query_body["offset"]
        return deepcopy(selected[offset : offset + query_body["limit"]])

    query = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute)
    return source, query, queries


def test_log_target_filters_before_pagination_and_count(log_backend):
    _, _, queries = log_backend
    target = [
        [
            {
                "field": "host_ip",
                "value": [
                    {"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": 1},
                    {"bk_target_ip": "192.0.2.20", "bk_target_cloud_id": 2},
                ],
            }
        ]
    ]
    params = log_params(target=target)
    preview = {
        "bk_biz_id": params["bk_biz_id"],
        "target": target,
        "target_filter_type": "query",
        "query_configs": [{"group_by": params["group_by"], "filter_dict": {}}],
    }
    assert UnifyQueryRawResource.get_target_instance(preview)

    result = LogQueryResource().perform_request(params)

    assert [row["id"] for row in result["data"]] == ["second"]
    assert result["meta"]["total"] == 2
    assert params["filter_dict"]["target"] == preview["query_configs"][0]["filter_dict"]["target"]
    assert len(queries) == 2
    assert queries[0]["offset"] == 1
    assert queries[1]["offset"] == 0
    for body in queries:
        assert (body["start_time"], body["end_time"]) == (100_000, 200_000)
        assert body["query_configs"][0]["query_string"] == "disk"
        assert body["query_configs"][0]["group_by"] == []  # Parsing context must not aggregate raw logs.
    assert queries[0]["query_configs"][0]["filter_dict"] == queries[1]["query_configs"][0]["filter_dict"]
    assert queries[0]["query_configs"][0]["where"] == queries[1]["query_configs"][0]["where"]


def test_large_target_is_always_filtered_in_query(log_backend):
    _, _, queries = log_backend
    params = log_params(target=[{"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": cloud} for cloud in range(100)])

    result = LogQueryResource().perform_request(params)

    assert result["meta"]["total"] == 2
    assert len(params["filter_dict"]["target"]) == 100
    assert all(body["query_configs"][0]["filter_dict"] for body in queries)


def test_events_outside_selected_target_return_empty_details_and_count(log_backend):
    assert LogQueryResource().perform_request(log_params())["meta"]["total"] == 4

    result = LogQueryResource().perform_request(
        log_params(target=[{"bk_target_ip": "192.0.2.30", "bk_target_cloud_id": 1}])
    )

    assert result["data"] == []
    assert result["meta"]["total"] == 0


@pytest.mark.parametrize("target", [[], [[]]])
def test_missing_target_preserves_unrestricted_query(log_backend, mocker, target):
    parse = mocker.patch("core.drf_resource.resource.cc.parse_topo_target")

    result = LogQueryResource().perform_request(log_params(target=target))

    assert result["meta"]["total"] == 4
    parse.assert_not_called()


@pytest.mark.parametrize("group_by", [[], ["status"]])
def test_no_target_dimensions_keeps_preview_semantics(log_backend, group_by):
    params = log_params(target=[{"bk_host_id": 10}], group_by=group_by)

    result = LogQueryResource().perform_request(params)

    assert result["meta"]["total"] == 4
    assert "target" not in params["filter_dict"]


@pytest.mark.parametrize(
    "dimension", ["bk_host_id", "service_instance_id", "bk_target_service_instance_id", "bk_target_ip"]
)
@pytest.mark.parametrize("data_format", ["strategy", "scene_view", "table"])
def test_empty_topology_returns_no_logs_without_query(log_backend, mocker, dimension, data_format):
    _, query, _ = log_backend
    mocker.patch("core.drf_resource.api.cmdb.get_host_by_topo_node", return_value=[])
    mocker.patch("core.drf_resource.api.cmdb.get_service_instance_ids_by_topo_node", return_value=[])
    params = log_params(
        target=[[{"value": [{"bk_obj_id": "module", "bk_inst_id": 10}]}]], group_by=[dimension], data_format=data_format
    )
    assert resource.cc.parse_topo_target(2, params["group_by"], params["target"]) is None
    assert not UnifyQueryRawResource.get_target_instance(
        {
            "bk_biz_id": 2,
            "target": params["target"],
            "query_configs": [{"group_by": [dimension]}],
        }
    )

    result = LogQueryResource().perform_request(params)

    query.assert_not_called()
    if data_format == "strategy":
        assert result["data"] == []
        assert result["meta"]["total"] == 0
    elif data_format == "scene_view":
        assert result["data"] == []
        assert result["total"] == 0
    else:
        assert result[0]["rows"] == []


@pytest.mark.parametrize("dimension", ["bk_host_id", "service_instance_id", "bk_target_service_instance_id"])
def test_host_and_service_targets_use_preview_identity(log_backend, dimension):
    params = log_params(target=[{dimension: 101}], group_by=[dimension])

    LogQueryResource().perform_request(params)

    assert params["filter_dict"]["target"] == [{dimension: ["101"]}]


def test_legacy_log_source_receives_same_target_filter(log_backend, mocker):
    source, query, _ = log_backend
    source.return_value.query_log.return_value = ([], 0)
    mocker.patch("monitor_web.grafana.resources.log.GrayUnifyQueryDataSources", [])
    params = log_params(target=[{"bk_host_id": 101}], group_by=["bk_host_id"])

    LogQueryResource().perform_request(params)

    assert source.call_args.kwargs["filter_dict"]["target"] == [{"bk_host_id": ["101"]}]
    source.return_value.query_log.assert_called_once_with(start_time=100_000, end_time=200_000, limit=1, offset=1)
    query.assert_not_called()
