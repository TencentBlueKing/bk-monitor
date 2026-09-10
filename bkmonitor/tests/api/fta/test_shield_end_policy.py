from unittest.mock import Mock, patch

import pytest
from monitor_web.shield.resources.backend_resources import (
    AddShieldResource,
    BulkAddAlertShieldResource,
    EditShieldResource,
    ShieldDetailResource,
)
from monitor_web.shield.serializers import BaseSerializer
from rest_framework.exceptions import ValidationError


def create_data(**overrides):
    return {
        "bk_biz_id": 2,
        "category": "dimension",
        "begin_time": "2026-09-09 10:00:00",
        "end_time": "2026-09-09 11:00:00",
        "dimension_config": {"dimension_conditions": [{"key": "ip", "value": ["127.0.0.1"]}]},
        "cycle_config": {"type": 1},
        "shield_notice": False,
        **overrides,
    }


@pytest.mark.parametrize("policy", ["notify_once", "close"])
def test_create_preserves_end_policy(policy):
    data = AddShieldResource().validate_request_data(create_data(end_policy=policy))
    with (
        patch("monitor_web.shield.resources.backend_resources.handle_shield_time", return_value=(1, 2)),
        patch("monitor_web.shield.resources.backend_resources.Shield.objects.create") as create,
    ):
        AddShieldResource().perform_request(data)
    assert create.call_args.kwargs["end_policy"] == policy


def test_old_create_defaults_to_notify_once():
    serializer = BaseSerializer(data=create_data())
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["end_policy"] == "notify_once"


@pytest.mark.parametrize("overrides", [{"category": "alert"}, {"category": "event"}, {"is_quick": True}])
def test_quick_shield_rejects_close(overrides):
    serializer = BaseSerializer(data=create_data(end_policy="close", **overrides))
    assert not serializer.is_valid()
    assert "end_policy" in serializer.errors


def test_invalid_policy_is_rejected():
    serializer = BaseSerializer(data=create_data(end_policy="other"))
    assert not serializer.is_valid()
    assert "end_policy" in serializer.errors


@pytest.mark.parametrize("resource_class", [AddShieldResource, BulkAddAlertShieldResource])
def test_alert_creation_rejects_close_before_side_effects(resource_class):
    with pytest.raises(ValidationError):
        resource_class().validate_request_data(
            create_data(category="alert", dimension_config={"alert_ids": ["123"]}, end_policy="close")
        )


@pytest.mark.parametrize("policy", ["notify_once", "close"])
def test_detail_returns_end_policy(policy):
    shield = Mock(end_policy=policy)
    with (
        patch("monitor_web.shield.resources.backend_resources.Shield.objects.get", return_value=shield),
        patch("monitor_web.shield.resources.backend_resources.utc2biz_str", return_value="time"),
    ):
        result = ShieldDetailResource().perform_request({"id": 1, "bk_biz_id": 2})
    assert result["end_policy"] == policy


@pytest.mark.parametrize("policy", [None, "close"])
def test_edit_keeps_original_policy(policy):
    shield = Mock(id=1, category="dimension", end_policy="close")
    data = create_data(id=1)
    if policy is not None:
        data["end_policy"] = policy
    serializer = EditShieldResource.RequestSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    if policy is None:
        assert "end_policy" not in serializer.validated_data
    with (
        patch("monitor_web.shield.resources.backend_resources.Shield.objects.get", return_value=shield),
        patch("monitor_web.shield.resources.backend_resources.handle_shield_time", return_value=(1, 2)),
    ):
        EditShieldResource().perform_request(serializer.validated_data)
    assert shield.end_policy == "close"
    shield.save.assert_called_once()


@pytest.mark.parametrize("original,changed", [("close", "notify_once"), ("notify_once", "close")])
def test_edit_rejects_entire_change_before_mutation(original, changed):
    shield = Mock(id=1, category="dimension", end_policy=original, description="original")
    with (
        patch("monitor_web.shield.resources.backend_resources.Shield.objects.get", return_value=shield),
        patch("monitor_web.shield.resources.backend_resources.handle_shield_time") as handle_time,
        pytest.raises(ValidationError),
    ):
        EditShieldResource().perform_request(create_data(id=1, end_policy=changed, description="changed"))
    handle_time.assert_not_called()
    shield.save.assert_not_called()
    assert shield.description == "original"
