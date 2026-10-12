"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.iam.backends.v4.exceptions import V4ClientError
from apps.iam.backends.v4.model_definition import CURRENT_MODEL_FILE, ModelDefinitionError
from apps.iam.backends.v4.model_migrator import ModelMigrationBlocked, V4ModelMigrator


class Command(BaseCommand):
    help = "把 support-files/iam/v4/ 下的 IAM V4 权限模型基线收敛到权限中心，默认只打印计划"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="真正写入权限中心；不加该参数时只做 dry-run",
        )
        parser.add_argument(
            "--file",
            dest="file_name",
            default=CURRENT_MODEL_FILE,
            help=f"要收敛的基线文件名，默认 {CURRENT_MODEL_FILE}",
        )
        parser.add_argument(
            "--tenant",
            dest="bk_tenant_id",
            default="",
            help="调用权限中心使用的租户 ID，默认取 settings.BK_APP_TENANT_ID",
        )

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"] or settings.BK_APP_TENANT_ID
        apply_changes = options["apply"]

        try:
            migrator = V4ModelMigrator.from_settings(
                bk_tenant_id=bk_tenant_id,
                file_name=options["file_name"],
            )
        except ModelDefinitionError as error:
            raise CommandError(f"IAM V4 model baseline is invalid: {error}") from error

        try:
            plan = migrator.plan()
        except V4ClientError as error:
            raise CommandError(f"failed to read the current IAM V4 model: {error}") from error

        self.stdout.write(f"system: {migrator.desired.system.id} (tenant={bk_tenant_id})")
        self.stdout.write(plan.describe())

        for reason in plan.drift:
            # 漂移只报不删：删除受存量授权约束且不可逆，必须人工确认。
            self.stdout.write(self.style.WARNING(f"drift: {reason}"))

        if not apply_changes:
            self.stdout.write(self.style.NOTICE("dry-run: nothing was written; rerun with --apply to converge"))
            return

        if plan.blocking:
            raise CommandError(
                "plan contains changes that cannot be applied automatically:\n" + "\n".join(plan.blocking)
            )

        if not plan.has_changes():
            self.stdout.write(self.style.SUCCESS("IAM V4 model is already up to date"))
            return

        try:
            migrator.apply(plan)
        except (V4ClientError, ModelMigrationBlocked) as error:
            raise CommandError(f"failed to apply the IAM V4 model plan: {error}") from error

        self.stdout.write(self.style.SUCCESS("IAM V4 model converged"))
