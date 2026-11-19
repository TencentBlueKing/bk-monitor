"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from types import SimpleNamespace

import pytest
from requests import Response
from requests.exceptions import ReadTimeout

from bkmonitor.define.global_config import ADVANCED_OPTIONS
from bkmonitor.models import GlobalConfig
from bkmonitor.utils import dynamic_settings
from core.errors.api import BKAPIError
from metadata import models
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.utils.redis_tools import RedisTools


@pytest.fixture
def worker_http(settings, mocker):
    settings.ENABLE_BMW_ROUTE_REFRESH = True
    settings.BMW_API_URL = "http://worker.test:10211/"
    mocker.patch("core.drf_resource.contrib.api.metrics.report_all")
    response = Response()
    response.status_code = 200
    response._content = b'{"result":true,"code":0,"data":null}'
    return mocker.patch("requests.Session.request", return_value=response)


def assert_worker_post(http, route, **payload):
    http.assert_called_once()
    request = http.call_args.kwargs
    assert request["method"] == "POST"
    assert request["url"] == f"http://worker.test:10211/bmw/metadata/routes/{route}/refresh"
    assert request["json"] == {"bk_tenant_id": "tenant-a", **payload}
    assert request["headers"]["X-Bk-Tenant-Id"] == "tenant-a"


@pytest.mark.django_db(databases="__all__")
def test_dynamic_switch_defaults_off_and_can_be_toggled(mocker):
    key = "ENABLE_BMW_ROUTE_REFRESH"
    assert ADVANCED_OPTIONS[key].default is False
    mocker.patch.object(dynamic_settings, "locmem_cache", None)
    mocker.patch.object(dynamic_settings, "redis_cache", None)
    GlobalConfig.objects.filter(key=key).delete()
    config = dynamic_settings.DynamicSettings(SimpleNamespace(ENABLE_BMW_ROUTE_REFRESH=False), GlobalConfig)
    assert config.ENABLE_BMW_ROUTE_REFRESH is False
    config.ENABLE_BMW_ROUTE_REFRESH = True
    assert GlobalConfig.get(key) is True
    assert config.ENABLE_BMW_ROUTE_REFRESH is True
    config.ENABLE_BMW_ROUTE_REFRESH = False
    assert GlobalConfig.get(key) is False


@pytest.mark.parametrize("kwargs, expected", [({}, False), ({"is_publish": True}, True)])
def test_result_table_refresh(worker_http, kwargs, expected):
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id="tenant-a", table_id_list=["demo.cpu"], **kwargs)
    assert_worker_post(worker_http, "result-table", table_ids=["demo.cpu"], is_publish=expected)


def test_space_refresh_uses_space_tenant(worker_http, mocker):
    space = mocker.patch.object(models.Space.objects, "get", return_value=SimpleNamespace(bk_tenant_id="tenant-a"))
    SpaceTableIDRedis().push_space_table_ids("bkcc", 2)
    space.assert_called_once_with(space_type_id="bkcc", space_id="2")
    assert_worker_post(worker_http, "space", space_type="bkcc", space_id="2")


@pytest.mark.parametrize(
    "targets, expected",
    [
        ({"table_id_list": ["demo.cpu"]}, {"table_ids": ["demo.cpu"]}),
        ({"data_label_list": ["removed,cpu", "cpu"]}, {"data_labels": ["removed", "cpu"]}),
    ],
)
def test_data_label_refresh(worker_http, targets, expected):
    SpaceTableIDRedis().push_data_label_table_ids(bk_tenant_id="tenant-a", **targets)
    assert_worker_post(worker_http, "data-label", **expected)


@pytest.mark.django_db(databases="__all__")
def test_data_label_refresh_with_both_filters(worker_http):
    models.ResultTable.objects.create(
        table_id="demo.cpu", data_label="cpu,system", bk_tenant_id="tenant-a", is_custom_table=False
    )
    router = SpaceTableIDRedis()
    router.push_data_label_table_ids(
        bk_tenant_id="tenant-a", table_id_list=["demo.cpu"], data_label_list=["cpu,removed"]
    )
    assert_worker_post(worker_http, "data-label", data_labels=["cpu"])

    worker_http.reset_mock()
    router.push_data_label_table_ids(bk_tenant_id="tenant-a", table_id_list=["demo.cpu"], data_label_list=["removed"])
    worker_http.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("targets", [None, []])
def test_full_data_label_refresh_uses_local_routes(worker_http, mocker, targets, settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    models.ResultTable.objects.create(
        table_id="demo.cpu", data_label="cpu", bk_tenant_id="tenant-a", is_custom_table=False
    )
    write = mocker.patch.object(RedisTools, "hmset_to_redis")
    SpaceTableIDRedis().push_data_label_table_ids(
        bk_tenant_id="tenant-a", table_id_list=targets, data_label_list=targets
    )
    worker_http.assert_not_called()
    write.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_KEY, {"cpu": json.dumps(["demo.cpu"])})


@pytest.mark.parametrize("timeout", [True, False], ids=["read-timeout", "http-500"])
def test_worker_failure_propagates(worker_http, timeout):
    if timeout:
        worker_http.side_effect = ReadTimeout()
    else:
        worker_http.return_value.status_code = 500

    with pytest.raises(BKAPIError):
        SpaceTableIDRedis().push_table_id_detail(bk_tenant_id="tenant-a", table_id_list=["demo.cpu"])
    worker_http.assert_called_once()
