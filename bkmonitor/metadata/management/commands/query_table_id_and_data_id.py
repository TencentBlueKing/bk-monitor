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
    def handle(self, *args, **options):
        bk_biz_id = options.get("bk_biz_id")
        if not bk_biz_id:
            raise Exception("参数[bk_biz_id]不能为空")
        table_id_and_data_id = models.ResultTable.get_table_id_and_data_id(bk_biz_id)
        self.stdout.write(json.dumps(table_id_and_data_id))

    def add_arguments(self, parser):
        parser.add_argument("--bk_biz_id", type=int, help="业务ID")
