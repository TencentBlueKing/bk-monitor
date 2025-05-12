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

from django.db.models import QuerySet, Q

from constants.apm import PreCalculateSpecificField, TRACE_RESULT_TABLE_OPTION, PRECALCULATE_RESULT_TABLE_OPTION
from django.utils.translation import gettext_lazy as _

from typing import Any, TYPE_CHECKING

from django.core.management.base import BaseCommand

from metadata.models.common import OptionBase
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

if TYPE_CHECKING:
    from metadata.models import ResultTable, ResultTableOption, ESStorage

logging.basicConfig(format="%(levelname)s [%(asctime)s] %(name)s | %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)


DEFAULT_BATCH_SIZE: int = 1000

APM_PRECALCULATE_TABLE_PREFIX: str = "apm_global.precalculate_storage"


class Command(BaseCommand):
    """同步 Trace Unify-Query 检索路由
    - 将查询切换到 Unify-Query 后，需要在存量数据源增加路由信息。
    - 命令可以多次执行，支持可重入，同时不会对现有 ES 查询产生影响。
    """

    help = "sync trace unify-query router"

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk-biz-ids", nargs="+", type=int, default=[], help=_("业务 ID 列表"))
        parser.add_argument("-c", "--batch-size", type=str, help="同步批次大小")

    def handle(self, *args, **options):
        bk_biz_ids: list[int] = options.get("bk_biz_ids") or []
        batch_size: int = int(options.get("batch_size") or DEFAULT_BATCH_SIZE)

        from metadata.models import ResultTable, ResultTableOption, ESStorage

        self.batch_sync_router(ESStorage, ResultTable, ResultTableOption, batch_size, bk_biz_ids)

    @classmethod
    def is_precalculate(cls, table_id: str) -> bool:
        return APM_PRECALCULATE_TABLE_PREFIX in table_id

    @classmethod
    def batch_sync_router(
        cls,
        es_storage_model: type["ESStorage"],
        result_table_model: type["ResultTable"],
        result_table_option_model: type["ResultTableOption"],
        batch_size: int = DEFAULT_BATCH_SIZE,
        bk_biz_ids: list[int] | None = None,
        push_now: bool = True,
    ):
        """分批同步检索路由"""
        queryset: QuerySet = (
            result_table_model.objects
            # 只过滤出 APM 相关的结果表。
            .filter(Q(table_id__contains="bkapm.trace") | Q(table_id__contains=APM_PRECALCULATE_TABLE_PREFIX))
            .values("table_id", "bk_biz_id")
            .order_by("table_id")
        )
        # 不指定业务 ID 时，默认迁移全部。
        if bk_biz_ids:
            queryset = queryset.filter(bk_biz_id__in=bk_biz_ids)

        total: int = queryset.count()
        for begin_idx in range(0, total, batch_size):
            logger.info(
                "[sync_trace_unify_query_router] started with "
                "begin_idx: %s, bk_biz_ids: %s, batch_size: %s, total: %s.",
                begin_idx,
                bk_biz_ids,
                batch_size,
                total,
            )
            result_table_infos: list[dict[str, Any]] = list(queryset[begin_idx : begin_idx + batch_size])
            cls.sync_router(
                result_table_infos, es_storage_model, result_table_model, result_table_option_model, push_now
            )

    @classmethod
    def sync_router(
        cls,
        result_table_infos: list[dict[str, Any]],
        es_storage_model: type["ESStorage"],
        result_table_model: type["ResultTable"],
        result_table_option_model: type["ResultTableOption"],
        push_now: bool = True,
    ):
        table_ids: list[str] = []

        # Step-1: 预计算表默认按业务 ID 进行查询隔离。
        to_be_updated_rts: list[result_table_model] = []
        for result_table_info in result_table_infos:
            table_id: str = result_table_info["table_id"]
            if cls.is_precalculate(table_id=table_id):
                to_be_updated_rts.append(
                    result_table_model(table_id=table_id, bk_biz_id_alias=PreCalculateSpecificField.BIZ_ID.value)
                )

            table_ids.append(table_id)

        result_table_model.objects.bulk_update(to_be_updated_rts, fields=["bk_biz_id_alias"])
        logger.info("[sync_trace_unify_query_router] update rt -> %s", len(to_be_updated_rts))

        # Step-2: ESStorage 指定索引集。
        to_be_updated_storages: list[es_storage_model] = []
        for table_id in es_storage_model.objects.filter(table_id__in=table_ids).values_list("table_id", flat=True):
            to_be_updated_storages.append(es_storage_model(table_id=table_id, index_set=table_id.replace(".", "_")))

        es_storage_model.objects.bulk_update(to_be_updated_storages, fields=["index_set"])
        logger.info("[sync_trace_unify_query_router] sync index_set to ESStorage: %s", len(to_be_updated_storages))

        # Step-3：设置查询选项，例如事件字段、是否在查询索引中增加日期等。
        rt_option_map: dict[str, Any] = {
            f"{_rt_option['table_id']}-{_rt_option['name']}": _rt_option
            for _rt_option in result_table_option_model.objects.filter(table_id__in=table_ids).values(
                "id", "table_id", "name"
            )
        }
        to_be_created_rt_options: list[result_table_option_model] = []
        to_be_updated_rt_options: list[result_table_option_model] = []
        for table_id in table_ids:
            if cls.is_precalculate(table_id=table_id):
                result_table_options: dict[str, Any] = PRECALCULATE_RESULT_TABLE_OPTION
            else:
                result_table_options: dict[str, Any] = TRACE_RESULT_TABLE_OPTION

            for option_name, option_value in result_table_options.items():
                if option_name not in ["need_add_time", "time_field"]:
                    continue

                value, value_type = OptionBase._parse_value(option_value)
                rt_option: result_table_option_model = result_table_option_model(
                    table_id=table_id, name=option_name, value=value, value_type=value_type
                )
                rt_option_key: str = f"{table_id}-{option_name}"
                if rt_option_key in rt_option_map:
                    rt_option.id = rt_option_map[rt_option_key]["id"]
                    to_be_updated_rt_options.append(rt_option)
                else:
                    to_be_created_rt_options.append(rt_option)

        result_table_option_model.objects.bulk_create(to_be_created_rt_options)
        result_table_option_model.objects.bulk_update(to_be_updated_rt_options, fields=["value_type", "value"])
        logger.info(
            "[sync_trace_unify_query_router] update or create rt options: create -> %s, update -> %s",
            len(to_be_created_rt_options),
            len(to_be_updated_rt_options),
        )

        # 立即同步到缓存。
        if push_now:
            client = SpaceTableIDRedis()
            client.push_es_table_id_detail(table_id_list=table_ids, is_publish=True)
