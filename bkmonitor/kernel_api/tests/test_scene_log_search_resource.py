"""场景化日志 MCP Resource 测试。"""

from unittest.mock import Mock

import pytest
from django.test import override_settings

from core.drf_resource import api
from kernel_api.resource.log_search import GetSceneLogFieldsResource, ListLogScenesResource, SearchLogResource


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


def test_search_log_resource_routes_scene_request_to_log_platform(monkeypatch):
    platform_result = Mock()
    scene_search = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_search", scene_search)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = SearchLogResource().perform_request(
        build_search_request(
            target_type="scene",
            table_id_conditions=SCENE_CONDITIONS,
            query_string="level:ERROR",
            limit=100,
        )
    )

    scene_search.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=SCENE_CONDITIONS,
        keyword="level:ERROR",
        start_time="1710000000",
        end_time="1710003600",
        size=100,
        record_history=False,
    )
    assert result is platform_result


def test_list_log_scenes_resource_calls_log_platform(monkeypatch):
    platform_result = Mock()
    list_scenes = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "list_scenes", list_scenes)

    result = ListLogScenesResource().perform_request({"bk_biz_id": 2})

    list_scenes.assert_called_once_with(bk_biz_id=2)
    assert result is platform_result


def test_get_scene_log_fields_resource_calls_log_platform(monkeypatch):
    platform_result = Mock()
    scene_fields = Mock(return_value=platform_result)
    monkeypatch.setattr(api.log_search, "scene_fields", scene_fields)
    monkeypatch.setattr("kernel_api.resource.log_search.bk_biz_id_to_space_uid", lambda bk_biz_id: "bkcc__2")

    result = GetSceneLogFieldsResource().perform_request({"bk_biz_id": 2, "table_id_conditions": SCENE_CONDITIONS})

    scene_fields.assert_called_once_with(
        space_uid="bkcc__2",
        bk_biz_id=2,
        table_id_conditions=SCENE_CONDITIONS,
    )
    assert result is platform_result
