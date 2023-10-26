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

from apm.core.handlers.ebpf.base import EbpfHandler


class Command(BaseCommand):

    help = "operate apm ebpf config"

    def add_arguments(self, parser):
        parser.add_argument('params', metavar='N', type=str, nargs='+')

    def handle(self, *args, **options):
        """
        操作业务下EBPF应用
        用法:
        manage.py set_ebpf_config add 2 创建业务id为2的EBPF应用
        manage.py set_ebpf_config use 2 <app_name> 将业务2下的application_id为27的应用作为此业务的EBPF应用
        manage.py set_ebpf_config delete 2 <is_delete_application[0|1]> 将业务id为2的EBPF应用删除
        """
        params = options.get("params")

        op = params[0]

        if op == "add":
            bk_biz_id = int(params[1])
            EbpfHandler.create_ebpf_application(bk_biz_id)
        elif op == "use":
            bk_biz_id = int(params[1])
            app_name = params[2]
            EbpfHandler.use_exists_as_ebpf(bk_biz_id, app_name)
        elif op == "delete":
            bk_biz_id = int(params[1])
            is_delete_application = int(params[2])
            EbpfHandler.delete_ebpf_related(bk_biz_id, bool(is_delete_application))
        else:
            raise ValueError(f"不支持的操作: {op}")
