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

from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.external_auth import (
    AuthSource,
    Capability,
    DecisionSource,
    ExternalRequestContext,
    HardConstraint,
    IdentityContext,
    SourceResult,
    authorize,
    combine_or,
    get_capability,
    resolve_declared_action_id,
    resolve_resource,
)
from apps.log_commons.external_auth.capability import CAPABILITY_REGISTRY, FALLBACK_CAPABILITY
from apps.log_commons.external_auth.sources import LEGACY_TICKET_SOURCE
from apps.log_commons.models import ExternalPermission

SPACE_UID = "bkcc__100605"
EXTERNAL_USER = "po_external_user"
AUTHORIZER = "authorizer_zhang"
ALLOWED_INDEX_SET_ID = 628108
DENIED_INDEX_SET_ID = 999999


def build_context(
    view_set="SearchViewSet",
    view_action="search",
    declared_action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
    url_kwargs=None,
    json_data_str="",
) -> ExternalRequestContext:
    return ExternalRequestContext(
        identity=IdentityContext.for_external_request(
            external_user=EXTERNAL_USER, authorizer=AUTHORIZER, bk_tenant_id="system"
        ),
        space_uid=SPACE_UID,
        view_set=view_set,
        view_action=view_action,
        declared_action_id=declared_action_id,
        url_kwargs=url_kwargs or {},
        json_data_str=json_data_str,
    )


class StubSource:
    """外部实现的放行来源，用来验证注册新来源不需要改动 pipeline。"""

    def __init__(self, name: DecisionSource, result: SourceResult):
        self.name = name
        self.result = result
        self.calls = 0

    def check(self, ctx: ExternalRequestContext) -> SourceResult:
        self.calls += 1
        return self.result


class DenyAllConstraint:
    def check(self, ctx: ExternalRequestContext) -> str:
        return "blocked by hard constraint"


class ExternalAuthContractTest(SimpleTestCase):
    def test_stub_source_satisfies_the_auth_source_protocol(self):
        source = StubSource(DecisionSource.IAM, SourceResult.allow())

        self.assertIsInstance(source, AuthSource)
        self.assertIsInstance(DenyAllConstraint(), HardConstraint)
        self.assertIsInstance(LEGACY_TICKET_SOURCE, AuthSource)

    def test_registry_only_registers_legacy_for_now(self):
        """本单不改变放行行为，每个能力只认旧票；新增来源时这条断言应当被显式更新。"""
        for capability in [*CAPABILITY_REGISTRY.values(), FALLBACK_CAPABILITY]:
            self.assertEqual(capability.sources, (LEGACY_TICKET_SOURCE,))

    def test_unknown_action_id_falls_back_to_legacy_only(self):
        self.assertIs(get_capability("brand_new_action"), FALLBACK_CAPABILITY)


class CombineOrTest(SimpleTestCase):
    def test_any_allowing_source_allows_the_request(self):
        denying = StubSource(DecisionSource.LEGACY, SourceResult.deny("no ticket"))
        allowing = StubSource(DecisionSource.IAM, SourceResult.allow(matched_action_id="log_search"))

        decision = combine_or((denying, allowing), build_context())

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sources, frozenset({DecisionSource.IAM}))
        self.assertEqual(decision.matched_action_id, "log_search")
        self.assertEqual(decision.reject_reason, "")

    def test_all_sources_are_consulted_and_reasons_are_joined(self):
        first = StubSource(DecisionSource.LEGACY, SourceResult.deny("no ticket"))
        second = StubSource(DecisionSource.IAM, SourceResult.deny("iam denied"))

        decision = combine_or((first, second), build_context())

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.sources, frozenset())
        self.assertEqual(decision.reject_reason, "no ticket | iam denied")
        self.assertEqual((first.calls, second.calls), (1, 1))

    def test_single_source_keeps_its_reject_reason_verbatim(self):
        only = StubSource(DecisionSource.LEGACY, SourceResult.deny("external_user:x has no permission."))

        decision = combine_or((only,), build_context())

        self.assertEqual(decision.reject_reason, "external_user:x has no permission.")

    def test_errored_source_marks_degraded_without_allowing(self):
        broken = StubSource(DecisionSource.IAM, SourceResult.error("iam timeout"))
        denying = StubSource(DecisionSource.LEGACY, SourceResult.deny("no ticket"))

        decision = combine_or((denying, broken), build_context())

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.degraded)

    def test_errored_source_does_not_veto_another_allowing_source(self):
        broken = StubSource(DecisionSource.IAM, SourceResult.error("iam timeout"))
        allowing = StubSource(DecisionSource.LEGACY, SourceResult.allow(matched_action_id="log_search"))

        decision = combine_or((allowing, broken), build_context())

        self.assertTrue(decision.allowed)
        self.assertTrue(decision.degraded)
        self.assertEqual(decision.sources, frozenset({DecisionSource.LEGACY}))

    def test_denied_result_still_carries_action_and_resource_for_audit(self):
        denying = StubSource(
            DecisionSource.LEGACY,
            SourceResult.deny("resource denied", matched_action_id="log_search", resource_id=DENIED_INDEX_SET_ID),
        )

        decision = combine_or((denying,), build_context())

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.matched_action_id, "log_search")
        self.assertEqual(decision.resource_id, DENIED_INDEX_SET_ID)

    def test_capability_without_source_denies_instead_of_allowing(self):
        decision = combine_or((), build_context())

        self.assertFalse(decision.allowed)
        self.assertIn("no auth source", decision.reject_reason)


class AuthorizePipelineTest(SimpleTestCase):
    def test_default_allowed_view_bypasses_every_source(self):
        source = StubSource(DecisionSource.LEGACY, SourceResult.deny("no ticket"))
        ctx = build_context(view_set="MetaViewSet", view_action="menu")

        decision = authorize(ctx, capability=Capability(action_id="", sources=(source,)))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sources, frozenset())
        self.assertEqual(decision.matched_action_id, "")
        self.assertFalse(decision.allow_resources_result["allowed"])
        self.assertEqual(source.calls, 0)

    def test_hard_constraint_denies_before_any_source_runs(self):
        source = StubSource(DecisionSource.LEGACY, SourceResult.allow(matched_action_id="log_search"))

        decision = authorize(
            build_context(),
            capability=Capability(action_id="", sources=(source,)),
            hard_constraints=(DenyAllConstraint(),),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "blocked by hard constraint")
        self.assertEqual(source.calls, 0)

    def test_hard_constraint_is_not_overridable_by_an_allowing_source(self):
        """硬约束不参与 OR，这是它与 AuthSource 的唯一区别，必须锁死。"""
        allowing = StubSource(DecisionSource.IAM, SourceResult.allow())

        decision = authorize(
            build_context(),
            capability=Capability(action_id="", sources=(allowing,)),
            hard_constraints=(DenyAllConstraint(),),
        )

        self.assertFalse(decision.allowed)


class LegacyTicketSourceTest(TestCase):
    """旧票来源的判定与拒绝文案必须与接入管道之前逐字一致。"""

    def _create_ticket(self, action_id, resources):
        ExternalPermission.objects.create(
            authorized_user=EXTERNAL_USER,
            space_uid=SPACE_UID,
            action_id=action_id,
            resources=resources,
            expire_time=timezone.now() + timedelta(days=30),
        )

    def test_denies_with_original_message_when_no_ticket_exists(self):
        decision = authorize(build_context(url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID}))

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reject_reason,
            f"dispatch_plugin_query: external_user:{EXTERNAL_USER} has no permission.",
        )

    def test_denies_with_original_message_when_ticket_does_not_cover_the_view(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_EXTRACT.value, [])

        decision = authorize(build_context(url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID}))

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, f"external_user:{EXTERNAL_USER} has not enough permission.")

    def test_allows_and_reports_legacy_source_when_ticket_covers_the_index_set(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_SEARCH.value, [ALLOWED_INDEX_SET_ID])

        decision = authorize(build_context(url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID}))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.sources, frozenset({DecisionSource.LEGACY}))
        self.assertEqual(decision.matched_action_id, ExternalPermissionActionEnum.LOG_SEARCH.value)
        self.assertEqual(decision.resource_id, ALLOWED_INDEX_SET_ID)
        self.assertEqual(decision.allow_resources_result["resources"], [ALLOWED_INDEX_SET_ID])

    def test_denies_with_original_message_when_index_set_is_outside_the_ticket(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_SEARCH.value, [ALLOWED_INDEX_SET_ID])

        decision = authorize(build_context(url_kwargs={"index_set_id": DENIED_INDEX_SET_ID}))

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reject_reason,
            f"external_user:{EXTERNAL_USER} cannot access resource(ID:{DENIED_INDEX_SET_ID}).",
        )
        self.assertEqual(decision.matched_action_id, ExternalPermissionActionEnum.LOG_SEARCH.value)
        self.assertEqual(decision.resource_id, DENIED_INDEX_SET_ID)

    def test_client_log_ticket_implies_log_search_on_its_own_index_sets(self):
        self._create_ticket(ExternalPermissionActionEnum.CLIENT_LOG.value, [ALLOWED_INDEX_SET_ID])

        decision = authorize(build_context(url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID}))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.matched_action_id, ExternalPermissionActionEnum.LOG_SEARCH.value)

    def test_clustering_ticket_does_not_imply_log_search(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_CLUSTERING.value, [ALLOWED_INDEX_SET_ID])

        decision = authorize(build_context(url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID}))

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reject_reason,
            f"external_user:{EXTERNAL_USER} has not enough permission.",
        )

    def test_clustering_settings_require_both_tickets_on_the_same_index_set(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_CLUSTERING.value, [ALLOWED_INDEX_SET_ID])
        ctx = build_context(
            view_set="ClusteringConfigViewSet",
            view_action="update_access",
            declared_action_id=ExternalPermissionActionEnum.LOG_CLUSTERING.value,
            url_kwargs={"index_set_id": ALLOWED_INDEX_SET_ID},
        )

        denied = authorize(ctx)
        self.assertFalse(denied.allowed)
        self.assertIn("cannot access clustering settings", denied.reject_reason)

        self._create_ticket(ExternalPermissionActionEnum.LOG_SEARCH.value, [ALLOWED_INDEX_SET_ID])
        allowed = authorize(ctx)
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.matched_action_id, ExternalPermissionActionEnum.LOG_CLUSTERING.value)

    def test_capability_without_resource_scope_allows_without_resource_check(self):
        """log_common 授权项没有资源维度，get_resources 返回 allowed=False，此时直接放行。"""
        self._create_ticket(ExternalPermissionActionEnum.LOG_COMMON.value, [])
        ctx = build_context(
            view_set="MetaViewSet",
            view_action="menu",
            declared_action_id=ExternalPermissionActionEnum.LOG_COMMON.value,
        )

        result = LEGACY_TICKET_SOURCE.check(ctx)

        self.assertTrue(result.allowed)
        self.assertEqual(result.matched_action_id, ExternalPermissionActionEnum.LOG_COMMON.value)
        self.assertIsNone(result.resource_id)
        self.assertFalse(result.allow_resources_result["allowed"])

    def test_resource_is_not_resolved_for_capabilities_without_instance_scope(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_EXTRACT.value, [])
        ctx = build_context(
            view_set="ExplorerViewSet",
            view_action="list_file",
            declared_action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value,
        )

        decision = authorize(ctx)

        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.resource_id)


class DeclaredActionIdTest(SimpleTestCase):
    def test_declared_action_id_comes_from_the_view_not_from_tickets(self):
        self.assertEqual(
            resolve_declared_action_id("SearchViewSet", "search"),
            ExternalPermissionActionEnum.LOG_SEARCH.value,
        )
        self.assertEqual(
            resolve_declared_action_id("ExplorerViewSet", "list_file"),
            ExternalPermissionActionEnum.LOG_EXTRACT.value,
        )

    def test_unmapped_view_falls_back_to_log_common(self):
        self.assertEqual(
            resolve_declared_action_id("NotAViewSet", "nope"),
            ExternalPermissionActionEnum.LOG_COMMON.value,
        )


class ResolveResourceTest(SimpleTestCase):
    LOG_SEARCH = ExternalPermissionActionEnum.LOG_SEARCH.value

    def test_index_set_id_is_read_from_the_url_first(self):
        resource_id = resolve_resource(self.LOG_SEARCH, {"index_set_id": "628108"}, '{"index_set_id": 1}')

        self.assertEqual(resource_id, ALLOWED_INDEX_SET_ID)

    def test_index_set_id_falls_back_to_the_request_body(self):
        resource_id = resolve_resource(self.LOG_SEARCH, {}, '{"index_set_id": 628108}')

        self.assertEqual(resource_id, ALLOWED_INDEX_SET_ID)

    def test_body_without_index_set_id_resolves_to_nothing(self):
        self.assertIsNone(resolve_resource(self.LOG_SEARCH, {}, '{"space_uid": "bkcc__1"}'))

    def test_unparsable_body_resolves_to_nothing_instead_of_raising(self):
        self.assertIsNone(resolve_resource(self.LOG_SEARCH, {}, "not json at all"))

    def test_capabilities_without_instance_scope_have_no_resource(self):
        self.assertIsNone(resolve_resource(ExternalPermissionActionEnum.LOG_EXTRACT.value, {"index_set_id": "1"}, ""))

    def test_clustering_action_resolves_index_set_id(self):
        resource_id = resolve_resource(
            ExternalPermissionActionEnum.LOG_CLUSTERING.value, {"index_set_id": "628108"}, ""
        )

        self.assertEqual(resource_id, ALLOWED_INDEX_SET_ID)
