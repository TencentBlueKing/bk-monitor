"""
TAPD3: 外部链路 PO(legacy) OR IAM 统一决策组件。

身份三分离约束（禁止混用）：
  - authorization_subject: 恒为 external_user，legacy_check / iam_check 的 subject 均为此值
  - execution_user: 内部授权人(authorizer)，仅作下游代理执行身份，不参与鉴权判断，只透传进审计结果
  - audit_user: 恒为 external_user，与 authorization_subject 一致

decide() 与具体资源类型无关，供 04/05 等后续能力复用。
"""
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum
from apps.log_commons.models import ExternalPermission
from apps.utils.log import logger
from bkm_space.utils import space_uid_to_bk_biz_id


@dataclass
class CheckResult:
    """单侧(legacy/iam)判断结果。allowed=None 表示异常/不可判定，fail-closed。"""

    allowed: bool | None
    resources: set = field(default_factory=set)
    source: str = "none"
    detail: str = ""


@dataclass
class DecisionResult:
    """OR决策最终结果，强制携带三身份字段。"""

    allowed: bool
    resources: set
    decision_source: str  # legacy / iam / both / none
    warning: bool
    authorization_subject: str
    execution_user: str
    audit_user: str
    reason: str = ""


class ExternalLogSearchPermissionDecision:
    """
    外部日志检索场景 legacy(PO) OR iam 决策组件。

    硬约束:
      1) legacy_check/iam_check 的 subject 恒为 external_user，绝不传 authorizer。
      2) execution_user(authorizer) 只透传进 DecisionResult 供审计，不参与 allowed/resources 计算。
      3) IAM 异常 -> source="error", allowed=None, resources=set()，不可被当作允许/扩权依据。
    """

    @classmethod
    def _get_legacy_action_ids(cls, space_uid: str, external_user: str) -> list:
        action_ids = list(
            ExternalPermission.get_authorizer_permission(space_uid=space_uid, authorizer=external_user).get(
                space_uid, []
            )
        )
        if (
            ExternalPermissionActionEnum.CLIENT_LOG.value in action_ids
            and ExternalPermissionActionEnum.LOG_SEARCH.value not in action_ids
        ):
            action_ids.append(ExternalPermissionActionEnum.LOG_SEARCH.value)
        return action_ids

    @classmethod
    def legacy_check(cls, *, space_uid, external_user, view_set, view_action, resource_id):
        """legacy(PO) 判断，subject 恒为 external_user。resource_id=None 表示列表类接口。"""
        action_ids = cls._get_legacy_action_ids(space_uid=space_uid, external_user=external_user)
        if not action_ids:
            return CheckResult(allowed=False, source="legacy", detail="no_legacy_action")

        matched_action_id = ""
        for action_id in action_ids:
            if ExternalPermission.is_action_valid(view_set=view_set, view_action=view_action, action_id=action_id):
                matched_action_id = action_id
                break
        if not matched_action_id:
            return CheckResult(allowed=False, source="legacy", detail="action_not_match")

        resources = set()
        if matched_action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
            resources_result = ExternalPermission.get_resources(
                space_uid=space_uid, action_id=matched_action_id, authorized_user=external_user
            )
            resources = {int(r) for r in resources_result.get("resources", [])}

        if resource_id is None:
            return CheckResult(allowed=True, resources=resources, source="legacy", detail="action_allowed")

        return CheckResult(
            allowed=int(resource_id) in resources,
            resources=resources,
            source="legacy",
            detail="resource_allowed" if int(resource_id) in resources else "resource_denied",
        )

    @classmethod
    def iam_check_resource(cls, *, space_uid, external_user, resource_id):
        """IAM 判断，subject 恒为 external_user。resource_id=None 时不可判定（返回 None，不参与放通）。"""
        if resource_id is None:
            return CheckResult(allowed=None, source="iam", detail="resource_not_provided")

        try:
            attribute = {"bk_biz_id": space_uid_to_bk_biz_id(space_uid), "space_uid": space_uid}
            resource = ResourceEnum.INDICES.create_simple_instance(instance_id=resource_id, attribute=attribute)
            allowed = Permission(username=external_user, bk_tenant_id=settings.BK_APP_TENANT_ID).is_allowed(
                ActionEnum.SEARCH_LOG, [resource], raise_exception=False
            )
            return CheckResult(allowed=allowed, resources={int(resource_id)} if allowed else set(), source="iam")
        except Exception as err:  # pylint: disable=broad-except
            logger.exception(
                "iam_check_resource failed, external_user=%s, resource_id=%s, error=%s",
                external_user, resource_id, err,
            )
            return CheckResult(allowed=None, source="error", detail=str(err))

    @classmethod
    def batch_iam_allowed_resources(cls, *, space_uid, external_user, resource_ids):
        """批量 IAM 判断（一次 HTTP 调用），subject 恒为 external_user，用于列表场景避免逐条请求 IAM。"""
        if not resource_ids:
            return set()
        try:
            attribute = {"bk_biz_id": space_uid_to_bk_biz_id(space_uid), "space_uid": space_uid}
            iam_resources = [
                [ResourceEnum.INDICES.create_simple_instance(instance_id=rid, attribute=attribute)]
                for rid in resource_ids
            ]
            permission_result = Permission(
                username=external_user, bk_tenant_id=settings.BK_APP_TENANT_ID
            ).batch_is_allowed(actions=[ActionEnum.SEARCH_LOG], resources=iam_resources)
            return {
                int(rid)
                for rid, action_result in permission_result.items()
                if action_result.get(ActionEnum.SEARCH_LOG.id, False)
            }
        except Exception as err:  # pylint: disable=broad-except
            logger.exception(
                "batch_iam_allowed_resources failed, external_user=%s, error=%s", external_user, err
            )
            return set()

    @classmethod
    def decide(cls, *, external_user, execution_user, legacy_result, iam_result):
        """
        通用 OR 决策矩阵，与资源类型无关。
        资源并集永远是 legacy.resources ∪ iam.resources；source="error" 侧的 resources 恒为空集，不参与并集放大。
        """
        legacy_allowed = legacy_result.allowed
        iam_allowed = iam_result.allowed
        warning = legacy_result.source == "error" or iam_result.source == "error"

        if legacy_allowed is True and iam_allowed is True:
            decision_source, allowed, resources = "both", True, legacy_result.resources | iam_result.resources
        elif legacy_allowed is True:
            decision_source, allowed, resources = "legacy", True, legacy_result.resources
        elif iam_allowed is True:
            decision_source, allowed, resources = "iam", True, iam_result.resources
        else:
            decision_source, allowed, resources = "none", False, set()

        return DecisionResult(
            allowed=allowed,
            resources=resources,
            decision_source=decision_source,
            warning=warning,
            authorization_subject=external_user,
            execution_user=execution_user,
            audit_user=external_user,
            reason="" if allowed else "legacy_and_iam_denied_or_unavailable",
        )


class ExternalLogExtractPermissionDecision:
    """外部日志提取场景 legacy(PO) OR strategy 决策组件。

    复用 TAPD3 的 decide() 通用 OR 决策矩阵，与 LogSearch 保持一致的 CheckResult/DecisionResult 契约。

    PO 日志提取路径依赖两种授权来源：
      - legacy: ExternalPermission.log_extract 在有效期内（expire_time > now）
      - strategy: Strategies 表中 user_list 包含当前 external_user

    两者满足其一即可放行入口；入口放行后，具体的文件浏览/任务创建仍需经过 Strategies
    内部的主机/拓扑/目录/文件类型硬校验（不参与 OR）。
    """

    @classmethod
    def legacy_check(cls, *, space_uid, external_user):
        """查 ExternalPermission.log_extract 是否未过期。

        与 TAPD3 LogSearch 不同，此处直接查 expire_time > now 而非遍历 action_id 列表，
        因为 log_extract 只有一个 action_id，且不需要 resource 级权限判定。
        """
        has_log_extract = ExternalPermission.objects.filter(
            authorized_user=external_user,
            space_uid=space_uid,
            action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value,
            expire_time__gt=timezone.now(),
        ).exists()
        return CheckResult(
            allowed=has_log_extract,
            source="legacy",
            detail="legacy_valid" if has_log_extract else "legacy_expired_or_missing",
        )

    @classmethod
    def strategy_check(cls, *, bk_biz_id, external_user):
        """查 Strategies 表中 external_user 是否有可用策略。

        user_list 存储格式为 ",user1,user2,"，使用 ",{external_user}," 锚定匹配
        天然防止字符串包含误匹配（如 user="alice" 不会匹配到 "alice_2"）。
        """
        from apps.log_extract.models import Strategies

        has_strategy = Strategies.objects.filter(
            bk_biz_id=bk_biz_id,
            user_list__contains=f",{external_user},",
        ).exclude(operator="").exists()
        return CheckResult(
            allowed=has_strategy,
            source="strategy",
            detail="strategy_found" if has_strategy else "no_strategy",
        )

    @classmethod
    def decide(cls, *, external_user, execution_user, legacy_result, strategy_result):
        """日志提取 OR 决策矩阵，复用 TAPD3 同款 decide() 逻辑。

        与 LogSearch 的区别：第二个判据是 strategy_result（策略表中 user_list 包含外部用户），
        而非 iam_result（IAM 权限中心查询）。
        """
        legacy_allowed = legacy_result.allowed
        strategy_allowed = strategy_result.allowed

        # source="error" 侧的 resources 恒为空集，不可被当作允许/扩权依据
        if legacy_result.source == "error":
            legacy_allowed = None
        if strategy_result.source == "error":
            strategy_allowed = None

        warning = legacy_result.source == "error" or strategy_result.source == "error"

        if legacy_allowed is True and strategy_allowed is True:
            decision_source, allowed = "both", True
        elif legacy_allowed is True:
            decision_source, allowed = "legacy", True
        elif strategy_allowed is True:
            decision_source, allowed = "strategy", True
        else:
            decision_source, allowed = "none", False

        return DecisionResult(
            allowed=allowed,
            resources=set(),
            decision_source=decision_source,
            warning=warning,
            authorization_subject=external_user,
            execution_user=execution_user,
            audit_user=external_user,
            reason="" if allowed else "legacy_and_strategy_denied_or_unavailable",
        )
