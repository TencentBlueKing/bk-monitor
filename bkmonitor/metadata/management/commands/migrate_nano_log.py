"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from metadata import models
from metadata.models.constants import DT_TIME_STAMP_NANO, EPOCH_MILLIS_FORMAT, NANO_FORMAT, STRICT_NANO_ES_FORMAT
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "migrate nano log"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="bk tenant id", required=True)
        parser.add_argument("--space_type", type=str, help="space type", required=True)
        parser.add_argument("--space_id", type=str, help="space id", required=True)
        parser.add_argument("--table_id", type=str, help="table id", required=True)

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        space_type = options["space_type"]
        space_id = options["space_id"]
        table_id = options["table_id"]

        result_table = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        if not result_table:
            self.stderr.write(self.style.ERROR(f"result table not found: {table_id}"))
            return

        result_table_options = list(
            models.ResultTableOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
        )
        result_table_fields = list(models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id))
        result_table_field_options = list(
            models.ResultTableFieldOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
        )
        es_storage = models.ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        es_field_query_alias_options = list(
            models.ESFieldQueryAliasOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
        )

        # 复制新结果表相关配置
        new_table_id = f"{table_id}_nano"
        new_result_table = copy.deepcopy(result_table)
        new_result_table_options = copy.deepcopy(result_table_options)
        new_result_table_fields = copy.deepcopy(result_table_fields)
        new_result_table_field_options = copy.deepcopy(result_table_field_options)
        new_es_storage = copy.deepcopy(es_storage)
        new_es_field_query_alias_options = copy.deepcopy(es_field_query_alias_options)

        new_records_list = [
            new_result_table,
            *new_result_table_options,
            *new_result_table_fields,
            *new_result_table_field_options,
            new_es_storage,
            *new_es_field_query_alias_options,
        ]
        # 移除pk字段，替换table_id
        for record in new_records_list:
            record.pk = None
            record.table_id = new_table_id
            record.save()

        # 增加dtEventTimestampNanos字段，将旧的时间字段变更为毫秒
        models.ResultTableField.objects.create(
            table_id=new_table_id,
            field_name=DT_TIME_STAMP_NANO,
            field_type="timestamp",
            description="数据时间",
            tag="dimension",
            is_config_by_user=True,
            bk_tenant_id=bk_tenant_id,
        )

        # 通过复制的方式,生成dtEventTimestampNanos的option
        original_objects = models.ResultTableFieldOption.objects.filter(
            table_id=new_table_id, field_name="dtEventTimeStamp", bk_tenant_id=bk_tenant_id
        )

        # 创建新对象，修改 field_name 为 'dtEventTimeStampNanos'
        for obj in original_objects:
            # 使用 get_or_create 以确保不会重复创建相同的记录
            models.ResultTableFieldOption.objects.update_or_create(
                table_id=new_table_id,
                field_name="dtEventTimeStampNanos",  # 更新 field_name
                name=obj.name,
                defaults={  # 如果记录不存在，才会使用 defaults 来创建新的记录
                    "value_type": obj.value_type,
                    "value": obj.value,
                    "creator": obj.creator,
                    "bk_tenant_id": obj.bk_tenant_id,
                },
            )

        update_field_options = [
            ("dtEventTimeStampNanos", "es_type", NANO_FORMAT),
            ("dtEventTimeStampNanos", "es_format", STRICT_NANO_ES_FORMAT),
            ("dtEventTimeStamp", "es_format", EPOCH_MILLIS_FORMAT),
            ("dtEventTimeStamp", "es_type", "date"),
        ]

        for field_name, name, value in update_field_options:
            models.ResultTableFieldOption.objects.filter(
                table_id=new_table_id, field_name=field_name, name=name, bk_tenant_id=bk_tenant_id
            ).update(value=value)

        # 增加新表集群迁移记录，为了确保数据能够正常被查询，将enable_time设置为当前时间的前两年
        models.StorageClusterRecord.objects.update_or_create(
            table_id=new_table_id,
            cluster_id=new_es_storage.storage_cluster_id,
            bk_tenant_id=bk_tenant_id,
            defaults={"is_current": True, "enable_time": timezone.now() - timedelta(days=365 * 2)},
        )

        # 旧表标记与新表的关联关系，后续构建data_label查询路由时，需要根据此字段进行查询
        models.ResultTableOption.objects.get_or_create(
            table_id=table_id,
            name="es_related_query_table_id",
            bk_tenant_id=bk_tenant_id,
            defaults={"value": new_table_id},
        )

        # 将原本的索引集关联的虚拟RT进行复制
        virtual_es_storages = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id=table_id)
        virtual_table_ids = [es_storage.table_id for es_storage in virtual_es_storages]
        virtual_result_tables = models.ResultTable.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )
        virtual_result_table_options = models.ResultTableOption.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )
        virtual_result_table_fields = models.ResultTableField.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )
        virtual_result_table_field_options = models.ResultTableFieldOption.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )
        virtual_storage_cluster_records = models.StorageClusterRecord.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )
        virtual_es_field_query_alias_options = models.ESFieldQueryAliasOption.objects.filter(
            table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
        )

        # 获取虚拟RT的data_label
        virtual_data_labels = list(virtual_result_tables.values_list("data_label", flat=True))

        new_records_list = [
            *virtual_es_storages,
            *virtual_result_tables,
            *virtual_result_table_options,
            *virtual_result_table_fields,
            *virtual_result_table_field_options,
            *virtual_storage_cluster_records,
            *virtual_es_field_query_alias_options,
        ]
        for record in new_records_list:
            record.pk = None
            if hasattr(record, "origin_table_id"):
                record.origin_table_id = new_table_id
            if hasattr(record, "index_set") and getattr(record, "index_set", None):
                record.index_set += "_nano"
            record.table_id = record.table_id.split(".")[0] + "_nano" + ".__default__"
            record.save()

        # 新rt对应的虚拟路由表需要增加时间字段别名，兼容新旧rt时间字段
        for virtual_table_id in virtual_table_ids:
            # 设置新表时间字段别名
            models.ESFieldQueryAliasOption.objects.update_or_create(
                table_id=virtual_table_id,
                query_alias="dtEventTimeStamp",
                field_path="dtEventTimeStampNanos",
                bk_tenant_id=bk_tenant_id,
            )

        # 停用旧表的索引轮转并删除datasource关联，并更新新表的datasource关联
        es_storage.need_create_index = False
        es_storage.save()
        old_dsrt = models.DataSourceResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        bk_data_id = old_dsrt.bk_data_id
        old_dsrt.delete()
        models.DataSourceResultTable.objects.create(
            table_id=new_table_id, bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id
        )

        # 更新新表的索引轮转
        new_es_storage.create_index_v2()
        new_es_storage.create_or_update_aliases()

        # 刷新consul配置
        new_result_table.refresh_etl_config()

        # 刷新路由
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)
        SpaceTableIDRedis().push_data_label_table_ids(
            bk_tenant_id=bk_tenant_id, data_label_list=virtual_data_labels, is_publish=True
        )
        SpaceTableIDRedis().push_es_table_id_detail(
            bk_tenant_id=bk_tenant_id, table_id_list=virtual_table_ids + [new_table_id, table_id], is_publish=True
        )
