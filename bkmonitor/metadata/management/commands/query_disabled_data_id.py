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

from django.core.management.base import BaseCommand

from metadata import models


class Command(BaseCommand):
    help = "查询已经禁用的数据源ID"
    regex = r"_delete_[0-9]{14}$"

    def handle(self, *args, **options):
        """这里要包含两个场景
        1. is_enable 为 False
        2. data_name 以 _delete_16位数字结尾
        """
        # 1. 过滤出 is_enable 为 False 的数据源
        _data_ids = set(models.DataSource.objects.filter(is_enable=False).values_list("bk_data_id", flat=True))
        # 2. 按照规则，过滤符合条件的名称
        data_ids = _data_ids.union(
            set(models.DataSource.objects.filter(data_name__regex=self.regex).values_list("bk_data_id", flat=True))
        )
        self.stdout.write(json.dumps({"count": len(data_ids), "result": list(data_ids)}))
