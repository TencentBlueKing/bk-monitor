from django.db.models import Q
from django.utils import timezone

from bkmonitor.models import Shield
from bkmonitor.models.fta.action import ActionConfig, StrategyActionConfigRelation
from bkmonitor.models.fta.assign import AlertAssignGroup, AlertAssignRule
from bkmonitor.models.strategy import (
    AlgorithmModel,
    DetectModel,
    DutyArrange,
    DutyRule,
    DutyRuleRelation,
    ItemModel,
    NoticeSubscribe,
    QueryConfigModel,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
    UserGroup,
)
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def get_strategy_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取告警相关迁移所需的 ORM 查询配置。

    这里合并了原策略链和告警配置链，统一按业务导出：
    - 主表直接按 ``bk_biz_id`` 过滤
    - 子表通过 ``strategy_id`` 关联回策略主表
    - ``ActionConfig`` 取两部分并集：
      - 被策略动作关系表引用到的配置
      - 当前业务下自愈套餐本身的配置
    - 轮值只迁静态配置，不迁运行态排班结果
    - 屏蔽只迁当前仍生效的记录
    """
    now = timezone.now()
    strategy_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    biz_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    strategy_ids = StrategyModel.objects.filter(**(strategy_filters or {})).values_list("id", flat=True)
    related_action_config_ids = StrategyActionConfigRelation.objects.filter(strategy_id__in=strategy_ids).values_list(
        "config_id", flat=True
    )
    if bk_biz_id is None:
        action_config_filters = None
    else:
        action_config_ids = ActionConfig.objects.filter(
            Q(id__in=related_action_config_ids) | Q(bk_biz_id=str(bk_biz_id))
        ).values_list("id", flat=True)
        action_config_filters = {"id__in": action_config_ids}

    shield_filters = {
        "is_enabled": True,
        "begin_time__lte": now,
        "end_time__gte": now,
    }
    if bk_biz_id is not None:
        shield_filters["bk_biz_id"] = bk_biz_id

    user_group_ids = UserGroup.objects.filter(**(biz_filters or {})).values_list("id", flat=True)
    duty_rule_ids = DutyRule.objects.filter(**(biz_filters or {})).values_list("id", flat=True)

    return [
        (StrategyModel, strategy_filters, None),
        (ItemModel, {"strategy_id__in": strategy_ids}, None),
        (DetectModel, {"strategy_id__in": strategy_ids}, None),
        (AlgorithmModel, {"strategy_id__in": strategy_ids}, None),
        (QueryConfigModel, {"strategy_id__in": strategy_ids}, None),
        (StrategyLabel, {"strategy_id__in": strategy_ids}, None),
        (StrategyHistoryModel, {"strategy_id__in": strategy_ids}, None),
        (NoticeSubscribe, strategy_filters, None),
        (StrategyActionConfigRelation, {"strategy_id__in": strategy_ids}, None),
        (ActionConfig, action_config_filters, None),
        (Shield, shield_filters, None),
        (UserGroup, biz_filters, None),
        (DutyRule, biz_filters, None),
        (DutyRuleRelation, biz_filters, None),
        (DutyArrange, {"user_group_id__in": user_group_ids}, None),
        (DutyArrange, {"duty_rule_id__in": duty_rule_ids}, None),
        (AlertAssignGroup, biz_filters, None),
        (AlertAssignRule, biz_filters, None),
    ]
