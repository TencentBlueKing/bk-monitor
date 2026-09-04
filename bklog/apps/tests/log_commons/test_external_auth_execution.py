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

from django.test import SimpleTestCase

from apps.log_commons.external_auth import (
    DecisionSource,
    ExternalAuthDecision,
    IdentityContext,
    resolve_execution_user,
)

EXTERNAL_USER = "po_external_user"
AUTHORIZER = "authorizer_zhang"


def _identity() -> IdentityContext:
    return IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer="", bk_tenant_id="system")


class ResolveExecutionUserTest(SimpleTestCase):
    def test_legacy_only_uses_the_space_authorizer(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset({DecisionSource.LEGACY}))

        self.assertEqual(resolve_execution_user(decision, _identity(), AUTHORIZER), AUTHORIZER)

    def test_iam_source_uses_the_external_user(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset({DecisionSource.IAM}))

        self.assertEqual(resolve_execution_user(decision, _identity(), AUTHORIZER), EXTERNAL_USER)

    def test_strategy_source_uses_the_external_user(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset({DecisionSource.STRATEGY}))

        self.assertEqual(resolve_execution_user(decision, _identity(), AUTHORIZER), EXTERNAL_USER)

    def test_both_legacy_and_iam_uses_the_external_user(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset({DecisionSource.LEGACY, DecisionSource.IAM}))

        self.assertEqual(resolve_execution_user(decision, _identity(), AUTHORIZER), EXTERNAL_USER)

    def test_default_allow_with_empty_sources_uses_the_authorizer(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset())

        self.assertEqual(resolve_execution_user(decision, _identity(), AUTHORIZER), AUTHORIZER)

    def test_missing_authorizer_stays_empty_for_legacy(self):
        decision = ExternalAuthDecision(allowed=True, sources=frozenset({DecisionSource.LEGACY}))

        self.assertEqual(resolve_execution_user(decision, _identity(), ""), "")


class IdentityContextExecutionUserTest(SimpleTestCase):
    def test_with_execution_user_returns_a_new_frozen_context(self):
        identity = _identity()

        updated = identity.with_execution_user(AUTHORIZER)

        self.assertEqual(identity.execution_user, "")
        self.assertEqual(updated.execution_user, AUTHORIZER)
        self.assertEqual(updated.authorization_subject, EXTERNAL_USER)
        self.assertEqual(updated.audit_user, EXTERNAL_USER)
