"""场景化日志 MCP Resource 测试。"""

from pathlib import Path
from unittest.mock import Mock

import yaml
from django.test import override_settings

from core.drf_resource import api
from kernel_api.resource.log_search import GetSceneLogFieldsResource, ListLogScenesResource, SearchSceneLogResource


@override_settings(MCP_MAX_TIME_SPAN_SECONDS=86400)
def test_scene_log_request_serializer_validates_and_applies_defaults():
    serializer = SearchSceneLogResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "table_id_conditions": [
                [
                    {"field_name": "scene", "value": ["k8s"], "op": "eq"},
                    {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
                ]
            ],
            "start_time": "1710000000",
            "end_time": "1710003600",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["size"] == 10


def test_scene_log_request_serializer_passes_condition_content_through():
    serializer = SearchSceneLogResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "table_id_conditions": [[{"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"}]],
            "start_time": "1710000000",
            "end_time": "1710003600",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["table_id_conditions"] == [
        [{"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"}]
    ]


def test_scene_log_request_serializer_rejects_empty_condition_group():
    serializer = SearchSceneLogResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "table_id_conditions": [[]],
            "start_time": "1710000000",
            "end_time": "1710003600",
        }
    )

    assert not serializer.is_valid()
    assert "table_id_conditions" in serializer.errors


def test_scene_log_request_serializer_rejects_empty_conditions():
    serializer = SearchSceneLogResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "table_id_conditions": [],
            "start_time": "1710000000",
            "end_time": "1710003600",
        }
    )

    assert not serializer.is_valid()
    assert "table_id_conditions" in serializer.errors


def test_scene_log_resource_calls_log_platform_and_returns_result(monkeypatch):
    platform_result = {
        "took": 12,
        "total": 1,
        "list": [{"dtEventTimeStamp": "1710000000000", "log": "error"}],
        "origin_log_list": [{"log": "error"}],
        "result_table_id": ["2_bklog.container_stdout"],
    }
    scene_search = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_search", scene_search)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = SearchSceneLogResource().perform_request(
        {
            "bk_biz_id": 2,
            "table_id_conditions": [
                [
                    {"field_name": "scene", "value": ["k8s"], "op": "eq"},
                    {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
                    {"field_name": "stream", "value": ["stdout"], "op": "eq"},
                ]
            ],
            "keyword": "level:ERROR",
            "start_time": "1710000000",
            "end_time": "1710003600",
            "size": 10,
        }
    )

    scene_search.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=[
            [
                {"field_name": "scene", "value": ["k8s"], "op": "eq"},
                {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
                {"field_name": "stream", "value": ["stdout"], "op": "eq"},
            ]
        ],
        keyword="level:ERROR",
        start_time="1710000000",
        end_time="1710003600",
        size=10,
    )
    assert result == platform_result


def test_list_log_scenes_resource_calls_log_platform(monkeypatch):
    list_scenes = Mock(return_value=[{"id": "k8s", "dimensions": []}])
    monkeypatch.setattr(api.log_search, "list_scenes", list_scenes)

    result = ListLogScenesResource().perform_request({"bk_biz_id": 2})

    list_scenes.assert_called_once_with(bk_biz_id=2)
    assert result == [{"id": "k8s", "dimensions": []}]


def test_get_scene_log_fields_resource_calls_log_platform(monkeypatch):
    scene_fields = Mock(return_value={"fields": [{"field_name": "log", "field_type": "text"}]})
    monkeypatch.setattr(api.log_search, "scene_fields", scene_fields)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = GetSceneLogFieldsResource().perform_request(
        {
            "bk_biz_id": 2,
            "table_id_conditions": [
                [
                    {"field_name": "scene", "value": ["k8s"], "op": "eq"},
                    {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
                ]
            ],
        }
    )

    scene_fields.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=[
            [
                {"field_name": "scene", "value": ["k8s"], "op": "eq"},
                {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
            ]
        ],
    )
    assert result == {"fields": [{"field_name": "log", "field_type": "text"}]}


def test_scene_log_mcp_gateway_paths_match_kernel_api_routes():
    project_dir = Path(__file__).resolve().parents[2]
    gateway_file = project_dir / "support-files/apigw/resources/internal/user/log_mcp.yaml"
    gateway_paths = yaml.safe_load(gateway_file.read_text())["paths"]
    expected_routes = {
        "/mcp/list_log_scenes/": ("get", "/api/v4/log_search/list_log_scenes/"),
        "/mcp/get_scene_log_fields/": ("post", "/api/v4/log_search/get_scene_log_fields/"),
        "/mcp/search_logs_by_scene/": ("post", "/api/v4/log_search/search_scene_log/"),
    }

    for public_path, (method, backend_path) in expected_routes.items():
        gateway_resource = gateway_paths[public_path][method]["x-bk-apigateway-resource"]
        assert gateway_resource["backend"]["method"] == method
        assert gateway_resource["backend"]["path"] == backend_path
        assert gateway_resource["authConfig"]["userVerifiedRequired"] is True
        assert gateway_resource["authConfig"]["appVerifiedRequired"] is False
