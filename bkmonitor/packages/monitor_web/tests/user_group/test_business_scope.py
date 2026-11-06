from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.action.serializers.strategy import PreviewSerializer
from bkmonitor.iam import ActionEnum
from bkmonitor.models import DutyRule, UserGroup
from core.drf_resource.exceptions import CustomException
from monitor_web import permissions
from monitor_web.notice_group.resources import front
from monitor_web.user_group import resources, views

pytestmark = pytest.mark.django_db


@pytest.fixture
def iam(monkeypatch):
    permission = Mock()
    permission.is_allowed.side_effect = PermissionDenied()
    monkeypatch.setattr(permissions, "Permission", lambda: permission)
    monkeypatch.setattr(permissions, "is_biz_in_tenant", lambda *_: True)
    monkeypatch.setattr(views, "BusinessActionPermission", lambda *_: SimpleNamespace(has_permission=lambda *_: True))
    return permission


@pytest.fixture(params=[(UserGroup, views.UserGroupViewSet), (DutyRule, views.DutyRuleViewSet)])
def api(request, iam):
    model, viewset = request.param

    class ObjectSerializer(serializers.ModelSerializer):
        class Meta:
            fields = ["id", "name", "bk_biz_id"]

    ObjectSerializer.Meta.model = model

    class TestViewSet(viewset):
        filter_backends = [DjangoFilterBackend]
        authentication_classes = []

        def get_serializer_class(self):
            return ObjectSerializer

    objects = {biz: model.objects.create(name=f"group-{biz}", bk_biz_id=biz) for biz in [0, 2, 3, -2]}

    def call(method="get", biz=2, target=None, data=None, query=None, action=None):
        params = {} if biz is None else {"bk_biz_id": biz}
        params.update(query or {})
        path = "/?" + "&".join(f"{key}={value}" for key, value in params.items())
        req = getattr(APIRequestFactory(), method)(path, data=data, format="json")
        req.biz_id = biz
        force_authenticate(req, user=SimpleNamespace(tenant_id="tenant-a", is_active=True))
        action = action or (
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}[method] if target else "list"
        )
        return TestViewSet.as_view({method: action})(req, **({"pk": target.id} if target else {}))

    yield objects, call
    model.objects.filter(id__in=[obj.id for obj in objects.values()]).delete()


@pytest.mark.parametrize("biz", [None, 0, "0", "invalid"])
def test_object_routes_require_real_business(api, biz):
    objects, call = api
    assert call(biz=biz).status_code == 400
    assert call(biz=biz, target=objects[0]).status_code == 400


@pytest.mark.parametrize("biz", [2, -2])
def test_current_business_reads_platform_and_own_objects(api, iam, biz):
    objects, call = api
    response = call(biz=biz)
    assert response.status_code == 200
    assert {item["bk_biz_id"] for item in response.data} == {0, biz}
    assert call(biz=biz, target=objects[0]).status_code == 200
    assert call(biz=biz, target=objects[biz]).status_code == 200
    assert call(biz=biz, target=objects[3]).status_code == 404
    iam.is_allowed.assert_not_called()


def test_explicit_business_filter_only_narrows_and_name_filter_remains(api):
    _, call = api
    response = call(query={"bk_biz_id__in": "0,2,3"})
    assert {item["bk_biz_id"] for item in response.data} == {0, 2}
    assert [item["bk_biz_id"] for item in call(query={"bk_biz_id__in": "0"}).data] == [0]
    assert [item["bk_biz_id"] for item in call(query={"name": "group-0"}).data] == [0]
    assert call(query={"bk_biz_id__in": "bad"}).status_code == 400


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_platform_write_needs_global_permission(api, iam, method):
    objects, call = api
    assert call(method, target=objects[0], data={"bk_biz_id": 2, "name": "changed"}).status_code == 403
    objects[0].refresh_from_db()
    assert objects[0].name == "group-0"
    iam.is_allowed.assert_called_once_with(ActionEnum.MANAGE_GLOBAL_SETTING, raise_exception=True)
    iam.is_allowed.side_effect = None
    response = call(method, target=objects[0], data={"bk_biz_id": 2, "name": "changed"})
    assert response.status_code == (200 if method == "patch" else 204)
    if method == "patch":
        objects[0].refresh_from_db()
        assert objects[0].bk_biz_id == 0
        assert objects[0].name == "changed"


def test_business_write_cannot_reassign_or_modify_another_business(api, iam):
    objects, call = api
    assert call("patch", target=objects[2], data={"bk_biz_id": 3, "name": "changed"}).status_code == 200
    objects[2].refresh_from_db()
    assert objects[2].bk_biz_id == 2
    assert call("patch", target=objects[3], data={"name": "changed"}).status_code == 404
    iam.is_allowed.assert_not_called()


@pytest.mark.parametrize("target_biz", [0, 3])
def test_switch_validates_all_objects_before_writing(iam, target_biz):
    own = DutyRule.objects.create(bk_biz_id=2, name="own", enabled=False)
    target = DutyRule.objects.create(bk_biz_id=target_biz, name="target", enabled=False)
    request = SimpleNamespace(
        biz_id=2,
        user=SimpleNamespace(tenant_id="tenant-a"),
        data={"ids": [own.id, target.id], "enabled": True, "bk_biz_id": 2},
    )
    with pytest.raises(PermissionDenied):
        views.DutyRuleViewSet().switch(request)
    own.refresh_from_db()
    assert own.enabled is False
    if target_biz == 0:
        iam.is_allowed.side_effect = None
        assert set(views.DutyRuleViewSet().switch(request).data["rule_ids"]) == {own.id, target.id}
        target.refresh_from_db()
        assert target.bk_biz_id == 0 and target.enabled is True


@pytest.mark.parametrize("target_biz", [0, 3])
def test_bulk_update_validates_before_updating_users(monkeypatch, iam, target_biz):
    group = UserGroup.objects.create(bk_biz_id=target_biz, name="target")
    request = SimpleNamespace(biz_id=2, user=SimpleNamespace(tenant_id="tenant-a"))
    monkeypatch.setattr(resources, "get_request", lambda **_: request)
    update = resources.UserGroupBulkUpdateResource()
    update.update_users = Mock()
    with pytest.raises(PermissionDenied):
        update.perform_request({"ids": [group.id], "bk_biz_id": 2, "edit_data": {"users": []}})
    update.update_users.assert_not_called()
    if target_biz == 0:
        iam.is_allowed.side_effect = None
        update.perform_request({"ids": [group.id], "bk_biz_id": 2, "edit_data": {"users": []}})
        update.update_users.assert_called_once_with(partial=False)


def test_legacy_save_preserves_platform_ownership_and_delete_checks_all(monkeypatch, iam):
    request = SimpleNamespace(biz_id=2, user=SimpleNamespace(tenant_id="tenant-a"))
    backend = Mock()
    backend.backend_search_notice_group.return_value = [{"id": 1, "bk_biz_id": 0}]
    monkeypatch.setattr(front, "get_request", lambda **_: request)
    monkeypatch.setattr(front, "resource", SimpleNamespace(notice_group=backend))
    params = {"id": 1, "bk_biz_id": 2, "name": "changed"}
    with pytest.raises(PermissionDenied):
        front.NoticeGroupConfigResource().perform_request(params)
    backend.backend_save_notice_group.assert_not_called()
    iam.is_allowed.side_effect = None
    front.NoticeGroupConfigResource().perform_request(params)
    backend.backend_save_notice_group.assert_called_once_with(id=1, bk_biz_id=0, name="changed")
    backend.backend_search_notice_group.return_value = [{"id": 1, "bk_biz_id": 0}, {"id": 2, "bk_biz_id": 3}]
    with pytest.raises(PermissionDenied):
        front.DeleteNoticeGroupResource().perform_request({"id_list": [1, 2]})
    backend.backend_delete_notice_group.assert_not_called()


@pytest.mark.parametrize("biz,valid", [(2, True), (-2, True), (0, False), (None, False)])
def test_api_preview_accepts_real_business_without_http_context(biz, valid):
    rule = DutyRule.objects.create(bk_biz_id=0, name="platform")
    data = {"id": rule.id, "source_type": "DB"}
    if biz is not None:
        data["bk_biz_id"] = biz
    serializer = PreviewSerializer(data=data)
    assert serializer.is_valid() is valid
    if valid:
        assert serializer.validated_data["instance"].bk_biz_id == 0


def test_api_preview_rejects_other_business():
    rule = DutyRule.objects.create(bk_biz_id=3, name="other")
    serializer = PreviewSerializer(data={"id": rule.id, "source_type": "DB", "bk_biz_id": 2})
    with pytest.raises(CustomException, match="not existed"):
        serializer.is_valid(raise_exception=True)


def test_context_rejects_tenant_mismatch(monkeypatch):
    monkeypatch.setattr(permissions, "is_biz_in_tenant", lambda *_: False)
    with pytest.raises(PermissionDenied):
        permissions.require_business_id(SimpleNamespace(biz_id=2, user=SimpleNamespace(tenant_id="tenant-b")))
