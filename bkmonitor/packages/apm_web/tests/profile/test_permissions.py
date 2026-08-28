from unittest import mock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apm_web.profile.serializers import (
    ProfileListFileSerializer,
    ProfileQuerySerializer,
    ProfileQueryLabelValuesSerializer,
    ProfileQueryLabelsSerializer,
)
from apm_web.profile.views import ProfileQueryViewSet, ProfileUploadViewSet
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission


def build_viewset(view_class, params, method="get"):
    factory = APIRequestFactory()
    if method == "get":
        raw_request = factory.get("/", params)
    else:
        raw_request = factory.post("/", params, format="json")
    viewset = view_class()
    viewset.request = Request(raw_request)
    viewset.kwargs = {}
    return viewset


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"bk_biz_id": 2, "app_name": "demo"}, InstanceActionForDataPermission),
        ({"bk_biz_id": 2}, ViewBusinessPermission),
        ({"bk_biz_id": 2, "app_name": "demo", "global_query": "true"}, ViewBusinessPermission),
        ({"bk_biz_id": 2, "app_name": "demo", "global_query": "false"}, InstanceActionForDataPermission),
    ],
)
def test_profile_permissions_never_return_empty(params, expected):
    permissions = build_viewset(ProfileQueryViewSet, params).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], expected)


def test_profile_upload_requires_business_permission():
    permissions = build_viewset(ProfileUploadViewSet, {"bk_biz_id": 2}, method="post").get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], ViewBusinessPermission)


@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.profile.views.Application.get_application_id_by_app_name", return_value=9)
def test_profile_permission_checks_resolved_application_resource(application_id_mock, permission_mock):
    viewset = build_viewset(ProfileQueryViewSet, {"bk_biz_id": 2, "app_name": "demo"})
    permission = viewset.get_permissions()[0]

    assert permission.has_permission(viewset.request, viewset) is True

    application_id_mock.assert_called_once_with("demo")
    checked_resource = permission_mock.return_value.is_allowed.call_args[1]["resources"][0]
    assert str(checked_resource.id) == "9"


def test_profile_records_require_bk_biz_id():
    assert not ProfileListFileSerializer(data={}).is_valid()
    assert ProfileListFileSerializer(data={"bk_biz_id": 2}).is_valid()


@mock.patch("apm_web.profile.views.ProfileUploadRecord.objects.filter")
def test_global_query_rejects_profile_id_of_another_business(filter_mock):
    filter_mock.return_value.exists.return_value = False

    with pytest.raises(ValueError):
        ProfileQueryViewSet._examine_global_query_scope({"bk_biz_id": 2, "profile_id": "foreign-profile"})

    filter_mock.assert_called_once_with(bk_biz_id=2, profile_id="foreign-profile")


@mock.patch("apm_web.profile.views.ProfileUploadRecord.objects.filter")
def test_global_query_accepts_own_profile_id(filter_mock):
    filter_mock.return_value.exists.return_value = True

    ProfileQueryViewSet._examine_global_query_scope(
        {"bk_biz_id": 2, "profile_id": "own-profile", "diff_profile_id": ""}
    )


@mock.patch("apm_web.profile.views.ProfileUploadRecord.objects.filter")
def test_global_compare_query_requires_diff_profile_id(filter_mock):
    filter_mock.return_value.exists.return_value = True
    serializer = ProfileQuerySerializer(
        data={
            "bk_biz_id": 2,
            "global_query": True,
            "start": 1,
            "end": 2,
            "profile_id": "own-profile",
            "is_compared": True,
        }
    )
    serializer.is_valid(raise_exception=True)

    with pytest.raises(ValueError, match="diff_profile_id"):
        ProfileQueryViewSet._examine_global_query_scope(serializer.validated_data)


@pytest.mark.parametrize("serializer_class", [ProfileQueryLabelsSerializer, ProfileQueryLabelValuesSerializer])
def test_global_label_query_requires_profile_id(serializer_class):
    data = {"bk_biz_id": 2, "global_query": True, "start": 1, "end": 2}
    if serializer_class is ProfileQueryLabelValuesSerializer:
        data["label_key"] = "service"
    serializer = serializer_class(
        data=data
    )
    serializer.is_valid(raise_exception=True)

    with pytest.raises(ValueError, match="profile_id"):
        ProfileQueryViewSet._examine_global_query_scope(serializer.validated_data)


@pytest.mark.parametrize(
    ("action", "extra_params"),
    [("labels", {}), ("label_values", {"label_key": "service"})],
)
@mock.patch.object(ProfileQueryViewSet, "query")
@mock.patch.object(ProfileQueryViewSet, "_get_essentials")
def test_global_label_query_filters_by_profile_id(essentials_mock, query_mock, action, extra_params):
    essentials_mock.return_value = {
        "bk_biz_id": 1,
        "app_name": "builtin",
        "service_name": "builtin",
        "result_table_id": "1_profile_builtin",
    }
    query_mock.return_value = {"list": []}
    params = {
        "bk_biz_id": 2,
        "global_query": True,
        "start": 1,
        "end": 2,
        "profile_id": "own-profile",
    }
    params.update(extra_params)
    viewset = build_viewset(ProfileQueryViewSet, params)

    getattr(viewset, action)(viewset.request)

    assert query_mock.call_args[1]["profile_id"] == "own-profile"
