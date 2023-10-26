# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import mock
import pytest
from apm_web.meta.resources import ListApplicationAsyncResource
from apm_web.models import Application

pytestmark = pytest.mark.django_db


BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"

PARAM = {
    "application_id": 1,
    "app_name": APP_NAME,
    "app_alias": APP_ALIAS,
    "description": DESCRIPTION,
    "bk_biz_id": BK_BIZ_ID,
}


def test_list_application_async():

    Application.objects.create(**PARAM)

    miss_application = [{"application_id": 1, "bk_biz_id": 2, "app_name": "test_demo", "metric_result_table_id": ""}]
    mock.patch(
        'apm_web.meta.resources.ListApplicationAsyncResource.get_miss_application_and_cache_metric_data',
        return_value=(miss_application, {}),
    ).start()
    mock.patch(
        "apm_web.meta.resources.ListApplicationAsyncResource.get_metric_data",
        return_value={"1": {"service_count": 1}},
    ).start()

    validate_data = {"column": "service_count", "application_ids": ["1"], "bk_biz_id": 2}

    obj = ListApplicationAsyncResource()
    res = obj.perform_request(validate_data)

    assert len(res) == 1

    assert res[0].get("service_count", {}).get("value") == 1


def test_build_res():

    Application.objects.create(**PARAM)
    cache_metric_data = {"1": {"service_count": 10}}
    mock.patch(
        'apm_web.meta.resources.ListApplicationAsyncResource.get_miss_application_and_cache_metric_data',
        return_value=([], cache_metric_data),
    ).start()
    validate_data = {"column": "service_count", "application_ids": ["1"], "bk_biz_id": 2}

    obj = ListApplicationAsyncResource()
    res = obj.perform_request(validate_data)

    assert len(res) == 1

    assert res[0].get("service_count", {}).get("value") == 10
