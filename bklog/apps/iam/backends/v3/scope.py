from __future__ import annotations

from iam import ObjectSet, Request, Subject, make_expression
from iam.exceptions import AuthAPIError

from apps.iam.backends.v3.codec import V3RequestCodec
from apps.iam.iam_engine.core.types import AuthorizedResourceScope

# IAM v1 策略在 CompatibleIAM 中已经转换为 space.id；这里只优化转换后的稳定形态。
FLATTENABLE_FIELD = "space.id"
FLATTENABLE_ANY_FIELDS = frozenset({FLATTENABLE_FIELD, ""})


def try_flatten_space_policy(policies: dict) -> dict | None:
    """
    将仅包含 any、space.id eq/in 和 OR 的策略树转换为全量标记或 ID 集合。

    为保证与 IAM SDK 的类型比较语义一致，策略值必须已经是字符串；
    任一节点格式或算子不满足约束时，返回 None 交给原始表达式求值逻辑。

    返回：
      {"mode": "any"}                   -> 策略恒真，全放行
      {"mode": "flat", "allowed": set} -> 已抽取 biz_id 白名单
      None                              -> 无法平坦化，走兜底
    """

    def analyze(node):
        if not isinstance(node, dict):
            return None

        op = node.get("op")
        if op == "any":
            # IAM 的全量策略可能使用 space.id 或空 field；
            # 其他字段交回 SDK，避免改变异常和权限语义。
            if node.get("field") not in FLATTENABLE_ANY_FIELDS or "value" not in node:
                return None
            return {"mode": "any"}

        if op == "eq":
            value = node.get("value")
            if node.get("field") != FLATTENABLE_FIELD or not isinstance(value, str):
                return None
            return {"mode": "flat", "allowed": {value}}

        if op == "in":
            value = node.get("value")
            if (
                node.get("field") != FLATTENABLE_FIELD
                or not isinstance(value, list | tuple)
                or not all(isinstance(item, str) for item in value)
            ):
                return None
            return {"mode": "flat", "allowed": set(value)}

        if op != "OR":
            return None

        content = node.get("content")
        if not isinstance(content, list | tuple):
            return None

        allowed = set()
        for child in content:
            result = analyze(child)
            if result is None:
                return None
            if result["mode"] == "any":
                return {"mode": "any"}
            allowed.update(result["allowed"])

        return {"mode": "flat", "allowed": allowed}

    return analyze(policies)


class V3AuthorizedScopeQuery:
    """用 policy_query + 本地表达式求值给出 IAM V3 的顶层资源授权范围。

    V3 没有"列出已授权资源"的接口，无法平坦化的策略只能逐个候选求值，
    因此 requires_candidate_ids 为 True，调用方必须先给出候选 ID 集合。
    """

    name = "v3"
    requires_candidate_ids = True

    def __init__(self, client, system_id: str, *, codec: V3RequestCodec | None = None) -> None:
        self.client = client
        self.system_id = system_id
        self.codec = codec or V3RequestCodec(system_id)

    def list_authorized_resources(
        self,
        *,
        action_id: str,
        resource_type: str = "space",
        subject: dict[str, str] | None = None,
        candidate_ids: frozenset[str] | None = None,
    ) -> AuthorizedResourceScope:
        request_subject = subject or {}
        subject_id = str(request_subject.get("id") or "").strip()
        if not subject_id:
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=self.name,
                reason="IAM V3 policy query requires a non-empty subject id",
                error_type="InvalidSubject",
            )

        request = Request(
            system=self.system_id,
            subject=Subject(request_subject.get("type") or "user", subject_id),
            action=self.codec.encode_action(action_id),
            resources=[],
            environment=None,
        )
        try:
            policies = self.client._do_policy_query(request)
        except AuthAPIError as error:
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=self.name,
                reason=str(error) or "IAM V3 policy query failed",
                error_type=type(error).__name__,
            )

        if not policies:
            return AuthorizedResourceScope.empty(resource_type, provider_name=self.name)

        # 平坦化快路径：只优化可证明等价的策略树，其他形态回退 IAM SDK。
        flat = try_flatten_space_policy(policies)
        if flat is not None:
            if flat["mode"] == "any":
                return AuthorizedResourceScope.wildcard(resource_type, provider_name=self.name)
            return AuthorizedResourceScope.concrete(resource_type, flat["allowed"], provider_name=self.name)

        if candidate_ids is None:
            return AuthorizedResourceScope.error(
                resource_type,
                provider_name=self.name,
                reason="IAM V3 policy expression evaluation requires candidate ids",
                error_type="MissingCandidateIds",
            )

        # SDK 支持但无法安全平坦化的算子和树结构继续走原始求值逻辑。
        expr = make_expression(policies)
        allowed_ids = set()
        for candidate_id in candidate_ids:
            obj_set = ObjectSet()
            obj_set.add_object(_type=resource_type, obj={"id": candidate_id})
            if self.client._eval_expr(expr, obj_set):
                allowed_ids.add(candidate_id)
        return AuthorizedResourceScope.concrete(resource_type, allowed_ids, provider_name=self.name)
