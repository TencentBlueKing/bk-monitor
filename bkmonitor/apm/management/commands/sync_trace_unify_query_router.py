"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import threading

from bkmonitor.utils.thread_backend import run_threads, InheritParentThread
from bkmonitor.utils.user import get_global_user
from constants.apm import PreCalculateSpecificField, TRACE_RESULT_TABLE_OPTION, PRECALCULATE_RESULT_TABLE_OPTION
from core.drf_resource import resource
from django.utils.translation import gettext_lazy as _

from typing import Any

from django.core.management.base import BaseCommand

logging.basicConfig(format="%(levelname)s [%(asctime)s] %(name)s | %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)


DEFAULT_CONCURRENCY: int = 10

PRECALCULATE_TYPE: str = "precalculate"


class Command(BaseCommand):
    """同步 Trace Unify-Query 检索路由
    - 将查询切换到 Unify-Query 后，需要在存量数据源增加路由信息。
    - 命令可以多次执行，支持可重入，同时不会对现有 ES 查询产生影响。
    - Benchmarks（-c 10）：215 Apps，25s。
    """

    help = "sync trace unify-query router"

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk-biz-ids", nargs="+", type=int, default=[], help=_("业务 ID 列表"))
        parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="并发数量")

    def handle(self, *args, **options):
        from apm.models.datasource import TraceDataSource, DataLink

        bk_biz_ids: list[int] = options.get("bk_biz_ids") or []
        concurrency: int = int(options.get("concurrency") or DEFAULT_CONCURRENCY)
        self.sync_router(bk_biz_ids, concurrency, TraceDataSource, DataLink)

    @classmethod
    def sync_router(cls, bk_biz_ids: list[int], concurrency: int, trace_datasource_model, data_link_model):
        logger.info(
            "[sync_trace_unify_query_router] started with bk_biz_ids: %s, concurrency: %s", bk_biz_ids, concurrency
        )

        # 默认迁移全部
        queryset = trace_datasource_model.objects.all()
        if bk_biz_ids:
            queryset = queryset.filter(bk_biz_id__in=bk_biz_ids)

        trace_datasources: list[dict[str, str]] = list(queryset.values("result_table_id"))
        for data_link in data_link_model.objects.all():
            # 增加预计算表
            for cluster_info in data_link.pre_calculate_config.get("cluster") or []:
                result_table_id: str | None = cluster_info.get("table_name")
                if not result_table_id:
                    continue
                trace_datasources.append({"result_table_id": result_table_id, "type": PRECALCULATE_TYPE})

        logger.info("[sync_trace_unify_query_router] total -> %s", len(trace_datasources))

        err_trace_datasources: list[dict[str, str]] = cls._sync_router(trace_datasources, concurrency)
        if err_trace_datasources:
            # 尝试再次同步失败的数据源
            err_trace_datasources = cls._sync_router(err_trace_datasources, concurrency)

        logger.info(
            "[sync_trace_unify_query_router] finished, total -> %s, error num -> %s",
            len(trace_datasources),
            len(err_trace_datasources),
        )

    @classmethod
    def _sync_single_router(
        cls, datasource: dict[str, str], err_trace_datasources: list[dict[str, str]], lock: threading.Lock
    ):
        """同步单个数据源的路由"""
        table_id: str = datasource["result_table_id"]
        modify_params: dict[str, Any] = {"table_id": table_id, "operator": get_global_user()}
        if datasource.get("type") == PRECALCULATE_TYPE:
            # 默认情况下，预计算表需要按业务 ID 进行隔离查询。
            modify_params["bk_biz_id_alias"] = PreCalculateSpecificField.BIZ_ID.value
            modify_params["option"] = PRECALCULATE_RESULT_TABLE_OPTION
        else:
            # metadata 的 option 不支持增量更新，这里需要传入完整的 option。
            modify_params["option"] = TRACE_RESULT_TABLE_OPTION

        try:
            resource.metadata.modify_result_table(modify_params)
            resource.metadata.create_or_update_es_router(
                {"table_id": table_id, "index_set": table_id.replace(".", "_")}
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "[sync_trace_unify_query_router] failed to sync router: table_id -> %s, err -> %s", table_id, e
            )
            with lock:
                err_trace_datasources.append(datasource)
        else:
            logger.info("[sync_trace_unify_query_router] success to sync router: table_id -> %s", table_id)

    @classmethod
    def _sync_router(cls, trace_datasources: list[dict[str, str]], concurrency: int) -> list[dict[str, str]]:
        """同步路由"""
        lock: threading.Lock = threading.Lock()
        err_trace_datasources: list[dict[str, str]] = []
        for idx in range(0, len(trace_datasources), concurrency):
            run_threads(
                [
                    InheritParentThread(target=cls._sync_single_router, args=(datasource, err_trace_datasources, lock))
                    for datasource in trace_datasources[idx : idx + concurrency]
                ]
            )

        logger.info("[sync_trace_unify_query_router] sync router finished, error num -> %s", len(err_trace_datasources))
        return err_trace_datasources
