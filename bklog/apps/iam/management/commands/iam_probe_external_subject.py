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

import inspect
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.actions import ActionMeta, get_action_by_id
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.types import AuthDecision

# 外部用户可能落到的能力对应的 IAM 动作。别名只是为了让探测命令好敲，
# 真正的动作定义仍以 ActionEnum 为准，也允许直接传 action_id。
ACTION_ALIASES = {
    "search_log": ActionEnum.SEARCH_LOG,
    "view_business": ActionEnum.VIEW_BUSINESS,
    "manage_extract_config": ActionEnum.MANAGE_EXTRACT_CONFIG,
}


class Command(BaseCommand):
    help = (
        "只读探测指定用户名能否作为 IAM 鉴权主体，用于 PO 外部用户接入权限中心的可行性验证。"
        "只发起鉴权查询，不创建、不授权、不修改任何权限数据。"
        "--check-django-user 只读查询 User 表并报告 authenticate 后端行为，不调用 auth.authenticate，不写库。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="要探测的鉴权主体用户名，例如 PO 外部用户名",
        )
        parser.add_argument(
            "--tenant",
            dest="bk_tenant_id",
            default="",
            help="鉴权使用的租户 ID，默认取 settings.BK_APP_TENANT_ID",
        )
        parser.add_argument(
            "--action",
            dest="actions",
            action="append",
            default=[],
            required=False,
            help=f"要探测的动作，可重复。可用别名：{'/'.join(ACTION_ALIASES)}，也可直接传 action_id",
        )
        parser.add_argument(
            "--check-django-user",
            dest="check_django_user",
            action="store_true",
            default=False,
            help="只读探测该用户名是否已存在于 Django User 表，以及 authenticate(username=) 会命中哪个后端。不调用 authenticate，不写库。",
        )
        parser.add_argument(
            "--index-set-id",
            dest="index_set_ids",
            action="append",
            default=[],
            help="索引集 ID，可重复；用于依赖 indices 资源的动作",
        )
        parser.add_argument(
            "--bk-biz-id",
            dest="bk_biz_ids",
            action="append",
            default=[],
            help="业务 ID 或空间 UID，可重复；用于依赖 business 资源的动作",
        )
        parser.add_argument(
            "--timeout",
            dest="timeout_seconds",
            default=None,
            help="临时覆盖 BK_IAM_V4_TIMEOUT，用于复现 IAM 超时后的兜底行为",
        )
        parser.add_argument(
            "--json",
            dest="as_json",
            action="store_true",
            default=False,
            help="额外输出一行 JSON，便于贴进自测报告",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("--username must not be empty")

        bk_tenant_id = options["bk_tenant_id"] or settings.BK_APP_TENANT_ID
        if not options["actions"] and not options["check_django_user"]:
            raise CommandError("provide --action and/or --check-django-user")

        django_user = self._inspect_django_user(username) if options["check_django_user"] else None
        if django_user is not None:
            self._write_django_user(django_user)

        rows = []
        if options["actions"]:
            actions = [self._resolve_action(value) for value in options["actions"]]

            if options["timeout_seconds"] is not None:
                # V4Options.from_settings() 在 Provider 构造时才读取，这里改 settings 即可生效。
                settings.BK_IAM_V4_TIMEOUT = options["timeout_seconds"]

            self._write_preamble(username, bk_tenant_id)

            permission = Permission(username=username, bk_tenant_id=bk_tenant_id)
            if permission.username != username:
                # Permission 只在 username 与 bk_tenant_id 同时给出时才认显式身份，
                # 一旦回落到线程内的登录用户，探测出来的就不是目标主体的权限。
                raise CommandError(
                    f"resolved subject is {permission.username!r}, expected {username!r}; "
                    "the explicit identity was not honoured"
                )

            for action in actions:
                for resources, resource_label in self._iter_resources(action, options):
                    decision = permission.mode_router.is_allowed(permission.make_engine_request(action, resources))
                    rows.append(self._render(action, resource_label, decision))

            self._write_table(rows)
        if options["as_json"]:
            payload = {"subject": {"type": "user", "id": username}, "bk_tenant_id": bk_tenant_id, "probes": rows}
            if django_user is not None:
                payload["django_user"] = django_user
            self.stdout.write(json.dumps(payload, ensure_ascii=False))

    def _resolve_action(self, value: str) -> ActionMeta:
        if value in ACTION_ALIASES:
            return ACTION_ALIASES[value]
        try:
            return get_action_by_id(value)
        except Exception as error:  # pylint: disable=broad-except
            raise CommandError(
                f"unknown action {value!r}; use one of {'/'.join(ACTION_ALIASES)} or a valid action_id"
            ) from error

    def _iter_resources(self, action: ActionMeta, options):
        """按动作声明的资源类型展开待探测的资源实例，每个实例单独判定一次。"""

        if not action.related_resource_types:
            yield [], "-"
            return

        resource_type = action.related_resource_types[0]
        if resource_type is ResourceEnum.INDICES:
            instance_ids, flag = options["index_set_ids"], "--index-set-id"
        elif resource_type is ResourceEnum.BUSINESS:
            instance_ids, flag = options["bk_biz_ids"], "--bk-biz-id"
        else:
            raise CommandError(f"action {action.id} depends on unsupported resource type {resource_type.id}")

        if not instance_ids:
            raise CommandError(f"action {action.id} depends on {resource_type.id}, please provide {flag}")

        for instance_id in instance_ids:
            yield (
                [resource_type.create_simple_instance(str(instance_id))],
                f"{resource_type.id}:{instance_id}",
            )

    def _inspect_django_user(self, username: str) -> dict:
        """只读查看 User 表和 authenticate 后端，绝不调用 authenticate。"""
        user_model = get_user_model()
        existing = user_model.objects.filter(**{user_model.USERNAME_FIELD: username}).first()
        backend_path, creates_user = self._first_username_backend()
        return {
            "username": username,
            "exists": existing is not None,
            "is_superuser": bool(existing.is_superuser) if existing is not None else None,
            "is_staff": bool(existing.is_staff) if existing is not None else None,
            "authenticate_backend": backend_path,
            "authenticate_creates_user": creates_user,
            "authenticate_called": False,
        }

    @staticmethod
    def _first_username_backend() -> tuple[str, bool]:
        """找到第一个签名接受 username 的认证后端，并看它会不会 get_or_create。"""
        for path in settings.AUTHENTICATION_BACKENDS:
            backend = import_string(path)()
            if "username" not in inspect.signature(backend.authenticate).parameters:
                continue
            return path, "get_or_create" in inspect.getsource(backend.authenticate)
        return "", False

    def _write_django_user(self, django_user: dict):
        exists_label = "exists" if django_user["exists"] else "missing"
        self.stdout.write(
            f"django_user  : {django_user['username']} {exists_label} "
            f"superuser={django_user['is_superuser']} staff={django_user['is_staff']}"
        )
        self.stdout.write(
            f"auth_backend : {django_user['authenticate_backend'] or '-'} "
            f"creates_user={django_user['authenticate_creates_user']}"
        )
        self.stdout.write("authenticate : not called (read-only probe)")
        if django_user["exists"]:
            self.stdout.write(
                self.style.WARNING(
                    "username already exists: auth.authenticate(username=) would reuse this User record, "
                    "including is_superuser / is_staff"
                )
            )
        if django_user["authenticate_creates_user"]:
            self.stdout.write(
                self.style.WARNING(
                    "first username backend uses get_or_create: a missing Taihu username would be created on login"
                )
            )

    def _write_preamble(self, username: str, bk_tenant_id: str):
        self.stdout.write(f"subject      : {json.dumps({'type': 'user', 'id': username}, ensure_ascii=False)}")
        self.stdout.write(f"bk_tenant_id : {bk_tenant_id}")
        self.stdout.write(f"multi_tenant : {getattr(settings, 'ENABLE_MULTI_TENANT_MODE', False)}")
        # 这两个开关会让业务代码在到达 IAM 之前就放行，探测结果与线上表现会不一致，必须提示。
        for name in ("IGNORE_IAM_PERMISSION", "SKIP_IAM_PERMISSION_CHECK"):
            if getattr(settings, name, False):
                self.stdout.write(self.style.WARNING(f"{name} is on: business code bypasses IAM before this check"))

    @staticmethod
    def _render(action: ActionMeta, resource_label: str, decision: AuthDecision) -> dict:
        return {
            "action_id": action.id,
            "resource": resource_label,
            "mode": decision.mode,
            "allowed": decision.allowed,
            "degraded": decision.degraded,
            "providers": [
                {
                    "name": result.provider_name,
                    "status": result.status.value,
                    "error_type": result.error_type,
                    "reason": result.reason,
                }
                for result in decision.provider_results
            ],
        }

    def _write_table(self, rows: list[dict]):
        for row in rows:
            verdict = "ALLOW" if row["allowed"] else "DENY"
            style = self.style.SUCCESS if row["allowed"] else self.style.NOTICE
            line = f"{row['action_id']:<26} {row['resource']:<22} mode={row['mode']:<6} {verdict}"
            if row["degraded"]:
                line = f"{line} (degraded)"
            self.stdout.write(style(line))
            for provider in row["providers"]:
                detail = f"    {provider['name']}: {provider['status']}"
                if provider["error_type"]:
                    detail = f"{detail} [{provider['error_type']}]"
                if provider["reason"]:
                    detail = f"{detail} {provider['reason']}"
                self.stdout.write(detail)
