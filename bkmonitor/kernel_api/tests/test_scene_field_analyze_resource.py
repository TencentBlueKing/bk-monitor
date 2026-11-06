"""场景化字段分析 MCP Resource 测试。"""

from unittest.mock import Mock

from django.test import override_settings

from core.drf_resource import api
from kernel_api.resource.log_search import FieldAnalyzeResource


SCENE_CONDITIONS = [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]]


def build_request(**kwargs):
    return {
        "bk_biz_id": 2,
        "field_name": "level",
        "start_time": "1710000000",
        "end_time": "1710003600",
        **kwargs,
    }


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_serializer_requires_target():
    serializer = FieldAnalyzeResource.RequestSerializer(data=build_request())

    assert not serializer.is_valid()
    assert "index_set_id" in serializer.errors


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_serializer_accepts_scene_target():
    serializer = FieldAnalyzeResource.RequestSerializer(
        data=build_request(target_type="scene", table_id_conditions=SCENE_CONDITIONS)
    )

    assert serializer.is_valid(), serializer.errors


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_serializer_rejects_scene_conditions():
    serializer = FieldAnalyzeResource.RequestSerializer(
        data=build_request(
            target_type="scene",
            table_id_conditions=SCENE_CONDITIONS,
            conditions={"field_list": [], "condition_list": []},
        )
    )

    assert not serializer.is_valid()
    assert "conditions" in serializer.errors


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_serializer_rejects_scene_without_conditions():
    serializer = FieldAnalyzeResource.RequestSerializer(data=build_request(target_type="scene"))

    assert not serializer.is_valid()
    assert "table_id_conditions" in serializer.errors


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_serializer_rejects_time_span_over_one_day():
    serializer = FieldAnalyzeResource.RequestSerializer(data=build_request(index_set_id=123, end_time="1710086401"))

    assert not serializer.is_valid()


def test_scene_request_routes_to_log_platform(monkeypatch):
    scene_analyze = Mock(return_value={"series": []})
    monkeypatch.setattr(api.log_search, "scene_field_analyze", scene_analyze)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = FieldAnalyzeResource().perform_request(
        build_request(
            target_type="scene",
            table_id_conditions=SCENE_CONDITIONS,
            query_string="level:ERROR",
            group_by=True,
            order_by="value",
            limit=20,
            step="5m",
        )
    )

    scene_analyze.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=SCENE_CONDITIONS,
        field_name="level",
        keyword="level:ERROR",
        group_by=True,
        order_by="value",
        limit=20,
        step="5m",
        start_time="1710000000000",
        end_time="1710003600000",
    )
    assert result == {"series": []}


def test_index_set_request_keeps_existing_query(monkeypatch):
    query_reference = Mock(return_value={"series": []})
    monkeypatch.setattr(api.unify_query, "query_reference", query_reference)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = FieldAnalyzeResource().perform_request(build_request(index_set_id=123))

    query_reference.assert_called_once()
    params = query_reference.call_args.kwargs
    assert params["query_list"][0]["table_id"] == "bklog_index_set_123"
    assert params["query_list"][0]["function"] == [{"method": "count", "dimensions": ["level"]}]
    assert params["order_by"] == ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"]
    assert params["space_uid"] == "bkcc__2"
    assert result == {"series": []}
