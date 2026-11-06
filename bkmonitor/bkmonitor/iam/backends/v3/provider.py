"""Monitor V3 capabilities, directly implementing the same Provider contract as BKLog."""

from __future__ import annotations
import logging
from iam.exceptions import AuthAPIError
from bkmonitor.iam.action import canonicalize_action_id
from iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject, to_definition_id
from iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem, AuthorizedResourceScope
from iam_engine.provider.base import PermissionProvider
from iam_engine.provider.requests import VisibleResult, to_action_id, to_resource_type_id
from iam_engine.exceptions import ProviderError
from bkmonitor.iam.backends.v3.apply import V3ApplicationBuilder

logger = logging.getLogger(__name__)


def _build_eval_obj(resource: ResourceInstance, with_id: bool = True) -> dict:
    """把 ResourceInstance 转成 IAM SDK 的求值对象。

    key 为 IAM 表达式 field 全名（"{rt}.id" / "{rt}._bk_iam_path_"）。
    with_id=False 时 id 置空串，用于"空 id 求值"的全量授权判定。
    """
    rt_biz = to_resource_type_id(resource.type)
    path = "".join(f"/{to_resource_type_id(a.type)},{a.id}/" for a in resource.ancestor_chain)
    return {
        f"{rt_biz}.id": resource.id if with_id else "",
        f"{rt_biz}._bk_iam_path_": path,
    }


class V3PermissionProvider(PermissionProvider):
    name = "v3"
    requires_candidate_ids = True

    def __init__(
        self,
        client,
        system_id,
        *,
        codec,
        schema,
        resolver=None,
        client_factory=None,
        configuration=None,
        tenant_id="system",
        username="",
    ):
        self._client_instance = client
        self.client_factory = client_factory
        self.system_id = system_id
        self.schema = schema
        self.codec = codec
        self.resolver = resolver
        self.tenant_id = tenant_id
        self.username = username
        self._cfg = configuration
        self.application_builder = V3ApplicationBuilder(self)

    @property
    def client(self):
        return self._get_client("")

    def _get_client(self, tenant_id=""):
        if self.client_factory is not None:
            return self.client_factory(tenant_id)
        return self._client_instance

    def _resolve(self, resource, *, tenant_id=""):
        if "id" in resource.attributes and "name" in resource.attributes:
            # Native public V3 constructors already queried the product resource.
            return resource
        if self.resolver is None:
            return resource
        return self.resolver.resolve(resource, tenant_id=tenant_id or self.tenant_id)

    def get_apply_data(self, actions, resources=None):
        return self.application_builder.get_apply_data(actions, resources or [])

    def _action_has_resource(self, action_id):
        return bool(self.schema.actions[canonicalize_action_id(to_definition_id(action_id))].resource_type)

    @staticmethod
    def _decision(name, allowed):
        if allowed is True:
            return AuthResult.allow(name)
        if allowed is False:
            return AuthResult.deny(name)
        return AuthResult.error(name, "provider returned a non-boolean decision", "InvalidProviderResult")

    def _error(self, error):
        return AuthResult.error(self.name, str(error) or type(error).__name__, type(error).__name__)

    @property
    def _iam_client(self):
        return self.client

    def is_allowed(self, request: AuthRequest) -> AuthResult:
        try:
            client = self._get_client(request.subject.tenant_id)
            action_id = canonicalize_action_id(to_definition_id(request.action_id))
            resources = (
                []
                if not self._action_has_resource(action_id)
                else [
                    self.codec.encode_resource(r, client, batch=False)
                    for r in (self._resolve(r, tenant_id=request.subject.tenant_id) for r in request.resources)
                ]
            )
            sdk_request = client.make_request(request.subject.id, self.codec.encode_action(action_id), resources)
            check = client.is_allowed_with_cache if self.codec.is_read_action(action_id) else client.is_allowed
            return self._decision(self.name, check(sdk_request))
        except Exception as error:
            return self._error(error)

    def _encode_batch_request(self, request, *, resolve_resources=False):
        client = self._get_client(request.subject.tenant_id)
        encoded_actions = [self.codec.encode_action(canonicalize_action_id(to_definition_id(a))) for a in request.action_ids]
        groups = [
            [
                self.codec.encode_resource(
                    self._resolve(r, tenant_id=request.subject.tenant_id) if resolve_resources else r,
                    client, batch=True,
                )
                for r in group
            ]
            for group in request.resource_groups
        ]
        encoded_ids = {
            (canonicalize_action_id(to_definition_id(resource.type)), str(resource.id)): sdk_resource.id
            for group, sdk_group in zip(request.resource_groups, groups)
            for resource, sdk_resource in zip(group, sdk_group)
        }
        return client, client.make_multi_action_request(request.subject.id, encoded_actions), groups, encoded_ids

    def batch_product_is_allowed(self, request):
        """Keep the original product batch SDK result and exception contract in V3.

        The caller already supplies complete resource groups. Do not replace
        their attributes through a resolver or discard associated resources.
        """
        client, sdk_request, groups, _ = self._encode_batch_request(request)
        return client.batch_resource_multi_actions_allowed(sdk_request, groups)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        try:
            client, sdk_request, groups, encoded_ids = self._encode_batch_request(request, resolve_resources=True)
            raw = client.batch_resource_multi_actions_allowed(
                sdk_request, groups
            )
        except Exception as error:
            result = self._error(error)
            return BatchAuthResult(tuple(BatchAuthResultItem(a, r, result) for a, r in request.iter_keys()))
        items = []
        for action_id, resource_id in request.iter_keys():
            rt = next(canonicalize_action_id(to_definition_id(g[0].type)) for g in request.resource_groups if str(g[0].id) == resource_id)
            encoded_id = encoded_ids[(rt, resource_id)]
            row = raw.get(encoded_id, {})
            aid = self.codec.encode_action(action_id)
            result = (
                self._decision(self.name, row[aid])
                if aid in row
                else AuthResult.error(
                    self.name,
                    f"missing IAM V3 batch result for action={action_id}, resource={resource_id}",
                    "IncompleteBatchResult",
                )
            )
            items.append(BatchAuthResultItem(action_id, resource_id, result))
        return BatchAuthResult(tuple(items))

    def list_authorized_resources(self, *, action_id, resource_type="space", subject=None, candidate_ids=None):
        if candidate_ids is None:
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=self.name,
                reason="V3 scope requires local candidate ids",
                error_type="MissingCandidates",
            )
        request_subject = Subject(id=(subject or {}).get("id", self.username), tenant_id=self.tenant_id)
        try:
            result = self.filter_visible_resources(
                request_subject, action_id, tuple(ResourceInstance(type=resource_type, id=i) for i in candidate_ids)
            )
        except Exception as error:
            return AuthorizedResourceScope.error(
                resource_type, provider_name=self.name, reason=str(error), error_type=type(error).__name__
            )
        if result.all_granted:
            return AuthorizedResourceScope.wildcard(resource_type, provider_name=self.name)
        return AuthorizedResourceScope.concrete(resource_type, set(result.visible_ids), provider_name=self.name)

    def query_policy(
        self,
        subject: Subject,
        action_id: str,
    ) -> dict | None:
        """查询单个 action 的策略 AST。

        语义约定：
          * 查询成功、用户无权限（IAM 返回空策略）→ {}
          * 查询失败 → 抛框架统一异常 ProviderError，由调用方（framework/permission 层）降级处理
        """
        action_id_biz = canonicalize_action_id(to_action_id(action_id))
        try:
            _ = self.schema.actions[action_id_biz]
        except Exception:
            logger.warning("[iam_v3:query_policy] unknown action_id=%s", action_id_biz)
            return None

        v3_action_id = self.codec.encode_action(action_id_biz)

        client = self._get_client(subject.tenant_id)
        sdk_request = client.make_request(subject.id, v3_action_id)

        # SDK 异常在 provider 公开边界转换为框架统一异常（上层不感知 v3/v4 差异）
        try:
            dict_ast = client._do_policy_query(sdk_request, with_resources=False)
        except AuthAPIError as e:
            raise ProviderError(
                f"[iam_v3:query_policy] policy query failed, action={action_id_biz}, user={subject.id}"
            ) from e
        return dict_ast or {}

    def query_policy_by_actions(
        self,
        subject: Subject,
        action_ids: list[str],
    ) -> dict[str, dict | None]:
        """批量查询多个 action 的策略 AST。

        语义约定：
          * 批量成功、未返回/空 condition 的 action（用户无权限）→ {}
          * 批量失败 → 抛框架统一异常 ProviderError，由调用方（framework/permission 层）降级为逐个查询
        """
        action_ids_biz = [canonicalize_action_id(to_action_id(a)) for a in action_ids]
        valid_aids = []
        for aid in action_ids_biz:
            try:
                self.schema.actions[aid]
                valid_aids.append(aid)
            except Exception:
                logger.warning("[iam_v3:query_policy_by_actions] unknown action_id=%s", aid)

        if not valid_aids:
            return {aid: {} for aid in action_ids_biz}

        v3_action_ids = [self.codec.encode_action(aid) for aid in valid_aids]

        client = self._get_client(subject.tenant_id)
        sdk_request = client.make_multi_action_request(subject.id, v3_action_ids)

        # SDK 异常在 provider 公开边界转换为框架统一异常（上层不感知 v3/v4 差异）
        try:
            raw_list = client._do_policy_query_by_actions(sdk_request, with_resources=False)
        except AuthAPIError as e:
            raise ProviderError(
                f"[iam_v3:query_policy_by_actions] batch policy query failed, actions={valid_aids}, user={subject.id}"
            ) from e

        # raw_list: [{"action": {"id": "v3_id"}, "condition": {...}}, ...]
        # 先构建有效结果，再补齐未返回的 action
        result: dict[str, dict | None] = {}
        for item in raw_list or []:
            v3_aid = item.get("action", {}).get("id", "")
            if not v3_aid:
                continue
            biz_aid = self.codec.decode_action(v3_aid)
            if biz_aid:
                # Empty successful conditions remain distinct from query failures.
                result[biz_aid] = item.get("condition") or {}

        # 未返回的 action：批量查询成功但没有该 action 的策略 → 无权限
        for aid in action_ids_biz:
            if aid not in result:
                result[aid] = {}

        return result

    # ================================================================
    # 可见性能力（低层能力）
    def has_any_permission(
        self,
        subject: Subject,
        action_id: str,
    ) -> bool:
        """v3：query_policy 返回非空表达式即视为有实例级权限（近似判定）。

        跨 org 场景可能"有权限但不在当前 org"——由资源层精确过滤兜底，
        与旧 Grafana 行为一致（表达式全局解析后按 org 匹配）。
        AuthAPIError 向上抛，由调用方决定降级。
        """
        expr = self.query_policy(subject, action_id)
        return bool(expr) and expr.get("op") != "none"

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """v3：query_policy 表达式 + IAM SDK 本地求值（1 次 API）。

        性能约定：顶层资源候选可达数十万（如 space 列表过滤），
        对 "{rt}.id" 上的 IN/EQ 叶子走集合快速路径，避免逐候选求值。
        """
        expr = self.query_policy(subject, action_id)
        if not expr or expr.get("op") == "none":
            return VisibleResult()
        if expr.get("op") == "any":
            return VisibleResult(all_granted=True, visible_ids=tuple(c.id for c in candidates))
        if not candidates:
            return VisibleResult()

        # Grafana V3 的产品范围原本来自策略 ID（包含 bare UID 和 folder），
        # 不能改为仅返回本地 DB 候选或用另一套解析规则替代。
        if to_resource_type_id(candidates[0].type) == "grafana_dashboard":
            from iam import make_expression
            from bkmonitor.iam.backends.v3.grafana import policy_resource_ids

            policy = expr
            probe = _build_eval_obj(candidates[0], with_id=False)
            all_granted = make_expression(policy).eval(probe)
            org_id = None
            for candidate in candidates:
                raw_id = candidate.id.removeprefix("folder:")
                if "|" in raw_id:
                    org_id = int(raw_id.split("|", 1)[0])
                    break
            if org_id is None:
                return VisibleResult(all_granted=all_granted)
            bk_biz_id = next((parent.id for parent in candidates[0].ancestor_chain if parent.type == "space"), 0)
            return VisibleResult(all_granted, tuple(sorted(policy_resource_ids(policy, org_id, bk_biz_id))))

        # 快速路径："{rt}.id" 的 IN/EQ → 集合过滤（O(N) set 查找，与旧 filter_space_list 的 IN 分支对齐）
        rt_biz = to_resource_type_id(candidates[0].type)
        id_field = f"{rt_biz}.id"
        if expr.get("op") in ("in", "eq") and expr.get("field") == id_field:
            # SDK 的 IN 只接受数组；不能把字符串拆成字符或改变数值类型。
            values = expr.get("value") if expr.get("op") == "in" else (expr.get("value"),)
            if not isinstance(values, list | tuple):
                return VisibleResult()
            try:
                allowed = set(values)
            except TypeError:
                # Array-valued EQ and nested values must retain SDK semantics.
                allowed = None
            if allowed is not None:
                return VisibleResult(
                    visible_ids=tuple(c.id for c in candidates if c.id in allowed),
                )

        # V3 必须沿用 SDK 求值器，不能以中立求值器替代其历史数组/path 语义。
        from iam import make_expression

        evaluator = make_expression(expr)

        # 全量判定：空 id + 首个候选的父链（约定同批候选共享父链，如 Grafana 单 org 一批）
        all_granted = False
        if rt_biz != "space" and evaluator.eval(_build_eval_obj(candidates[0], with_id=False)):
            all_granted = True

        visible: list[str] = []
        for c in candidates:
            if evaluator.eval(_build_eval_obj(c)):
                visible.append(c.id)

        return VisibleResult(all_granted=all_granted, visible_ids=tuple(visible))

    # ================================================================
    # 内部：action 元数据辅助方法
    def health_check(self) -> dict:
        """探活检查，委托给 V3Client。"""
        result = self._iam_client.health_check()
        result["provider"] = self.name
        result["remote_id"] = self._cfg.system.id
        return result
