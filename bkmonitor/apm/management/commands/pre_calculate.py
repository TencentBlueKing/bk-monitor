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
from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from django.core.management import BaseCommand


class Command(BaseCommand):

    help = "operate apm pre_calculate"

    def add_arguments(self, parser):
        parser.add_argument('params', metavar='N', type=str, nargs='+')

    def handle(self, *args, **options):
        """
        选择应用进行新版预计算灰度
        用法:
        manage.py set_ebpf_config add 2 触发应用ID为2的应用进行新版预计算 旧版预计算将会忽略此应用
        TODO 支持指定队列
        """
        params = options.get("params")

        op = params[0]

        if op == "add":
            app_id = int(params[1])
            DaemonTaskHandler.execute(app_id)
        else:
            raise ValueError(f"不支持的操作: {op}")
