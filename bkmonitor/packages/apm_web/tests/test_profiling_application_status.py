"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from apm_web.constants import DataStatus
from apm_web.models import Application
from apm_web.profile.resources import ListApplicationServicesResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "profiling-demo"


@pytest.fixture
def application() -> Application:
    return Application.objects.create(
        application_id=1,
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        app_alias="Profiling 应用",
        description="性能分析数据状态测试",
        is_enabled_profiling=True,
        profiling_data_status=DataStatus.NORMAL,
    )


@pytest.fixture
def profile_services() -> list[dict[str, Any]]:
    return [
        {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "name": name,
            "sample_type": sample_type,
            "last_check_time": "2026-10-01 00:00:00",
            "is_large": False,
        }
        for name, sample_type in (
            ("service-a", "cpu/nanoseconds"),
            ("service-b", "alloc_objects/count"),
            ("service-a", "inuse_objects/count"),
        )
    ]


@pytest.mark.parametrize("data_status", [DataStatus.NORMAL, DataStatus.NO_DATA, DataStatus.DISABLED])
@pytest.mark.parametrize("with_services", [False, True])
def test_application_group_uses_persisted_status_and_keeps_history(
    application: Application,
    profile_services: list[dict[str, Any]],
    mocker: MockerFixture,
    data_status: str,
    with_services: bool,
) -> None:
    Application.objects.filter(pk=application.pk).update(
        profiling_data_status=data_status,
        is_enabled_profiling=data_status != DataStatus.DISABLED,
    )
    services_query = mocker.patch(
        "apm_web.profile.resources.api.apm_api.query_profile_services_detail",
        return_value=profile_services if with_services else [],
    )
    ebpf_query = mocker.patch("apm_web.profile.resources.api.apm_api.query_ebpf_service_list")

    response = ListApplicationServicesResource().request({"bk_biz_id": BK_BIZ_ID})

    expected_group = "normal" if data_status == DataStatus.NORMAL else "no_data"
    expected = {"normal": [], "no_data": []}
    expected[expected_group] = [
        {
            "bk_biz_id": BK_BIZ_ID,
            "application_id": application.application_id,
            "description": application.description,
            "app_name": APP_NAME,
            "app_alias": application.app_alias,
            "services": [profile_services[2], profile_services[1]] if with_services else [],
        }
    ]
    assert response == expected
    services_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID)
    ebpf_query.assert_not_called()
    application.refresh_from_db()
    assert application.profiling_data_status == data_status


def test_application_services_are_isolated_by_business_and_application(
    application: Application,
    profile_services: list[dict[str, Any]],
    mocker: MockerFixture,
) -> None:
    Application.objects.create(
        application_id=2,
        bk_biz_id=BK_BIZ_ID + 1,
        app_name=APP_NAME,
        profiling_data_status=DataStatus.NORMAL,
    )
    foreign_services = [
        {**profile_services[0], "bk_biz_id": BK_BIZ_ID + 1},
        {**profile_services[0], "app_name": "other-app"},
    ]
    services_query = mocker.patch(
        "apm_web.profile.resources.api.apm_api.query_profile_services_detail",
        return_value=[profile_services[0], *foreign_services],
    )

    response = ListApplicationServicesResource().request({"bk_biz_id": BK_BIZ_ID})

    assert len(response["normal"]) == 1
    assert response["normal"][0]["application_id"] == application.application_id
    assert response["normal"][0]["services"] == [profile_services[0]]
    assert response["no_data"] == []
    services_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID)


@pytest.mark.parametrize("is_get_ebpf", [False, True])
def test_application_services_keep_ebpf_branch(
    application: Application,
    profile_services: list[dict[str, Any]],
    mocker: MockerFixture,
    is_get_ebpf: bool,
) -> None:
    mocker.patch(
        "apm_web.profile.resources.api.apm_api.query_profile_services_detail", return_value=[profile_services[0]]
    )
    ebpf_apps = [{"app_name": "ebpf-app", "services": [{"name": "ebpf-service", "sample_type": "cpu"}]}]
    ebpf_query = mocker.patch("apm_web.profile.resources.api.apm_api.query_ebpf_service_list", return_value=ebpf_apps)

    response = ListApplicationServicesResource().request({"bk_biz_id": BK_BIZ_ID, "is_get_ebpf": is_get_ebpf})

    assert response["normal"][0]["application_id"] == application.application_id
    assert response["normal"][0]["services"] == [profile_services[0]]
    assert response["normal"][1:] == (ebpf_apps if is_get_ebpf else [])
    assert response["no_data"] == []
    if is_get_ebpf:
        ebpf_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID)
    else:
        ebpf_query.assert_not_called()
