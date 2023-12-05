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

from typing import List, Optional

from django.core.management import BaseCommand, CommandError

from metadata import models
from metadata.models.space.constants import SpaceTypes


class Command(BaseCommand):
    help = "调整数据源所属的空间类型"

    def add_arguments(self, parser):
        parser.add_argument("--space_type_id", type=str, help="space type of the data source")
        parser.add_argument("--data_id", action="append", required=False, help="data id list")

    def handle(self, *args, **options):
        """
        使用说明:
        python manage.py modify_data_source_space_type --data_id=1 --space_type_id=bkcc
        """
        data_id_list, space_type_id = options.get("data_id"), options.get("space_type_id")
        # 判断数据源 ID
        self._validate_data_source(data_id_list)
        # 更改对应类型，如果没有传递data id，则更改所有记录
        self._validate_space_type(space_type_id)
        self._update(space_type_id, data_id_list)

        print("update space type of data source successfully")

    def _validate_data_source(self, data_id_list: List) -> None:
        """校验数据源是否存在"""
        if not data_id_list:
            return
        existed_data_id_list = models.DataSource.objects.filter(bk_data_id__in=data_id_list).values_list(
            "bk_data_id", flat=True
        )
        # 用以返回不存在的 data id
        diff = set(data_id_list) - set(existed_data_id_list)
        if diff:
            self.stderr.write(f"data id: {','.join(diff)} not found")
            raise CommandError(f"{','.join(diff)} not found")

    def _validate_space_type(self, space_type_id: str) -> None:
        space_type_list = [item[0] for item in SpaceTypes._choices_labels.value]
        if space_type_id not in space_type_list:
            raise CommandError("space type not found")

    def _update(self, space_type_id: str, data_id_list: Optional[List] = None):
        """更改类型"""
        ds_qs = models.DataSource.objects.all()
        if data_id_list:
            ds_qs = ds_qs.filter(bk_data_id__in=data_id_list)
        ds_qs.update(space_type_id=space_type_id)

        self.stdout.write(f"set space type to {space_type_id} successfully")
