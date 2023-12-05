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
import json
import os
from typing import List, Optional

from django.conf import settings
from django.core.management import BaseCommand

from metadata import models
from metadata.models.space.constants import SYSTEM_USERNAME, EtlConfigs, SpaceTypes
from metadata.task.sync_space import push_and_publish_space_router


class Command(BaseCommand):
    """添加 bkci 对应的指标和维度信息"""

    help = "add metrics and dimensions of bkci"

    def add_arguments(self, parser):
        parser.add_argument("--space_id", type=str, required=False, help="space id")
        parser.add_argument("--bk_data_id", type=int, required=True, help="data source id")
        parser.add_argument("--mq_cluster_id", type=int, required=True, help="mq cluster id")

    def handle(self, *args, **options):
        # 获取参数
        space_id, bk_data_id, mq_cluster_id = options.get("space_id"), options["bk_data_id"], options["mq_cluster_id"]
        # 1. 创建bkci空间
        self._create_bkci_system_space(space_id)
        # 2. 创建数据源
        self._get_or_create_data_source(bk_data_id, mq_cluster_id)
        # 3. 创建空间和数据源的关联
        self._get_or_create_space_data_source(bk_data_id, space_id)
        # 4. 创建结果表
        # 获取初始化数据
        bkci_data_path = os.path.join(settings.BASE_DIR, "metadata/data/bkci_data.json")
        with open(bkci_data_path) as f:
            bkci_data = json.load(f)
        self.db_name = bkci_data["db_name"]
        self.metrics_and_dimensions = bkci_data["metrics_and_dimensions"]

        self._get_or_create_result_table(bk_data_id)
        # 5. 创建关联资源
        self._create_space_resource(space_id)
        # 6. 推送数据到 redis并发布
        # NOTE: 仅 bkci 类型更新
        push_and_publish_space_router(space_type=SpaceTypes.BKCI.value)

        print("init bkci data successfully")

    def _create_bkci_system_space(self, space_id: Optional[str] = None):
        """创建 bkci 的系统空间"""
        if not space_id:
            return
        models.Space.objects.get_or_create(
            space_type_id=SpaceTypes.BKCI.value, space_id=space_id, space_name="蓝盾运营管理平台"
        )

    def _get_or_create_data_source(self, bk_data_id: int, mq_cluster_id: int):
        # 如果已经存在，为防止类型不正确，更新一次
        data_source = models.DataSource.objects.filter(bk_data_id=bk_data_id)
        if data_source.exists():
            data_source.update(space_type_id=SpaceTypes.BKCI.value)
            return
        # 否则，创建之
        models.DataSource.create_data_source(
            operator=SYSTEM_USERNAME,
            bk_data_id=bk_data_id,
            data_name="bkci.pipeline",
            data_description="bkci pipeline data source",
            mq_cluster=mq_cluster_id,
            etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
            is_refresh_config=False,
            is_platform_data_id=True,
            type_label="time_series",
            source_label="bk_monitor",
            space_type_id=SpaceTypes.BKCI.value,
        )

    def _get_or_create_space_data_source(self, bk_data_id: int, space_id: Optional[str] = None):
        if not space_id:
            return
        models.SpaceDataSource.objects.get_or_create(
            space_type_id=SpaceTypes.BKCI.value,
            space_id=space_id,
            bk_data_id=bk_data_id,
            defaults={
                "creator": SYSTEM_USERNAME,
                "from_authorization": False,
            },
        )

    def _get_or_create_result_table(self, bk_data_id: int):
        """查询或创建结果表

        如果查询到，则直接返回
        否则，要创建结果表和对应的field
        """
        table_id_list = [f"{self.db_name}.{key}" for key in self.metrics_and_dimensions]
        existed_table_qs = models.ResultTable.objects.filter(table_id__in=table_id_list)
        existed_table_id_list = existed_table_qs.values_list("table_id", flat=True)
        # 过滤到需要创建或更新的结果表
        created_table_id_list = set(table_id_list) - set(existed_table_id_list)
        # 创建结果表
        self.stdout.write(f"create result table start, table id: {','.join(created_table_id_list)}")
        for table_id in created_table_id_list:
            field_list = self._get_rt_field_list(table_id)
            try:
                params = {
                    "table_id": table_id,
                    "bk_data_id": bk_data_id,
                    "table_name_zh": table_id,
                    "is_custom_table": False,
                    "schema_type": "fixed",
                    "operator": SYSTEM_USERNAME,
                    "default_storage": "influxdb",
                    "field_list": field_list,
                    "is_sync_db": False,
                    "bk_biz_id": 0,
                    "create_storage": False,
                }
                models.ResultTable.create_result_table(**params)
            except Exception as e:
                self.stderr.write(f"create result table failed, params: {json.dumps(params)}, err: {e}")
            else:
                self.stdout.write(f"create result table: {table_id} successfully")
        self.stdout.write("create result table end")
        # 更新结果表
        self.stdout.write(f"update result table start, table id: {','.join([t.table_id for t in existed_table_qs])}")
        for table in existed_table_qs:
            field_list = self._get_rt_field_list(table.table_id)
            try:
                table.modify(
                    operator=SYSTEM_USERNAME,
                    field_list=field_list,
                )
            except Exception as e:
                self.stdoerr.write(f"update result table failed, field_list: {json.dumps(field_list)}, err: {e}")
            else:
                self.stdout.write(f"update result table: {table.table_id} successfully")
        self.stdout.write("update result table end")

    def _get_rt_field_list(self, table_id: str) -> List:
        measurements = table_id.split(".")[-1]
        # 指标数据
        field_list = [
            {
                "table_id": table_id,
                "field_name": field_name,
                "field_type": field_type,
                "unit": "",
                "tag": models.ResultTableField.FIELD_TAG_METRIC,
                "is_config_by_user": True,
                "description": "",
                "default_value": "",
                "creator": SYSTEM_USERNAME,
                "last_modify_user": SYSTEM_USERNAME,
            }
            for field_name, field_type in self.metrics_and_dimensions[measurements]["metric"].items()
        ]
        # 维度数据
        field_list.extend(
            [
                {
                    "table_id": table_id,
                    "field_name": field_name,
                    "field_type": field_type,
                    "unit": "",
                    "tag": models.ResultTableField.FIELD_TAG_DIMENSION,
                    "is_config_by_user": True,
                    "description": "",
                    "default_value": "",
                    "creator": SYSTEM_USERNAME,
                    "last_modify_user": SYSTEM_USERNAME,
                }
                for field_name, field_type in self.metrics_and_dimensions[measurements]["dimension"].items()
            ]
        )

        return field_list

    def _create_space_resource(self, space_id: Optional[str] = None):
        """创建关联资源"""
        if not space_id:
            return

        models.SpaceResource.objects.get_or_create(
            space_type_id=SpaceTypes.BKCI.value,
            space_id=space_id,
            resource_type=SpaceTypes.BKCI.value,
            resource_id=space_id,
            defaults={"dimension_values": [{"project_id": space_id}]},
        )
