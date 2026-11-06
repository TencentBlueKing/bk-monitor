"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

from django.core.cache import cache, caches
from django.test import override_settings
from pytest_mock import MockerFixture

from api.apm_api.default import QueryInstanceResource, QueryTopoNodeResource
from apm_web.constants import DataStatus
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application


@override_settings(
    ENVIRONMENT="production",
    ROLE="api",
    ENABLE_RESOURCE_DATA_COLLECT=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "apm-service-status-backend",
        },
        "locmem": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "apm-service-status-local",
        },
    },
)
def test_service_status_with_discovery_and_cache_delay(mocker: MockerFixture) -> None:
    started_at = 2_000_000_000
    now = [started_at]
    previous_data_at = started_at - 19 * 60
    nodes = [{"topo_key": "orders", "heartbeat": {"trace": {"last_data_at": previous_data_at}}}]
    app = Application(bk_biz_id=2, app_name="cache-delay", is_enabled_trace=True)
    app.no_data_period = 10
    mocker.patch("apm_web.handlers.service_handler.time.time", side_effect=lambda: now[0])
    mocker.patch("bkmonitor.utils.cache.monotonic", side_effect=lambda: now[0])
    mocker.patch("bkmonitor.utils.cache.mem_cache", caches["locmem"])
    query = mocker.patch.object(QueryTopoNodeResource, "perform_request", side_effect=lambda _params: deepcopy(nodes))
    resource = QueryTopoNodeResource()
    observed = []
    cache.clear()
    caches["locmem"].clear()
    ServiceHandler.list_nodes.cache_clear()
    try:
        # 发现任务排队时，旧心跳的数据龄会超过 20 分钟；两级缓存仍会继续持有该心跳。
        for elapsed in (0, 59, 61, 280):
            now[0] = started_at + elapsed
            services = ServiceHandler.list_nodes(app.bk_biz_id, app.app_name)
            status = ServiceHandler.build_service_data_status(app, services, data_type="trace")["orders"]["trace"]
            observed.append((services[0]["heartbeat"]["trace"]["last_data_at"], query.call_count, status))

        now[0] = started_at + 281
        nodes[0]["heartbeat"]["trace"]["last_data_at"] = now[0]
        now[0] = started_at + 299
        cached_nodes = resource.request(bk_biz_id=app.bk_biz_id, app_name=app.app_name)
        assert cached_nodes[0]["heartbeat"]["trace"]["last_data_at"] == previous_data_at
        assert query.call_count == 1

        now[0] = started_at + 301
        cached_nodes = resource.request(bk_biz_id=app.bk_biz_id, app_name=app.app_name)
        assert cached_nodes[0]["heartbeat"]["trace"]["last_data_at"] == started_at + 281
        assert query.call_count == 2

        # API 缓存已刷新，ServiceHandler 仍保留第 280 秒读取的旧心跳，直到本地 60 秒缓存过期。
        for elapsed in (301, 339, 341):
            now[0] = started_at + elapsed
            services = ServiceHandler.list_nodes(app.bk_biz_id, app.app_name)
            status = ServiceHandler.build_service_data_status(app, services, data_type="trace")["orders"]["trace"]
            observed.append((services[0]["heartbeat"]["trace"]["last_data_at"], query.call_count, status))

        assert observed == (
            [(previous_data_at, 1, DataStatus.NORMAL)] * 4
            + [(previous_data_at, 2, DataStatus.NORMAL)] * 2
            + [(started_at + 281, 2, DataStatus.NORMAL)]
        )
        assert QueryInstanceResource.backend_cache_type.timeout == 10 * 60
    finally:
        ServiceHandler.list_nodes.cache_clear()
        cache.clear()
        caches["locmem"].clear()
