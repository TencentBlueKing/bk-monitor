from copy import deepcopy
import json

import pytest

from api.unify_query.default import QueryRawResource
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, QueryHelper, UnifyQuerySet
from bkmonitor.data_source.unify_query.query import UnifyQuery
from core.errors.api import BKAPIError
from monitor_web.grafana.resources.log import LogQueryResource


@pytest.fixture
def raw_backend(mocker):
    mocker.patch("monitor_web.grafana.resources.log.get_request_tenant_id", return_value="system")
    mocker.patch("bkmonitor.data_source.data_source.bk_biz_id_to_bk_tenant_id", return_value="system")
    mocker.patch("bkmonitor.data_source.unify_query.query.bk_biz_id_to_bk_tenant_id", return_value="system")
    mocker.patch("bkmonitor.data_source.unify_query.query.bk_biz_id_to_space_uid", return_value="bkcc__2")
    mocker.patch("bkmonitor.data_source.data_source.CustomEventDataSource.switch_unify_query", return_value=True)
    raw = mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_raw")
    count = mocker.patch.object(UnifyQuery, "query_reference", return_value=[{"_result_": 12345}])
    return raw, count


def params(**overrides):
    serializer = LogQueryResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "data_source_label": "custom",
            "data_type_label": "event",
            "result_table_id": "test_event",
            "start_time": 100,
            "end_time": 200,
            "limit": 1,
            "offset": 1,
            "filter_dict": {"event_name": "disk_event"},
            "where": [{"key": "status", "method": "eq", "value": ["active"]}],
            "query_string": "disk",
            **overrides,
        }
    )
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@pytest.mark.parametrize("total, records", [(0, []), (12345, []), (12345, [{"time": 150000}])])
def test_exact_total_skips_count_through_real_query_chain(raw_backend, total, records):
    raw, count = raw_backend
    raw.return_value = {"list": deepcopy(records), "total": total, "total_exact": True}

    result = LogQueryResource().perform_request(params())

    assert result["meta"]["total"] == total
    assert len(result["data"]) == len(records)
    count.assert_not_called()
    sent = raw.call_args.kwargs
    assert sent["query_list"][0]["exact_total"] is True
    assert "metric_merge" not in sent
    assert (sent["start_time"], sent["end_time"], sent["limit"], sent["_from"]) == ("100", "200", 1, 1)
    assert sent["query_list"][0]["query_string"] == "disk"
    assert sent["query_list"][0]["conditions"]
    # Validate the actual API serializer too: optional metric_merge and nested exact_total survive.
    serializer = QueryRawResource.RequestSerializer(data=sent)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data["query_list"][0]["exact_total"] is True
    assert "metric_merge" not in serializer.validated_data


@pytest.mark.parametrize(
    "response",
    [
        {"total": 10000},
        {"total": 10000, "total_exact": False},
        {"total": 10000, "total_exact": 1},
        {"total_exact": True},
        *[{"total": value, "total_exact": True} for value in [None, -1, True, "12345", 12345.0]],
    ],
)
def test_unconfirmed_total_uses_original_count(raw_backend, response):
    raw, count = raw_backend
    raw.return_value = {"list": [], **response}

    result = LogQueryResource().perform_request(params())

    assert result["meta"]["total"] == 12345
    count.assert_called_once()


def test_raw_and_fallback_count_share_filters_and_time_range(raw_backend, mocker):
    raw, count = raw_backend
    raw.return_value = {"list": []}
    build = mocker.spy(QueryHelper, "_build_unify_query")
    request = params(
        target=[{"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": 1}],
        group_by=["bk_target_ip", "bk_target_cloud_id"],
    )

    LogQueryResource().perform_request(request)

    raw_body, count_body = [call.args[0] for call in build.call_args_list]
    for field in ["filter_dict", "where", "query_string", "group_by"]:
        assert raw_body["query_configs"][0][field] == count_body["query_configs"][0][field]
    assert "192.0.2.10" in str(raw_body["query_configs"][0]["filter_dict"])
    assert raw_body["query_configs"][0]["group_by"] == []
    assert (raw_body["start_time"], raw_body["end_time"]) == (count_body["start_time"], count_body["end_time"])
    assert (raw_body["offset"], count_body["offset"]) == (1, 0)
    count.assert_called_once()


def test_normal_iteration_does_not_opt_in(raw_backend):
    raw, _ = raw_backend
    raw.return_value = {"list": []}
    queryset = UnifyQuerySet().scope(2).start_time(100000).end_time(200000)

    assert list(queryset.add_query(QueryConfigBuilder(("event", "custom")).table("test_event"))) == []

    sent = raw.call_args.kwargs
    assert sent["metric_merge"] == "a"
    assert "exact_total" not in sent["query_list"][0]


def test_legacy_es_query_path_preserves_count(raw_backend, mocker):
    raw, count = raw_backend
    mocker.patch.object(UnifyQuery, "use_unify_query", return_value=False)
    legacy = mocker.patch.object(UnifyQuery, "_query_log_using_datasource", return_value=([], 12345))

    result = LogQueryResource().perform_request(params())

    assert result["meta"]["total"] == 12345
    legacy.assert_called_once_with(100000, 200000, 1, 1, None)
    raw.assert_not_called()
    count.assert_called_once()


def test_count_failure_keeps_existing_page_length_fallback(raw_backend):
    raw, count = raw_backend
    raw.return_value = {"list": [{"time": 150000}]}
    count.side_effect = RuntimeError("count failed")

    result = LogQueryResource().perform_request(params())

    assert result["meta"]["total"] == 1


def test_non_es_contract_rejection_retries_original_raw_once(raw_backend):
    raw, count = raw_backend
    raw.side_effect = [
        BKAPIError(result=json.dumps({"error": "ES exact total request requires one non-aggregated ES raw branch"})),
        {"list": [{"time": 150000}], "total": 10000},
    ]

    result = LogQueryResource().perform_request(params())

    assert result["meta"]["total"] == 12345
    assert len(result["data"]) == 1
    assert raw.call_count == 2
    first, second = [call.kwargs for call in raw.call_args_list]
    assert first["query_list"][0]["exact_total"] is True
    assert "metric_merge" not in first
    expected = deepcopy(first)
    expected["query_list"][0].pop("exact_total")
    expected["metric_merge"] = "a"
    assert second == expected
    count.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout"),
        BKAPIError(result=json.dumps({"error": "partial shards failed"})),
        BKAPIError(result="upstream timeout"),
        BKAPIError(result=json.dumps(["unsupported"])),
    ],
)
def test_query_failure_is_not_retried_or_hidden(raw_backend, error):
    raw, count = raw_backend
    raw.side_effect = error

    with pytest.raises(type(error)) as raised:
        LogQueryResource().perform_request(params())

    assert raised.value is error
    raw.assert_called_once()
    count.assert_not_called()
