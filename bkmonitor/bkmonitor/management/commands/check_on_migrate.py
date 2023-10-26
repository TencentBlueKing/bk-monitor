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
from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--update", default=False, action="store_true", help="update migrate version", dest="update"
        )

    def handle(self, **kwargs):
        # 检查是否需要更新迁移版本
        if kwargs.get("update"):
            settings.LAST_MIGRATE_VERSION = settings.MIGRATE_VERSION
            return

        # 检查是否执行迁移
        if settings.LAST_MIGRATE_VERSION == settings.MIGRATE_VERSION:
            exit(1)
