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
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string


class Command(BaseCommand):

    MODULE_PREFIX = "alarm_backends.core.cache."

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.supported_modules = [
            module[0][len(self.MODULE_PREFIX) :]
            for module in settings.DEFAULT_CRONTAB
            if module[0].startswith(self.MODULE_PREFIX)
        ]

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            "args",
            metavar="modules",
            nargs="+",
            choices=["all"] + self.supported_modules,
            help="cache module(s) to refresh, use `all` if want to refresh all cache",
        )

    def handle(self, *modules, **options):
        if "all" in modules:
            # 如果设置的模块中包含 all，则直接全量刷新缓存
            modules = self.supported_modules

        print("[Cache Refresh] {} cache modules will be refreshed: {}".format(len(modules), ",".join(modules)))

        success = 0
        failed = 0

        for module in modules:
            print("[Module: {}] cache refresh START...".format(module))

            module_path = "{}{}".format(self.MODULE_PREFIX, module)

            try:
                try:
                    process_func = import_string(module_path)
                    process_func = getattr(process_func, "main", process_func)
                except ImportError:
                    process_func = import_string("%s.main" % module_path)
                process_func()
                print("[Module: {}] cache refresh SUCCESS".format(module))
                success += 1
            except Exception as e:
                print("[Module: {}] cache refresh FAILED!!! Reason: {}".format(module, e))
                failed += 1

        print("[Cache Refresh] done! success: {}, failed: {}".format(success, failed))
