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
    sanitize_status_message,
)
from kernel_api.views.v4.log_collection_status import (
    CanonicalBusinessActionPermission,
    LogCollectionStatusViewSet,
)


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
        (["FAILED", "UNKNOWN"], "unknown"),
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
        ("unknown", "failed", "unknown"),
        ("unknown", "terminated", "unknown"),
        ("terminated", "success", "terminated"),
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


def test_serializer_accepts_integer_task_ids_and_rejects_empty_list():
    serializer = GetLogCollectorStatusResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "task_ids": [101]}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["task_ids"] == ["101"]

    serializer = GetLogCollectorStatusResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "task_ids": []}
    )
    assert not serializer.is_valid()
    assert "task_ids" in serializer.errors


def test_serializer_rejects_invalid_collector_id():
    serializer = GetLogCollectorStatusResource.RequestSerializer(data={"bk_biz_id": 2, "collector_config_id": 0})
    assert not serializer.is_valid()
    assert "collector_config_id" in serializer.errors


def test_normalize_task_ids_flattens_csv_and_removes_duplicates():
    assert normalize_task_ids(["1,2", "2", 3]) == ["1", "2", "3"]


def test_status_message_is_masked_and_truncated():
    message, truncated = sanitize_status_message("token=plain-secret," + "x" * 2100)
    assert "plain-secret" not in message
    assert len(message) == 2000
    assert truncated is True


def test_status_view_requires_log_collection_mcp_permission():
    permissions = LogCollectionStatusViewSet().get_permissions()
    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.USING_LOG_COLLECTION_MCP]


def test_status_permission_rejects_conflicting_business_alias():
    permission = CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])
    request = SimpleNamespace(
        data={"bk_biz_id": 2, "biz_id": 3},
        biz_id=3,
    )

    assert permission.has_permission(request, None) is False


def test_status_resource_normalizes_host_success(monkeypatch):
    captured = {"task": {}, "subscription": {}}

    def task_status(**kwargs):
        captured["task"].update(kwargs)
        return build_payload("SUCCESS")

    def subscription_status(**kwargs):
        captured["subscription"].update(kwargs)
        return build_payload("SUCCESS")

    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "collector_config_id": kwargs["collector_config_id"],
            "bk_biz_id": 2,
            "subscription_id": 88,
            "task_id_list": ["101"],
            "environment": "linux",
        },
        log_collector_task_status=task_status,
        log_collector_subscription_status=subscription_status,
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
    assert captured["task"]["read_only"] is True
    assert captured["subscription"]["include_plugin_status"] is False


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
    def task_status(**kwargs):
        pytest.fail("task status should not be requested")

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


def test_status_resource_uses_subscription_when_no_task_exists(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": None,
            "environment": None,
        },
        log_collector_task_status=lambda **kwargs: pytest.fail("task status should not be requested"),
        log_collector_subscription_status=lambda **kwargs: build_payload("SUCCESS"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 30, "detail_limit": 20}
    )

    assert result["status"] == "success"
    assert result["is_terminal"] is True
    assert result["environment"] == ""


def test_status_resource_rejects_non_numeric_task_ids(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "task_id_list": ["task-1"]},
        log_collector_task_status=lambda **kwargs: pytest.fail("task status should not be requested"),
        log_collector_subscription_status=lambda **kwargs: pytest.fail("subscription status should not be requested"),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(ValidationError, match="positive integers"):
        GetLogCollectorStatusResource().perform_request({"bk_biz_id": 2, "collector_config_id": 30, "detail_limit": 20})


def test_status_resource_rejects_oversized_task_id():
    serializer = GetLogCollectorStatusResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "task_ids": ["1" * 21]}
    )
    assert not serializer.is_valid()
    assert "task_ids" in serializer.errors


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
        GetLogCollectorStatusResource().perform_request({"bk_biz_id": 2, "collector_config_id": 31, "detail_limit": 20})


def test_status_resource_preserves_unknown_until_task_is_visible(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": ["101"],
            "environment": "linux",
        },
        log_collector_task_status=lambda **kwargs: {"task_ready": False, "contents": []},
        log_collector_subscription_status=lambda **kwargs: pytest.fail(
            "subscription status should be skipped until task is visible"
        ),
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


def test_status_resource_treats_container_task_terminated_as_terminal(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
            "bk_biz_id": 2,
            "task_id_list": ["101"],
            "environment": "container",
        },
        log_collector_task_status=lambda **kwargs: build_payload("TERMINATED"),
        log_collector_subscription_status=lambda **kwargs: pytest.fail(
            "subscription status should be skipped for terminal task"
        ),
    )
    monkeypatch.setattr(status_module, "api", SimpleNamespace(log_search=log_search))

    result = GetLogCollectorStatusResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 33, "detail_limit": 20}
    )

    assert result["status"] == "terminated"
    assert result["is_terminal"] is True
    assert result["task"]["counts"]["terminated"] == 1


def test_status_resource_applies_global_detail_limit(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "task_id_list": ["101"]},
        log_collector_task_status=lambda **kwargs: build_payload("SUCCESS", "SUCCESS"),
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
        GetLogCollectorStatusResource().perform_request({"bk_biz_id": 2, "collector_config_id": 40, "detail_limit": 20})
