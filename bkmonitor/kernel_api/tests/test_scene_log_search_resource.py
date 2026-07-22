"""场景化日志 MCP Resource 测试。"""

from unittest.mock import Mock

import pytest
from django.test import override_settings

from core.drf_resource import api
from kernel_api.resource.log_search import (
    GetSceneLogFieldsResource,
    ListLogScenesResource,
    ListSceneDimensionValuesResource,
    SearchLogResource,
)


SCENE_CONDITIONS = [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]]


def build_search_request(**kwargs):
    return {
        "bk_biz_id": 2,
        "start_time": "1710000000",
        "end_time": "1710003600",
        **kwargs,
    }


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
@pytest.mark.parametrize(
    "request_data",
    [
        build_search_request(index_set_id=375, table_id_conditions=SCENE_CONDITIONS),
        build_search_request(
            target_type="scene",
            index_set_id=375,
            table_id_conditions=SCENE_CONDITIONS,
            conditions={"field_list": [], "condition_list": []},
            keep_columns=["log"],
            order_by=["-dtEventTimeStamp"],
            offset=10,
            limit=51,
        ),
    ],
    ids=["index-set", "scene"],
)
def test_search_log_serializer_accepts_both_target_types(request_data):
    serializer = SearchLogResource.RequestSerializer(data=request_data)

    assert serializer.is_valid(), serializer.errors


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
@pytest.mark.parametrize(
    "request_data",
    [
        build_search_request(),
        build_search_request(target_type="scene", table_id_conditions=[]),
        build_search_request(target_type="scene", table_id_conditions=[[]]),
    ],
    ids=["missing-index-set", "empty-scene-conditions", "empty-scene-condition-group"],
)
def test_search_log_serializer_requires_target(request_data):
    serializer = SearchLogResource.RequestSerializer(data=request_data)

    assert not serializer.is_valid()


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
@pytest.mark.parametrize(
    "serializer_class, request_data",
    [
        (
            SearchLogResource.RequestSerializer,
            build_search_request(
                target_type="scene",
                table_id_conditions=[[{"field_name": "scene", "value": ["k8s"], "op": "like"}]],
            ),
        ),
        (
            GetSceneLogFieldsResource.RequestSerializer,
            {"bk_biz_id": 2, "table_id_conditions": [[{"value": ["k8s"], "op": "eq"}]]},
        ),
    ],
    ids=["search-invalid-op", "fields-missing-field-name"],
)
def test_scene_resources_validate_condition_structure(serializer_class, request_data):
    serializer = serializer_class(data=request_data)

    assert not serializer.is_valid()


def test_search_log_resource_routes_scene_request_to_log_platform(monkeypatch):
    platform_result = {
        "list": [
            {
                "dtEventTimeStamp": "1710000000000",
                "log": "large log content",
                "resource": {"cluster_id": "BCS-K8S-00000"},
            }
        ],
        "origin_log_list": [{"log": "duplicated log content"}],
        "fields": {"log": {"max_length": 1024}},
        "aggregations": {},
        "total": 21,
        "took": 12,
        "raw_took": 8,
    }
    scene_search = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_search", scene_search)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = SearchLogResource().perform_request(
        build_search_request(
            target_type="scene",
            table_id_conditions=SCENE_CONDITIONS,
            query_string="level:ERROR",
            offset=20,
            order_by=["-dtEventTimeStamp", "log"],
            limit=100,
        )
    )

    scene_search.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=SCENE_CONDITIONS,
        keyword="level:ERROR",
        start_time="1710000000000",
        end_time="1710003600000",
        begin=20,
        size=100,
        sort_list=[["dtEventTimeStamp", "desc"], ["log", "asc"]],
        record_history=False,
    )
    assert result == {
        "items": [
            {
                "dtEventTimeStamp": "1710000000000",
                "log": "large log content",
                "resource": {"cluster_id": "BCS-K8S-00000"},
            }
        ],
        "total": 21,
        "took": 12,
    }


def test_list_log_scenes_resource_calls_log_platform(monkeypatch):
    platform_result = [
        {
            "id": "k8s",
            "name": "Kubernetes",
            "dimensions": [{"key": "cluster_id", "choices_type": "dynamic"}],
        }
    ]
    list_scenes = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "list_scenes", list_scenes)

    result = ListLogScenesResource().perform_request({"bk_biz_id": 2})

    list_scenes.assert_called_once_with(bk_biz_id=2)
    assert result == {"scenes": platform_result}


def test_list_scene_dimension_values_resource_calls_log_platform(monkeypatch):
    platform_result = {"dimension_key": "cluster_id", "values": ["BCS-K8S-00000"]}
    scene_dimension_values = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_dimension_values", scene_dimension_values)
    request_data = {
        "bk_biz_id": 2,
        "scene": "k8s",
        "dimension_key": "cluster_id",
        "filters": [{"field_name": "stream", "value": ["stdout"], "op": "eq"}],
    }
    serializer = ListSceneDimensionValuesResource.RequestSerializer(data=request_data)
    assert serializer.is_valid(), serializer.errors

    result = ListSceneDimensionValuesResource().perform_request(serializer.validated_data)

    scene_dimension_values.assert_called_once_with(**request_data)
    assert result is platform_result


def test_get_scene_log_fields_resource_calls_log_platform(monkeypatch):
    platform_result = {
        "fields": [{"field_name": "log", "field_type": "text"}],
        "time_field": "dtEventTimeStamp",
        "display_fields": ["dtEventTimeStamp", "log"],
        "config": [{"id": "log", "name": "Log"}],
        "user_custom_config": {"display_fields": ["log"]},
    }
    scene_fields = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_fields", scene_fields)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = GetSceneLogFieldsResource().perform_request({"bk_biz_id": 2, "table_id_conditions": SCENE_CONDITIONS})

    scene_fields.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=SCENE_CONDITIONS,
    )
    assert result == {
        "fields": platform_result["fields"],
        "time_field": "dtEventTimeStamp",
    }
