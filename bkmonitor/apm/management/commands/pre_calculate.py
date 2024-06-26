# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from django.core.management import BaseCommand

from apm.core.discover.precalculation.daemon import DaemonTaskHandler


class Command(BaseCommand):
    help = "operate apm pre_calculate"

    def add_arguments(self, parser):
        parser.add_argument('params', metavar='N', type=str, nargs='+')

    def handle(self, *args, **options):
        """
        选择应用进行新版预计算灰度
        用法:
        manage.py pre_calculate add 2 (queue1) 触发应用ID为2的应用(发送到queue1队列)进行新版预计算 旧版预计算将会忽略此应用
        """
        params = options.get("params")

        op = params[0]

        if op == "add":
            app_id = int(params[1])
            if len(params) >= 3:
                queue = params[2]
            else:
                queue = None
            DaemonTaskHandler.execute(app_id, queue)
        else:
            raise ValueError(f"不支持的操作: {op}")
