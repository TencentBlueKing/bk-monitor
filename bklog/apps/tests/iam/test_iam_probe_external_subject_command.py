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

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.core.types import AuthDecision, AuthResult
from apps.utils.local import _local, activate_request

EXTERNAL_USER = "po_external_user"


def allow_decision(mode: str = "v4") -> AuthDecision:
    return AuthDecision(
        allowed=True,
        provider_results=(AuthResult.allow(provider_name=mode),),
        hit_provider_names=(mode,),
        mode=mode,
    )


def deny_decision(mode: str = "v4") -> AuthDecision:
    return AuthDecision(
        allowed=False,
        provider_results=(AuthResult.deny(provider_name=mode),),
        mode=mode,
    )


def timeout_decision(mode: str = "v4") -> AuthDecision:
    """单栈下 IAM 超时：provider ERROR，最终 allowed=False 且 degraded=True。"""
    return AuthDecision(
        allowed=False,
        provider_results=(AuthResult.error(provider_name=mode, reason="IAM V4 request timeout", error_type="Timeout"),),
        degraded=True,
        mode=mode,
    )


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_APP_TENANT_ID="system",
    BK_IAM_SYSTEM_ID="bk_log_search",
    IGNORE_IAM_PERMISSION=False,
    SKIP_IAM_PERMISSION_CHECK=False,
)
class IamProbeExternalSubjectCommandTest(TestCase):
    def setUp(self):
        self.router = Mock()
        self.router.is_allowed.return_value = allow_decision()
        patcher = patch.object(Permission, "mode_router", new_callable=PropertyMock, return_value=self.router)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def run_command(*args):
        stdout = StringIO()
        call_command("iam_probe_external_subject", *args, stdout=stdout, stderr=StringIO())
        return stdout.getvalue()

    def engine_subjects(self):
        return [call.args[0].subject for call in self.router.is_allowed.call_args_list]

    def test_probe_reports_allow_and_deny_per_index_set(self):
        self.router.is_allowed.side_effect = [allow_decision(), deny_decision()]

        output = self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
            "--index-set-id",
            "2002",
        )

        self.assertIn("indices:1001", output)
        self.assertIn("indices:2002", output)
        self.assertIn("ALLOW", output)
        self.assertIn("DENY", output)
        self.assertEqual(self.router.is_allowed.call_count, 2)

    def test_probe_sends_external_username_as_subject_with_explicit_tenant(self):
        self.run_command(
            "--username",
            EXTERNAL_USER,
            "--tenant",
            "tenant_a",
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
        )

        subject = self.engine_subjects()[0]
        self.assertEqual(subject.id, EXTERNAL_USER)
        self.assertEqual(subject.type, "user")
        self.assertEqual(subject.tenant_id, "tenant_a")

    def test_probe_keeps_external_subject_when_another_user_is_logged_in(self):
        """Permission 只在 username 与 tenant 同时给出时才认显式身份，这里锁住这个前提。"""
        activate_request(SimpleNamespace(user=SimpleNamespace(username="internal_authorizer"), META={}))
        self.addCleanup(lambda: _local.__dict__.pop("request", None))

        self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
        )

        self.assertEqual(self.engine_subjects()[0].id, EXTERNAL_USER)

    def test_probe_marks_degraded_when_provider_errors(self):
        self.router.is_allowed.return_value = timeout_decision()

        output = self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
        )

        self.assertIn("DENY", output)
        self.assertIn("(degraded)", output)
        self.assertIn("Timeout", output)

    def test_probe_emits_json_summary(self):
        output = self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "manage_extract_config",
            "--bk-biz-id",
            "100605",
            "--json",
        )

        summary = json.loads(output.strip().splitlines()[-1])
        self.assertEqual(summary["subject"], {"type": "user", "id": EXTERNAL_USER})
        self.assertEqual(summary["bk_tenant_id"], "system")
        self.assertEqual(summary["probes"][0]["action_id"], "manage_extract_config_v2")
        self.assertEqual(summary["probes"][0]["resource"], "space:100605")

    def test_probe_supports_actions_without_resource_dependency(self):
        output = self.run_command("--username", EXTERNAL_USER, "--action", "manage_global_desensitize_rule")

        self.assertIn("manage_global_desensitize_rule", output)
        self.assertEqual(self.router.is_allowed.call_count, 1)
        self.assertEqual(self.router.is_allowed.call_args.args[0].resources, ())

    @override_settings(BK_IAM_V4_TIMEOUT=10.0)
    def test_probe_can_override_the_iam_timeout_to_reproduce_degradation(self):
        self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
            "--timeout",
            "0.01",
        )

        self.assertEqual(settings.BK_IAM_V4_TIMEOUT, "0.01")

    def test_probe_rejects_blank_username(self):
        with self.assertRaises(CommandError):
            self.run_command("--username", "   ", "--action", "search_log")

        self.router.is_allowed.assert_not_called()

    def test_probe_fails_loudly_when_the_explicit_identity_is_not_honoured(self):
        """判权主体被换掉时必须报错，否则探测出来的是另一个人的权限。"""
        with patch(
            "apps.iam.management.commands.iam_probe_external_subject.Permission",
            return_value=Mock(username="internal_authorizer"),
        ):
            with self.assertRaises(CommandError) as ctx:
                self.run_command("--username", EXTERNAL_USER, "--action", "search_log", "--index-set-id", "1001")

        self.assertIn("internal_authorizer", str(ctx.exception))

    def test_probe_rejects_actions_with_unsupported_resource_type(self):
        with self.assertRaises(CommandError) as ctx:
            self.run_command("--username", EXTERNAL_USER, "--action", "view_collection_v2")

        self.assertIn("unsupported resource type", str(ctx.exception))

    def test_probe_rejects_unknown_action(self):
        with self.assertRaises(CommandError):
            self.run_command("--username", EXTERNAL_USER, "--action", "not_an_action")

        self.router.is_allowed.assert_not_called()

    def test_probe_requires_resource_flag_for_resource_scoped_action(self):
        with self.assertRaises(CommandError) as ctx:
            self.run_command("--username", EXTERNAL_USER, "--action", "search_log")

        self.assertIn("--index-set-id", str(ctx.exception))
        self.router.is_allowed.assert_not_called()

    @override_settings(IGNORE_IAM_PERMISSION=True)
    def test_probe_warns_when_business_code_bypasses_iam(self):
        output = self.run_command(
            "--username",
            EXTERNAL_USER,
            "--action",
            "search_log",
            "--index-set-id",
            "1001",
        )

        self.assertIn("IGNORE_IAM_PERMISSION is on", output)
