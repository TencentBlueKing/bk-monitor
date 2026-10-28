from importlib import import_module

import pytest
from rest_framework.exceptions import ValidationError

from core.errors.bkmonitor.space import SpaceNotFound
from metadata.models.space import Space
from metadata.resources import SetBkmsSpaceStatusResource

pytestmark = pytest.mark.django_db(databases="__all__")
space_resources = import_module("metadata.resources.space")


@pytest.fixture
def bkms_space(monkeypatch):
    monkeypatch.setattr(space_resources, "get_request_tenant_id", lambda: "tenant-main")
    return Space.objects.create(
        bk_tenant_id="tenant-main",
        space_type_id="bkci",
        space_id="bkms-status-test",
        space_name="status-test",
        space_code="status-test",
        is_bcs_valid=True,
    )


def test_set_status_is_idempotent_and_preserves_other_fields(bkms_space):
    before = bkms_space.to_dict()
    for status in ["disabled", "disabled", "normal", "normal"]:
        result = SetBkmsSpaceStatusResource().request(space_uid=bkms_space.space_uid, status=status)
        assert result == {"space_uid": bkms_space.space_uid, "status": status}
        bkms_space.refresh_from_db()
        assert bkms_space.to_dict() == {**before, "status": status}


@pytest.mark.parametrize(
    "space_uid",
    ["bkcc__bkms-example", "bcs__bkms-example", "bkci__project", "bkci__BKMS-example", "invalid", ""],
)
def test_rejects_space_outside_bkms_scope(bkms_space, space_uid):
    serializer = SetBkmsSpaceStatusResource.RequestSerializer(data={"space_uid": space_uid, "status": "disabled"})
    assert not serializer.is_valid()
    bkms_space.refresh_from_db()
    assert bkms_space.status == "normal"


@pytest.mark.parametrize("status", ["enabled", "", None])
def test_rejects_invalid_status(bkms_space, status):
    serializer = SetBkmsSpaceStatusResource.RequestSerializer(
        data={"space_uid": bkms_space.space_uid, "status": status}
    )
    assert not serializer.is_valid()


@pytest.mark.parametrize("tenant", ["tenant-main", "tenant-other"])
def test_missing_or_other_tenant_space_is_not_updated(bkms_space, monkeypatch, tenant):
    monkeypatch.setattr(space_resources, "get_request_tenant_id", lambda: tenant)
    space_uid = "bkci__bkms-missing" if tenant == "tenant-main" else bkms_space.space_uid
    with pytest.raises(SpaceNotFound):
        SetBkmsSpaceStatusResource().request(space_uid=space_uid, status="disabled")
    bkms_space.refresh_from_db()
    assert bkms_space.status == "normal"


def test_existing_non_bkms_space_is_not_updated(bkms_space):
    other = Space.objects.create(
        bk_tenant_id="tenant-main", space_type_id="bkci", space_id="other-project", space_name="other-project"
    )
    serializer = SetBkmsSpaceStatusResource.RequestSerializer(data={"space_uid": other.space_uid, "status": "disabled"})
    assert not serializer.is_valid()
    other.refresh_from_db()
    assert other.status == "normal"


def test_database_case_insensitive_match_does_not_expand_bkms_scope(bkms_space):
    other = Space.objects.create(
        bk_tenant_id="tenant-main", space_type_id="bkci", space_id="BKMS-case-test", space_name="case-test"
    )
    with pytest.raises((ValidationError, SpaceNotFound)):
        SetBkmsSpaceStatusResource().perform_request({"space_uid": "bkci__bkms-case-test", "status": "disabled"})
    other.refresh_from_db()
    assert other.status == "normal"
