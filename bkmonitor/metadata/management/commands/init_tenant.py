"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand, CommandParser

from metadata.task.tenant import init_tenant


class Command(BaseCommand):
    help = "init tenant"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--bk_tenant_id", type=str, required=True, help="租户ID")
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        init_tenant(bk_tenant_id)
