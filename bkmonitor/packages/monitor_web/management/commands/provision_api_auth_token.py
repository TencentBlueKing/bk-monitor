"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bkmonitor.models.token import AuthType
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from monitor_web.commons.token.service import get_or_create_business_token

SUPPORTED_TOKEN_TYPES = (AuthType.Grafana,)


class Command(BaseCommand):
    help = "获取或创建业务 API Token，仅允许在 api role 执行"

    def add_arguments(self, parser):
        parser.add_argument("--bk-biz-id", type=int, required=True, help="业务 ID")
        parser.add_argument(
            "--type",
            choices=SUPPORTED_TOKEN_TYPES,
            default=AuthType.Grafana,
            help=f"Token 类型，默认 {AuthType.Grafana}",
        )
        parser.add_argument("--operator", default="system", help="操作人，默认 system")
        parser.add_argument(
            "--output",
            choices=("token", "json"),
            default="token",
            help="输出格式，默认 token",
        )

    def handle(self, *args, **options):
        if settings.ROLE != "api":
            raise CommandError("该命令只能在 api role 执行")

        token_type = options["type"]
        if token_type not in SUPPORTED_TOKEN_TYPES:
            raise CommandError(f"不支持的 Token 类型: {token_type}")

        bk_biz_id = options["bk_biz_id"]
        if not bk_biz_id:
            raise CommandError("业务 ID 不能为 0")
        try:
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        except ValueError as error:
            raise CommandError(f"无法确定业务 {bk_biz_id} 所属租户") from error

        auth_token, created = get_or_create_business_token(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            token_type=token_type,
            operator=options["operator"],
        )

        if options["output"] == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "bk_biz_id": bk_biz_id,
                        "bk_tenant_id": bk_tenant_id,
                        "created": created,
                        "token": auth_token.token,
                        "type": token_type,
                    },
                    ensure_ascii=False,
                )
            )
            return

        self.stdout.write(auth_token.token)
