"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import caches

from apm_web.constants import ApmCacheKey, ServiceRelationLogTypeChoices
from apm_web.handlers.host_handler import HostHandler
from apm_web.models import LogServiceRelation
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import deserialize_and_decompress
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import FIVE_MIN_SECONDS
from core.drf_resource import api

if TYPE_CHECKING:
    from apm_web.models import Application

logger = logging.getLogger("apm")


def deserialize_service_related_log_indexes(cached_data: bytes) -> dict[str, list[dict[str, Any]]]:
    """反序列化并校验服务关联日志索引缓存。"""
    service_indexes: Any = deserialize_and_decompress(cached_data)
    if not isinstance(service_indexes, dict):
        raise TypeError("invalid service related log indexes cache structure")

    for service_name, indexes in service_indexes.items():
        if not isinstance(service_name, str) or not isinstance(indexes, list):
            raise TypeError("invalid service related log indexes cache structure")

        if any(not isinstance(index, dict) or index.get("index_set_id") is None for index in indexes):
            raise TypeError("invalid service related log indexes cache structure")

    return service_indexes


@using_cache(
    CacheType.APM(FIVE_MIN_SECONDS),
    func_key_generator=lambda func: f"{func.__module__}.{func.__name__}:{get_request_tenant_id(peaceful=True)}",
)
def get_biz_index_sets_with_cache(bk_biz_id: int) -> list[dict[str, Any]]:
    return api.log_search.search_index_set(bk_biz_id=bk_biz_id, bk_tenant_id=get_request_tenant_id(peaceful=True))


class ServiceLogHandler:
    """
    服务 - 日志工具类
    服务日志的来源：
    1. 应用自定义上报
    2. span 中主机关联采集项
    3. 服务关联日志
    """

    # ES 查询最大的服务数量
    SERVICE_MAX_SIZE = 1000
    # log 默认查询语句最大 value 数量
    LOG_DEFAULT_QUERY_CONDITION_MAX_SIZE = 20

    @staticmethod
    def get_cached_k8s_related_indexes(bk_biz_id: int, app_name: str) -> dict[str, list[dict[str, Any]]]:
        """读取后台发现的 K8S 日志关联关系。"""
        if "redis" not in caches:
            return {}

        cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=bk_biz_id, app_name=app_name)
        try:
            cached_data: bytes | None = caches["redis"].get(cache_key)
            return deserialize_service_related_log_indexes(cached_data) if cached_data else {}
        except Exception:  # noqa
            logger.exception("[GET_CACHED_K8S_RELATED_INDEXES] cache read failed: %s-%s", bk_biz_id, app_name)
            return {}

    @classmethod
    def list_available_related_services(cls, app: "Application", service_names: list[str]) -> set[str]:
        """按当前关联关系与后台索引状态快照，获取存在可用日志关联的服务。"""
        all_service_names = set(service_names)
        if not all_service_names or "redis" not in caches:
            return set()

        index_services: defaultdict[tuple[int, str], set[str]] = defaultdict(set)
        for relation in cls.get_log_relations(app.bk_biz_id, app.app_name, service_names, include_global=True):
            related_services = all_service_names if relation.is_global else {relation.service_name}
            for index_set_id in [*relation.value_list, relation.value]:
                if index_set_id:
                    index_services[(relation.related_bk_biz_id, str(index_set_id))].update(related_services)

        service_indexes = cls.get_cached_k8s_related_indexes(app.bk_biz_id, app.app_name)
        for service_name in all_service_names:
            for index in service_indexes.get(service_name, []):
                if index.get("bk_biz_id") is not None:
                    index_services[(index["bk_biz_id"], str(index["index_set_id"]))].add(service_name)

        if not index_services:
            return set()

        earliest_checked_at = time.time() - settings.APM_RELATED_LOG_INDEX_STATUS_CACHE_TTL
        available_services: set[str] = set()
        for bk_biz_id in {key[0] for key in index_services}:
            cache_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(
                bk_tenant_id=app.bk_tenant_id, bk_biz_id=bk_biz_id
            )
            try:
                snapshot = caches["redis"].get(cache_key)
                if not snapshot or snapshot["checked_at"] <= earliest_checked_at:
                    continue

                available_index_ids = {
                    str(index["index_set_id"]) for index in snapshot["indexes"] if index["available"] is True
                }
            except Exception:  # noqa
                logger.exception(
                    "[LIST_AVAILABLE_RELATED_SERVICES] snapshot read failed: bk_tenant_id=%s bk_biz_id=%s",
                    app.bk_tenant_id,
                    bk_biz_id,
                )
                continue

            for index_set_id in available_index_ids:
                available_services.update(index_services.get((bk_biz_id, index_set_id), ()))

        return available_services

    @classmethod
    def get_and_check_datasource_index_set_id(cls, bk_biz_id, app_name, full_indexes=None):
        """获取并校验 LogDatasource 的 IndexSetId"""

        ds = cls.get_log_datasource(bk_biz_id, app_name)
        if not ds:
            return None
        index_set_id = ds["index_set_id"]
        if not full_indexes:
            full_indexes = get_biz_index_sets_with_cache(bk_biz_id=bk_biz_id)

        index_set_info = next(
            (i for i in full_indexes if str(i.get("index_set_id", "")) == str(index_set_id)),
            None,
        )
        if index_set_info:
            return index_set_id

        # 如果不在接口返回的索引集中 说明此自定义上报在日志平台中已经停止
        return None

    @classmethod
    def get_log_datasource(cls, bk_biz_id, app_name):
        application_info = api.apm_api.detail_application(bk_biz_id=bk_biz_id, app_name=app_name)
        if not application_info.get("log_config"):
            return None
        return application_info["log_config"]

    @classmethod
    def list_host_indexes_by_span(cls, bk_biz_id, app_name, span_id, span_detail=None):
        """从 span 中找主机关联的采集项"""
        span_hosts = HostHandler.find_host_in_span(bk_biz_id, app_name, span_id, span_detail)

        if span_hosts:
            from monitor_web.scene_view.resources import HostIndexQueryMixin

            pool = ThreadPool()
            indies = pool.map_ignore_exception(
                HostIndexQueryMixin.query_indexes,
                [({"bk_biz_id": bk_biz_id, "bk_host_id": i["bk_host_id"]},) for i in span_hosts],
            )

            res = []
            for index, i in enumerate(indies):
                if not i:
                    continue
                for j in i:
                    res.append(
                        {
                            **j,
                            "addition": [
                                {
                                    "field": "*",
                                    "operator": "contains match phrase",
                                    "value": [span_hosts[index]["bk_host_innerip"]],
                                }
                            ],
                        }
                    )
            return res

        return []

    @classmethod
    def get_log_relations(
        cls, bk_biz_id: int, app_name: str, service_names: list[str] | None, include_global: bool = True
    ) -> list[LogServiceRelation]:
        """获取服务关联的日志"""
        return list(
            LogServiceRelation.get_relation_qs(
                bk_biz_id,
                app_name,
                service_names,
                include_global=include_global,
                log_type=ServiceRelationLogTypeChoices.BK_LOG,
            )
        )

    @staticmethod
    def list_indexes_by_relation(
        bk_biz_id: int,
        app_name: str,
        service_name: str | None,
    ) -> list[dict[str, Any]]:
        """从缓存获取服务关联的 K8S 日志索引集。"""
        if not service_name or "redis" not in caches:
            return []

        cache_key: str = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
            bk_biz_id=bk_biz_id, app_name=app_name
        )
        try:
            cached_data: bytes | None = caches["redis"].get(cache_key)
            if not cached_data:
                return []

            service_indexes = deserialize_service_related_log_indexes(cached_data)
            return service_indexes.get(service_name, [])
        except Exception:  # noqa
            logger.exception(
                "[LIST_INDEXES_BY_RELATION] cache read failed: %s-%s-%s",
                bk_biz_id,
                app_name,
                service_name,
            )
            return []

    @staticmethod
    def get_data_id_rt_map(data_ids: list[int]) -> dict[int, set[str]]:
        """获取 data_id 与 result_table_id 的映射。"""

        # 这里直接从 metadata 查询，是为了解决跨业务关联的场景
        # data_id -> table_id -> index_set_id
        # 这里待 metadata 有相关接口后，需要改为走 api 形式查询，去掉模块之间的依赖
        from metadata import models

        data_id_rt_map: defaultdict[int, set[str]] = defaultdict(set)
        for data_id, result_table_id in models.DataSourceResultTable.objects.filter(  # pyright: ignore[reportAttributeAccessIssue]
            bk_data_id__in=data_ids
        ).values_list("bk_data_id", "table_id"):
            data_id_rt_map[data_id].add(result_table_id)

        return dict(data_id_rt_map)
