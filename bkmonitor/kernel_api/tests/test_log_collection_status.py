"""日志采集状态 MCP 资源测试。"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.iam import ActionEnum
from kernel_api.resource import log_collection_status as status_module
from kernel_api.resource.log_collection_status import (
    GetLogCollectorStatusResource,
    aggregate_status,
    combine_phase_status,
    flatten_status_details,
    normalize_task_ids,
)
from kernel_api.views.v4.log_collection_status import LogCollectionStatusViewSet


def build_payload(*statuses):
    return {
        "contents": [
            {
                "child": [
                    {
                        "status": raw_status,
                        "instance_id": f"instance-{index}",
                        "task_id": str(index),
                        "message": f"message-{index}" if raw_status == "FAILED" else "",
                    }
                    for index, raw_status in enumerate(statuses)
                ]
            }
        ]
    }


@pytest.mark.parametrize(
    "raw_statuses,expected",
    [
        (["PENDING", "FAILED"], "running"),
        (["SUCCESS"], "success"),
        (["SUCCESS", "FAILED"], "partial_failed"),
        (["SUCCESS", "UNKNOWN"], "unknown"),
        (["FAILED"], "failed"),
        ([], "unknown"),
    ],
)
def test_aggregate_status(raw_statuses, expected):
    assert aggregate_status(flatten_status_details(build_payload(*raw_statuses), "task")) == expected


@pytest.mark.parametrize(
    "task_status,subscription_status,expected",
    [
        ("running", "success", "running"),
        ("failed", "success", "failed"),
        ("partial_failed", "success", "partial_failed"),
        ("success", "failed", "failed"),
        ("success", "unknown", "unknown"),
        ("unknown", "success", "unknown"),
        ("unknown", "terminated", "terminated"),
    ],
)
def test_combine_phase_status(task_status, subscription_status, expected):
    assert combine_phase_status(task_status, subscription_status) == expected


def test_serializer_rejects_too_many_task_ids():
    serializer = GetLogCollectorStatusResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "task_ids": [str(index) for index in range(101)]}
    )
    assert not serializer.is_valid()
    assert "task_ids" in serializer.errors


def test_normalize_task_ids_flattens_csv_and_removes_duplicates():
    assert normalize_task_ids(["1,2", "2", 3]) == ["1", "2", "3"]


def test_status_view_requires_view_collection_permission():
    permissions = LogCollectionStatusViewSet().get_permissions()
    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.VIEW_COLLECTION]


def test_status_resource_normalizes_host_success(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "collector_config_id": kwargs["collector_config_id"],
            "bk_biz_id": 2,
            "subscription_id": 88,
            "task_id_list": ["101"],
            "environment": "linux",
        },
        log_collector_task_status=lambda **kwargs: build_payload("SUCCESS"),
        log_collector_subscription_status=lambda **kwargs: build_payload("SUCCESS"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 10, "detail_limit": 20}
    )

    assert result["collector_config_id"] == 10
    assert result["subscription_id"] == 88
    assert result["task_ids"] == ["101"]
    assert result["status"] == "success"
    assert result["is_terminal"] is True
    assert result["retry_after_seconds"] == 0
    assert result["task"]["counts"]["success"] == 1
    assert result["subscription"]["counts"]["success"] == 1


def test_status_resource_normalizes_container_partial_failure(monkeypatch):
    captured = {}

    def task_status(**kwargs):
        captured.update(kwargs)
        return build_payload("SUCCESS", "FAILED")

    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "subscription_id": None,
            "task_id_list": [201, 202],
            "environment": "container",
        },
        log_collector_task_status=task_status,
        log_collector_subscription_status=lambda **kwargs: build_payload("SUCCESS", "FAILED"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 20, "detail_limit": 1}
    )

    assert captured["task_id_list"] == "201,202"
    assert result["status"] == "partial_failed"
    assert result["task"]["counts"] == {
        "total": 2,
        "running": 0,
        "success": 1,
        "partial_failed": 0,
        "failed": 1,
        "terminated": 0,
        "unknown": 0,
    }
    assert result["task"]["truncated"] is True
    assert len(result["task"]["details"]) == 1
    assert len(result["errors"]) == 1


def test_status_resource_marks_unknown_as_pollable(monkeypatch):
    task_status = lambda **kwargs: pytest.fail("task status should not be requested")
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "task_id_list": None},
        log_collector_task_status=task_status,
        log_collector_subscription_status=lambda **kwargs: None,
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 30, "detail_limit": 20}
    )

    assert result["status"] == "unknown"
    assert result["is_terminal"] is False
    assert result["retry_after_seconds"] == 5


def test_status_resource_rejects_normalized_task_id_overflow(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": ",".join(str(index) for index in range(101)),
        },
        log_collector_task_status=lambda **kwargs: pytest.fail("task status should not be requested"),
        log_collector_subscription_status=lambda **kwargs: pytest.fail("subscription status should not be requested"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(ValidationError, match="no more than 100"):
        GetLogCollectorStatusResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 31, "detail_limit": 20}
        )


def test_status_resource_preserves_unknown_until_task_is_visible(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": ["101"],
            "environment": "linux",
        },
        log_collector_task_status=lambda **kwargs: {"task_ready": False, "contents": []},
        log_collector_subscription_status=lambda **kwargs: build_payload("SUCCESS"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 32, "detail_limit": 20}
    )

    assert result["status"] == "unknown"
    assert result["is_terminal"] is False


def test_status_resource_treats_subscription_terminated_as_terminal(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": ["101"],
            "environment": "container",
        },
        log_collector_task_status=lambda **kwargs: build_payload("SUCCESS"),
        log_collector_subscription_status=lambda **kwargs: build_payload("TERMINATED"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 33, "detail_limit": 20}
    )

    assert result["status"] == "terminated"
    assert result["is_terminal"] is True
    assert result["subscription"]["counts"]["terminated"] == 1


def test_status_resource_applies_global_detail_limit(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "task_id_list": ["101"]},
        log_collector_task_status=lambda **kwargs: build_payload("SUCCESS", "FAILED"),
        log_collector_subscription_status=lambda **kwargs: build_payload("FAILED", "FAILED"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 34, "detail_limit": 2}
    )

    assert len(result["task"]["details"]) + len(result["subscription"]["details"]) == 2
    assert result["subscription"]["truncated"] is True
    assert len(result["errors"]) <= 2


def test_status_resource_rejects_cross_business_collector(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 3},
        log_collector_task_status=lambda **kwargs: pytest.fail("task status should not be requested"),
        log_collector_subscription_status=lambda **kwargs: pytest.fail("subscription status should not be requested"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(PermissionDenied):
        GetLogCollectorStatusResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 40, "detail_limit": 20}
        )
