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


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            "args", metavar="status", nargs=1, choices=["on", "off"], help="enable(on) or disable(off) global shield"
        )

    def handle(self, status, *args, **options):
        if status == "on":
            settings.GLOBAL_SHIELD_ENABLED = True
            print("GLOBAL_SHIELD_ENABLED is set to [ON], will be effective in 1 min")
        elif status == "off":
            settings.GLOBAL_SHIELD_ENABLED = False
            print("GLOBAL_SHIELD_ENABLEDd is set to [OFF], will be effective in 1 min")
        else:
            print("Invalid operate: {}".format(status))
