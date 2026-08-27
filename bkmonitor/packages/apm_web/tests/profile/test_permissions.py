"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apm_web.models import ProfileUploadRecord, UploadedFileStatus
from apm_web.profile.serializers import (
    ProfileListFileSerializer,
    ProfileQueryLabelsSerializer,
    ProfileQueryLabelValuesSerializer,
)
from apm_web.profile.views import ProfileQueryViewSet, ProfileUploadViewSet
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission

BK_BIZ_ID = 2
OTHER_BK_BIZ_ID = 3


def build_viewset(view_class, params: dict, method: str = "get"):
    factory = APIRequestFactory()
    if method == "get":
        raw_request = factory.get("/", params)
    else:
        raw_request = factory.post("/", params, format="json")

    viewset = view_class()
    viewset.request = Request(raw_request)
    return viewset


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # 带 app_name 的普通查询落到 APM 应用上鉴权
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "demo"}, InstanceActionForDataPermission),
        # 上传记录、文件上传没有 app_name，退到业务鉴权
        ({"bk_biz_id": BK_BIZ_ID}, ViewBusinessPermission),
        # global_query 读的是内置数据源，app_name 不参与查询
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "demo", "global_query": "true"}, ViewBusinessPermission),
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "demo", "global_query": "1"}, ViewBusinessPermission),
        # global_query 为假值时仍按应用鉴权
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "demo", "global_query": "false"}, InstanceActionForDataPermission),
        # ebpf- 应用来自 DeepFlow，没有对应的 Application 记录
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "ebpf-demo"}, ViewBusinessPermission),
    ],
)
def test_get_permissions_never_returns_empty(params, expected):
    viewset = build_viewset(ProfileQueryViewSet, params)
    permissions = viewset.get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], expected)


def test_upload_viewset_requires_business_permission():
    viewset = build_viewset(ProfileUploadViewSet, {"bk_biz_id": BK_BIZ_ID}, method="post")
    permissions = viewset.get_permissions()

    assert [type(permission) for permission in permissions] == [ViewBusinessPermission]


@pytest.mark.django_db
def test_global_query_rejects_profile_id_of_another_business():
    ProfileUploadRecord.objects.create(
        bk_biz_id=OTHER_BK_BIZ_ID,
        app_name="builtin",
        file_key="key",
        file_md5="md5",
        profile_id="foreign-profile-id",
        operator="admin",
        origin_file_name="foreign.pprof",
        status=UploadedFileStatus.STORE_SUCCEED,
    )

    with pytest.raises(ValueError):
        ProfileQueryViewSet._examine_global_query_scope({"bk_biz_id": BK_BIZ_ID, "profile_id": "foreign-profile-id"})


@pytest.mark.django_db
def test_global_query_rejects_empty_profile_id():
    # profile_id 为空时查询不带过滤条件，会读到整个内置数据源
    with pytest.raises(ValueError):
        ProfileQueryViewSet._examine_global_query_scope({"bk_biz_id": BK_BIZ_ID, "profile_id": ""})


@pytest.mark.django_db
def test_global_query_accepts_own_profile_id_without_diff():
    ProfileUploadRecord.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name="builtin",
        file_key="key",
        file_md5="md5",
        profile_id="own-profile-id",
        operator="admin",
        origin_file_name="own.pprof",
        status=UploadedFileStatus.STORE_SUCCEED,
    )

    ProfileQueryViewSet._examine_global_query_scope(
        {"bk_biz_id": BK_BIZ_ID, "profile_id": "own-profile-id", "diff_profile_id": ""}
    )


@pytest.mark.parametrize("serializer_class", [ProfileQueryLabelsSerializer, ProfileQueryLabelValuesSerializer])
def test_global_label_query_requires_profile_id(serializer_class):
    data = {"bk_biz_id": BK_BIZ_ID, "global_query": True, "start": 1, "end": 2}
    if serializer_class is ProfileQueryLabelValuesSerializer:
        data["label_key"] = "service"
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)

    with pytest.raises(ValueError, match="profile_id"):
        ProfileQueryViewSet._examine_global_query_scope(serializer.validated_data)


@pytest.mark.parametrize(
    ("action", "extra_params"),
    [("labels", {}), ("label_values", {"label_key": "service"})],
)
@mock.patch.object(ProfileQueryViewSet, "query")
@mock.patch.object(ProfileQueryViewSet, "get_essentials")
def test_global_label_query_filters_by_profile_id(essentials_mock, query_mock, action, extra_params):
    essentials_mock.return_value = {
        "bk_biz_id": 1,
        "app_name": "builtin",
        "service_name": "builtin",
        "result_table_id": "1_profile_builtin",
        "is_ebpf": False,
    }
    query_mock.return_value = {"list": []}
    params = {
        "bk_biz_id": BK_BIZ_ID,
        "global_query": True,
        "start": 1,
        "end": 2,
        "profile_id": "own-profile",
    }
    params.update(extra_params)
    viewset = build_viewset(ProfileQueryViewSet, params)

    getattr(viewset, action)(viewset.request)

    assert query_mock.call_args[1]["profile_id"] == "own-profile"


def test_list_file_serializer_requires_bk_biz_id():
    # 不带业务时曾会列出全平台的上传记录
    assert not ProfileListFileSerializer(data={}).is_valid()
    assert ProfileListFileSerializer(data={"bk_biz_id": BK_BIZ_ID}).is_valid()
