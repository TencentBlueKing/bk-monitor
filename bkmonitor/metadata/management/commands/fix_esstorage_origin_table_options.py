"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import logging
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Q

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill ESStorage index_set and ResultTableOption for origin ES tables."

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="租户ID")
        parser.add_argument("--bk_biz_id", type=int, help="业务ID", default=0)
        parser.add_argument(
            "--datasource_created_from",
            type=str,
            choices=[DataIdCreatedFromSystem.BKGSE.value, DataIdCreatedFromSystem.BKDATA.value],
            default=None,
            help="按 RT 关联的数据源来源过滤，仅处理 bkgse 或 bkdata 来源的数据源关联 RT",
        )
        parser.add_argument("--dry_run", action="store_true", help="只统计待修复数量，不写入数据库")

    def handle(self, *args, **options):
        bk_tenant_id: str = options["bk_tenant_id"]
        bk_biz_id: int = options["bk_biz_id"]

        # 填充index_set
        index_set_table_ids = self.fill_esstorage_index_set(bk_tenant_id, bk_biz_id, options["dry_run"])

        # 补充rt options
        option_table_ids = self.fill_rt_options(bk_tenant_id, bk_biz_id, options["dry_run"])

        # 指定业务时立即刷新路由；全量执行时等待定时任务刷新
        if bk_biz_id != 0 and not options["dry_run"]:
            table_id_list = sorted(set(index_set_table_ids) | set(option_table_ids))
            if table_id_list:
                self.refresh_routes(bk_tenant_id, table_id_list)

    def refresh_routes(self, bk_tenant_id: str, table_id_list: list[str]):
        """刷新路由

        Args:
            bk_tenant_id: 租户 ID
            table_id_list: 结果表 ID 列表
        """
        client = SpaceTableIDRedis()
        client.push_es_table_id_detail(bk_tenant_id, table_id_list=table_id_list, is_publish=True)

    @classmethod
    def _query_table_options(
        cls, bk_tenant_id: str, table_ids: list[str], names: list[str], batch_size: int = 500
    ) -> dict[tuple[str, str], models.ResultTableOption]:
        exists_options: dict[tuple[str, str], models.ResultTableOption] = {}
        for i in range(0, len(table_ids), batch_size):
            batch_table_ids = table_ids[i : i + batch_size]
            options = models.ResultTableOption.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id__in=batch_table_ids, name__in=names
            ).only("table_id", "name", "value", "value_type")
            for option in options:
                exists_options[(option.table_id, option.name)] = option
        return exists_options

    def fill_rt_options(self, bk_tenant_id: str, bk_biz_id: int, dry_run: bool = True):
        # 查询所有实体表
        es_storage_queryset = models.ESStorage.objects.filter(
            Q(origin_table_id__isnull=True) | Q(origin_table_id=""),
            need_create_index=True,
            bk_tenant_id=bk_tenant_id,
        )

        # 如果业务非0，则按业务过滤
        if bk_biz_id > 0:
            es_storage_queryset = es_storage_queryset.filter(table_id__startswith=f"{bk_biz_id}_")
        elif bk_biz_id < 0:
            es_storage_queryset = es_storage_queryset.filter(
                Q(table_id__startswith=f"{bk_biz_id}_") | Q(table_id__startswith=f"space_{abs(bk_biz_id)}_")
            )

        table_ids: list[str] = list(es_storage_queryset.values_list("table_id", flat=True))

        # 查询所有实体表的options
        batch_size = 500
        exists_options: dict[tuple[str, str], models.ResultTableOption] = self._query_table_options(
            bk_tenant_id, table_ids, ["need_add_time", "time_field"], batch_size
        )

        # 补充need_add_time
        need_add_time_options: list[models.ResultTableOption] = []
        need_add_time_table_ids: list[str] = []
        for table_id in table_ids:
            if (table_id, "need_add_time") in exists_options:
                continue
            need_add_time_options.append(
                models.ResultTableOption(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    name="need_add_time",
                    value="true",
                    value_type="bool",
                    creator="system",
                )
            )
            need_add_time_table_ids.append(table_id)
            logger.info(f"create need_add_time option: {bk_tenant_id} {table_id}")

        if len(need_add_time_options) > 0:
            if not dry_run:
                logger.info(f"create need_add_time options: {len(need_add_time_options)}")
                models.ResultTableOption.objects.bulk_create(need_add_time_options, batch_size=500)
            else:
                logger.info("dry run, no database changes applied")
        else:
            logger.info("no need_add_time options to create")

        # 补充time_field
        time_field_options: list[models.ResultTableOption] = []
        time_field_table_ids: list[str] = []
        query_virtual_table_ids: list[str] = []
        for table_id in table_ids:
            # 如果已经存在time_field option，则跳过
            if (table_id, "time_field") in exists_options:
                continue

            # 如果table_id包含_bkmonitor_event_，是自定义事件表，可以直接添加time_field
            if re.match(r"^(\d+_)?bkmonitor_event_\d+$", table_id):
                time_field_options.append(
                    models.ResultTableOption(
                        bk_tenant_id=bk_tenant_id,
                        table_id=table_id,
                        name="time_field",
                        creator="system",
                        value='{"name":"time","type":"date","unit":"millisecond"}',
                        value_type="dict",
                    )
                )
                time_field_table_ids.append(table_id)
                logger.info(
                    f'create time_field option: {table_id} -> {{"name":"time","type":"date","unit":"millisecond"}}'
                )
                continue

            # 其他表先查询关联的虚拟表的time_field
            query_virtual_table_ids.append(table_id)

        # 使用关联的虚拟表的time_field options补充实体表的time_field options
        if len(query_virtual_table_ids) > 0:
            # 查询实体表关联的虚拟表
            virtual_tables: list[tuple[str, str]] = list(
                models.ESStorage.objects.filter(
                    bk_tenant_id=bk_tenant_id, origin_table_id__in=query_virtual_table_ids
                ).values_list("origin_table_id", "table_id")
            )

            # 将虚拟表按实体表分组
            origin_to_virtual_table_ids: dict[str, list[str]] = defaultdict(list)
            for origin_table_id, virtual_table_id in virtual_tables:
                origin_to_virtual_table_ids[origin_table_id].append(virtual_table_id)

            # 查询虚拟表的time_field options
            virtual_table_options = self._query_table_options(
                bk_tenant_id,
                list(itertools.chain.from_iterable(origin_to_virtual_table_ids.values())),
                ["time_field"],
                batch_size,
            )
            for origin_table_id, virtual_table_ids in origin_to_virtual_table_ids.items():
                source_option = next(
                    (
                        virtual_table_options[(virtual_table_id, "time_field")]
                        for virtual_table_id in virtual_table_ids
                        if (virtual_table_id, "time_field") in virtual_table_options
                    ),
                    None,
                )
                if source_option:
                    time_field_value = source_option.value
                    logger.info(f"create time_field option from virtual table: {origin_table_id} -> {time_field_value}")
                else:
                    # 如果没有关联的虚拟表有time_field option，则使用dtEventTimeStamp作为time_field
                    time_field_value = '{"name":"dtEventTimeStamp","type":"date","unit":"millisecond"}'
                    logger.info(f"create time_field option by default: {origin_table_id} -> {time_field_value}")

                time_field_options.append(
                    models.ResultTableOption(
                        bk_tenant_id=bk_tenant_id,
                        table_id=origin_table_id,
                        name="time_field",
                        value=time_field_value,
                        value_type="dict",
                        creator="system",
                    )
                )
                time_field_table_ids.append(origin_table_id)

        # 创建time_field options
        if len(time_field_table_ids) > 0:
            if not dry_run:
                logger.info(f"create time_field options: {len(time_field_options)}")
                models.ResultTableOption.objects.bulk_create(time_field_options, batch_size=500)
            else:
                logger.info("dry run, no database changes applied")
        else:
            logger.info("no time_field options to create")

        return table_ids

    def fill_esstorage_index_set(self, bk_tenant_id: str, bk_biz_id: int, dry_run: bool = True):
        """填充esstorage的index_set

        1. 找出index_set为空的实体表, 排除索引集表
        2. 将table_id中的点替换成下划线, 更新esstorage的index_set

        Args:
            bk_tenant_id: 租户 ID
            bk_biz_id: 业务 ID
            dry_run: 是否只统计待修复数量，不写入数据库
        """

        # 找出index_set为空的实体表，排除索引集表
        es_storage_queryset = (
            models.ESStorage.objects.filter(Q(index_set__isnull=True) | Q(index_set=""))
            .filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
            .filter(need_create_index=True, bk_tenant_id=bk_tenant_id)
            .exclude(table_id__startswith="bklog_index_set_")
        )

        if bk_biz_id > 0:
            es_storage_queryset = es_storage_queryset.filter(table_id__startswith=f"{bk_biz_id}_")
        elif bk_biz_id < 0:
            es_storage_queryset = es_storage_queryset.filter(
                Q(table_id__startswith=f"{bk_biz_id}_") | Q(table_id__startswith=f"space_{abs(bk_biz_id)}_")
            )

        update_objects: list[models.ESStorage] = []
        table_ids: list[str] = []
        for ess in es_storage_queryset:
            ess.index_set = ess.table_id.replace(".", "_")
            update_objects.append(ess)
            table_ids.append(ess.table_id)
            logger.info(f"update esstorage index_set: {ess.table_id} -> {ess.index_set}")

        # 如果非dry_run，则更新数据库
        if not dry_run:
            if len(update_objects) > 0:
                logger.info(f"update esstorage index_set: {len(update_objects)}")
                models.ESStorage.objects.bulk_update(update_objects, ["index_set"], batch_size=500)
            else:
                logger.info("no esstorage index_set to update")
        else:
            logger.info("dry run, no database changes applied")

        logger.info(f"fill esstorage index_set success: {len(update_objects)}")
        return table_ids
