import logging
from collections.abc import Callable
from typing import Any, TypedDict, cast

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .constants import ActionSignal
from .converter import restore_strategy
from .errors import StrategyNotExistError
from .models import QueryConfigModel, StrategyModel, UserGroup
from .partial_update import StrategyPartialUpdater
from .query_engine import FilterCondition, StrategyQueryEngine
from .strategy import Strategy

logger = logging.getLogger(__name__)


def save_strategy(
    bk_biz_id: int,
    strategy_json: dict[str, Any],
    operator: str,
    *,
    aiops_access_func: Callable[[int], str] | None = None,
    apply_converters: bool = True,
) -> dict[str, Any]:
    """创建或更新策略。

    Args:
        bk_biz_id: 业务 ID
        strategy_json: 策略大 JSON（入参）
        operator: 操作人
        aiops_access_func: 智能检测接入函数（可选）
        apply_converters: 是否在保存前 convert

    Returns:
        dict[str, Any]: 当前仅返回保存后的策略 ID，例如 {"id": 1}。
    """
    strategy_json["bk_biz_id"] = bk_biz_id
    serializer = Strategy.Serializer(data=strategy_json)
    serializer.is_valid(raise_exception=True)
    strategy = Strategy(**cast(dict[str, Any], serializer.validated_data))

    # 更新场景：先做存在性校验（避免 Strategy.save() 进入“get失败再create”的兜底逻辑）
    if strategy.id and strategy.id > 0:
        exists = StrategyModel.objects.filter(id=strategy.id, bk_biz_id=strategy.bk_biz_id).exists()
        if not exists:
            raise StrategyNotExistError()

    if apply_converters:
        # converter.py 内存在运行时类型注解问题（Protocol 引用 Strategy 未定义）。
        # 为了不修改领域模块代码，这里做“可用则调用，不可用则跳过”的降级处理。
        try:
            from bk_monitor_base.domains.strategy.converter import convert_strategy
        except Exception:  # noqa: BLE001 - 需兼容导入期错误
            logger.warning("strategy.converter import failed; skip convert_strategy", exc_info=True)
        else:
            convert_strategy(strategy)

    strategy.save(operator=operator, aiops_access_func=aiops_access_func)

    # 只返回策略 ID：上层若需要完整策略，可通过 get_strategy 获取（并按需 restore）。
    strategy_id = int(getattr(strategy, "id", 0) or 0)
    return {"id": strategy_id}


def delete_strategy(bk_biz_id: int, strategy_id: int, operator: str) -> None:
    """删除策略。

    说明：
    - 按你的要求，删除逻辑直接复用 strategy 域已有删除接口，不在 operation 层自行实现。
    - 当前实现会执行物理删除（策略及其关联子表），并写入 delete history。
    """
    if strategy_id <= 0:
        raise ValidationError("strategy_id must be a positive integer")

    exists = StrategyModel.objects.filter(id=strategy_id, bk_biz_id=bk_biz_id).exists()
    if not exists:
        raise StrategyNotExistError()

    Strategy.delete_by_strategy_ids([strategy_id], operator=operator)


def get_strategy(
    bk_biz_id: int | None = None,
    strategy_id: int = 0,
    apply_converters: bool = True,
) -> dict[str, Any]:
    """获取策略（完整配置）。"""
    if strategy_id <= 0:
        raise ValidationError("strategy_id must be a positive integer")

    try:
        if bk_biz_id is not None:
            model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=bk_biz_id)
        else:
            model = StrategyModel.objects.get(id=strategy_id)
    except StrategyModel.DoesNotExist:
        raise StrategyNotExistError() from None

    strategy = Strategy.from_models([model])[0]
    if apply_converters:
        restore_strategy(strategy)

    return strategy.to_dict()


def update_strategy_query_config(
    strategy_id: int,
    config: dict[str, Any] | None = None,
    *,
    alias: str | None = None,
    metric_id: str | None = None,
) -> dict[str, Any]:
    """按策略维度合并更新查询配置。

    说明：
    - 支持更新 `alarm_query_config_v2` 的 `config` / `alias` / `metric_id` 字段。
    - `config` 更新方式为浅合并（`dict.update`）。
    - 传入 `None` 表示对应字段不更新；`config={}` 视为无实际更新。
    - 不调用 `Strategy.save()`，因此不会写入策略变更历史。

    Args:
        strategy_id: 策略 ID。
        config: 需要合并写入 query_config.config 的配置字典；None 表示不更新。
        alias: 需要更新的别名；None 表示不更新。
        metric_id: 需要更新的指标 ID；None 表示不更新。

    Returns:
        dict[str, Any]: 更新结果，格式为 `{"strategy_id": int, "updated_count": int}`。

    Raises:
        StrategyNotExistError: 策略不存在。
    """
    with transaction.atomic():
        exists = StrategyModel.objects.filter(id=strategy_id).exists()
        if not exists:
            raise StrategyNotExistError()

        query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id))
        if not query_configs:
            logger.warning("update_strategy_query_config: no query config found, strategy_id=%s", strategy_id)
            return {"strategy_id": strategy_id, "updated_count": 0}

        update_fields: list[str] = []
        if config:
            update_fields.append("config")
        if alias is not None:
            update_fields.append("alias")
        if metric_id is not None:
            update_fields.append("metric_id")
        if not update_fields:
            logger.info(
                "update_strategy_query_config: no effective fields to update, skip update, strategy_id=%s",
                strategy_id,
            )
            return {"strategy_id": strategy_id, "updated_count": 0}

        for query_config in query_configs:
            if config:
                merged_config = dict(query_config.config or {})
                merged_config.update(config)
                query_config.config = merged_config
            if alias is not None:
                query_config.alias = alias
            if metric_id is not None:
                query_config.metric_id = metric_id

        QueryConfigModel.objects.bulk_update(query_configs, update_fields)
        return {"strategy_id": strategy_id, "updated_count": len(query_configs)}


class ListStrategyResult(TypedDict):
    """查询策略列表（简要信息）返回结果"""

    count: int
    data: list[dict[str, Any]]


def list_strategy(
    bk_biz_id: int | None = None,
    bk_biz_ids: list[int] | None = None,
    is_enabled: bool | None = None,
    apply_converters: bool = True,
    conditions: list[FilterCondition] | None = None,
    scenario: str | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> ListStrategyResult:
    """查询策略列表（简要信息）。

    Args:
        bk_biz_id: 业务 ID，如果为 None，则查询所有业务ID的策略
        bk_biz_ids: 业务 ID 列表，如果为 None，则查询所有业务ID的策略
        is_enabled: 是否启用，如果为 None，则查询所有状态的策略
        apply_converters: 是否在返回前 restore_strategy
        conditions: QueryEngine 条件列表（FilterSpec 风格）
        scenario: 可选场景过滤；当传入 conditions 时由引擎处理，否则直接作用于 StrategyModel
        offset: 偏移量
        limit: 限制数量(如果为空，则不进行分页)
    """
    qs = StrategyModel.objects.all()
    if bk_biz_id is not None:
        qs = qs.filter(bk_biz_id=bk_biz_id)
    if bk_biz_ids:
        qs = qs.filter(bk_biz_id__in=bk_biz_ids)
    if is_enabled is not None:
        qs = qs.filter(is_enabled=is_enabled)

    if conditions:
        qs = StrategyQueryEngine.filter_strategies(
            bk_biz_id=bk_biz_id,
            conditions=conditions,
            scenario=scenario,
            base_qs=qs,
        )
    elif scenario:
        qs = qs.filter(scenario=scenario)

    # 排序
    qs = qs.order_by("-update_time")

    # 分页查询
    if limit and limit > 0:
        count = qs.count()
        qs = qs[offset : offset + limit]
    else:
        count = qs.count()

    strategies = Strategy.from_models(qs)
    # 恢复策略配置
    if apply_converters:
        for strategy in strategies:
            restore_strategy(strategy)

    return ListStrategyResult(count=count, data=[strategy.to_dict() for strategy in strategies])


class ListPlainStrategyData(TypedDict):
    """查询策略列表（简要信息）返回数据"""

    id: int
    name: str
    scenario: str
    is_enabled: bool


class ListPlainStrategyResult(TypedDict):
    """查询策略列表（简要信息）返回结果"""

    count: int
    data: list[ListPlainStrategyData]


def list_plain_strategy(
    bk_biz_id: int,
    *,
    strategy_ids: list[int] | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> ListPlainStrategyResult:
    """查询策略列表（简要信息）

    Args:
        bk_biz_id: 业务 ID
        strategy_ids: 策略 ID 列表(如果为空，则查询所有策略)
        search: 搜索条件(如果为空，则不进行搜索)
        offset: 偏移量
        limit: 限制数量(如果为空，则不进行分页)

    Returns:
        count: 策略总数
        data: 策略列表

    Examples:
        {
            "count": 100,
            "data": [
                {
                    "id": 1,
                    "name": "策略1",
                    "scenario": "场景1",
                    "is_enabled": True,
                },
            ],
        }

    """
    qs = StrategyModel.objects.filter(bk_biz_id=bk_biz_id).order_by("-update_time", "-id")

    # 过滤策略 ID
    if strategy_ids:
        qs = qs.filter(id__in=strategy_ids)

    # 搜索策略名称/ID
    if search:
        query = None

        # 尝试当成策略ID查询
        try:
            strategy_id = int(search)
            query = Q(id=strategy_id)
        except (ValueError, TypeError):
            pass

        # 查询策略名称
        if query is None:
            query = Q(name__icontains=search)
        else:
            query |= Q(name__icontains=search)

        qs = qs.filter(query)

    # 分页查询
    if limit and limit > 0:
        count = qs.count()
        qs = qs[offset : offset + limit]
    else:
        count = len(qs)

    data: list[ListPlainStrategyData] = [
        ListPlainStrategyData(
            id=strategy.pk, name=strategy.name, scenario=strategy.scenario, is_enabled=strategy.is_enabled
        )
        for strategy in qs
    ]

    return ListPlainStrategyResult(
        count=count,
        data=data,
    )


def switch_strategy(
    strategy_ids: list[int],
    is_enabled: bool,
    operator: str,
) -> dict[str, Any]:
    """批量启停策略。

    说明：
    - 策略 ID 全局唯一，不校验 bk_biz_id
    - 仅更新实际存在的策略，不存在的策略 ID 会被忽略

    Args:
        strategy_ids: 策略 ID 列表
        is_enabled: 是否启用
        operator: 操作人
        labels: 过滤标签列表
        only_change_updated_strategy: 是否只更新已更新过的策略

    Returns:
        dict[str, Any]: {"ids": [实际存在并更新的策略 ID 列表]}
    """
    if not strategy_ids:
        return {"ids": []}

    # 过滤出实际存在的策略 ID
    existing_ids = list(StrategyModel.objects.filter(id__in=strategy_ids).values_list("id", flat=True))
    if not existing_ids:
        return {"ids": []}

    # 批量更新
    StrategyModel.objects.filter(id__in=existing_ids).update(
        is_enabled=is_enabled,
        update_user=operator,
    )

    logger.info(
        "switch_strategy: updated %d strategies, is_enabled=%s, operator=%s",
        len(existing_ids),
        is_enabled,
        operator,
    )

    return {"ids": existing_ids}


class PartialUpdateLabels(TypedDict, total=False):
    """labels 字段的局部更新参数（与 bkmonitor 对齐）。"""

    labels: list[str]
    append_keys: list[str]


PartialUpdateTarget = list[list[dict[str, Any]]]


class PartialUpdateEditData(TypedDict, total=False):
    """策略局部更新 edit_data（与 bkmonitor `UpdatePartialStrategyV2Resource` 对齐）。"""

    is_enabled: bool
    notice_group_list: list[int]
    labels: PartialUpdateLabels
    trigger_config: dict[str, Any]
    recovery_config: dict[str, Any]
    alarm_interval: int
    send_recovery_alarm: bool
    message_template: str
    no_data_config: dict[str, Any]
    notice: dict[str, Any]
    target: PartialUpdateTarget
    actions: list[dict[str, Any]]
    algorithms: list[dict[str, Any]]


def update_partial_strategy(
    bk_biz_id: int, ids: list[int], edit_data: PartialUpdateEditData, operator: str
) -> list[int]:
    """批量更新策略的局部配置（partial update）。

    Args:
        bk_biz_id: 业务 ID
        ids: 需要批量更新的策略 ID 列表
        edit_data: 局部更新字段与参数（见下方字段说明）
        operator: 操作人

    edit_data 支持字段与参数格式（按字段说明语义）：
    - **is_enabled**: `bool`
      - 更新策略启停状态（StrategyModel.is_enabled）。
    - **notice_group_list**: `list[int]`
      - 更新通知组；会同步到 notice 与 actions 的 user_groups。
    - **labels**: `{"labels": list[str], "append_keys"?: list[str]}`
      - 若 `append_keys` 包含 `"labels"`：将 labels 追加到原策略标签集合；否则替换为传入 labels。
    - **trigger_config**: `dict`
      - 合并（shallow update）到每个 Detect 的 trigger_config。
    - **recovery_config**: `dict`
      - 替换每个 Detect 的 recovery_config。
    - **alarm_interval**: `int`
      - 通知间隔（分钟）；会写入 notice.config.notify_interval（秒，= alarm_interval * 60）。
    - **send_recovery_alarm**: `bool`
      - 是否发送恢复通知；会增删 notice.signal 中的 `RECOVERED`。
    - **message_template**: `str`
      - 更新通知模板内容：遍历 notice.config.template，将每个元素的 `message_tmpl` 置为该值。
    - **no_data_config**: `dict`
      - 递归合并到每个 Item 的 no_data_config。
    - **notice**: `dict`
      - 合并到 notice（支持 `append_keys` 语义：对指定 key 的 list 进行追加合并）；合并后会同步：\n
        - actions.user_groups = notice.user_groups\n
        - actions.options.start_time/end_time = notice.options.start_time/end_time（若缺省使用 00:00:00/23:59:59）
    - **target**: `list[list[dict]]`
      - 更新每个 Item 的 target；若传入空/无有效 value，则写入空列表 `[]`。
    - **actions**: `list[dict]`
      - 全量替换 actions；单个 action 的数据格式需满足领域内 `ActionRelation.Serializer` 的要求。
    - **algorithms**: `list[dict]`
      - 覆盖每个 Item 的算法列表；单个算法的格式需满足领域内 `Algorithm.Serializer` 的要求。

    Returns:
        list[int]: 实际更新的策略 ID 列表（仅包含存在且属于该业务的策略）。
    """

    return StrategyPartialUpdater(bk_biz_id=bk_biz_id, ids=ids, edit_data=edit_data).execute(operator=operator)


def delete_strategies(
    bk_biz_id: int,
    strategy_ids: list[int],
    operator: str,
) -> list[int]:
    """批量删除策略。

    说明：
    - 复用 Strategy.delete_by_strategy_ids() 进行删除
    - 仅删除实际存在且属于该业务的策略

    Args:
        bk_biz_id: 业务 ID
        strategy_ids: 策略 ID 列表
        operator: 操作人

    Returns:
        list[int]: 实际删除的策略 ID 列表
    """
    if not strategy_ids:
        return []

    # 过滤出实际存在且属于该业务的策略 ID
    existing_ids = list(
        StrategyModel.objects.filter(
            id__in=strategy_ids,
            bk_biz_id=bk_biz_id,
        ).values_list("id", flat=True)
    )
    if not existing_ids:
        return []

    # 批量删除
    Strategy.delete_by_strategy_ids(existing_ids, operator=operator)

    logger.info(
        "delete_strategies: deleted %d strategies, bk_biz_id=%d, operator=%s",
        len(existing_ids),
        bk_biz_id,
        operator,
    )

    return existing_ids


# ============ 策略 JSON 格式转换 ============
def transform_strategy_json(strategy_json: dict[str, Any]) -> dict[str, Any]:
    """将旧 API 格式的 strategy_json 转换为新格式。

    转换逻辑参考 strategy_v2.py 的 SaveStrategyResource.perform_request。

    主要转换：
    1. actions[0] → notice（通知配置）
    2. 根据 UserGroup.webhook_action_id 构建新的 actions（webhook 动作）
    3. detects 补充 uptime 配置

    Args:
        strategy_json: 旧 API 格式的策略配置

    Returns:
        转换后的新格式策略配置

    Raises:
        Exception: 转换失败时抛出异常
    """

    try:
        strategy_json = strategy_json.copy()

        actions = strategy_json.pop("actions", [])
        if not actions:
            # 没有 actions，设置空的 notice 和 actions
            logger.warning(
                "transform_strategy_json: no actions found, strategy_id=%s",
                strategy_json.get("id"),
            )
            strategy_json["notice"] = {
                "user_groups": [],
                "signal": [],
                "options": {"converge_config": {"need_biz_converge": True}},
                "config": {
                    "notify_interval": 7200,
                    "interval_notify_mode": "standard",
                    "template": [],
                },
            }
            strategy_json["actions"] = []
            return strategy_json

        action = actions[0]
        action_config = action.get("config", {})

        # 1. 构建 notice
        strategy_json["notice"] = _build_notice(action, action_config)

        # 2. 构建 webhook_actions
        strategy_json["actions"] = _build_webhook_actions(action)

        # 3. 处理 detects uptime
        _transform_detects_uptime(strategy_json, action_config)

        return strategy_json
    except Exception:
        logger.exception(
            "transform_strategy_json failed: strategy_id=%s",
            strategy_json.get("id"),
        )
        raise


def _build_notice(
    action: dict[str, Any],
    action_config: dict[str, Any],
) -> dict[str, Any]:
    """从旧格式 action 构建新格式 notice。

    Args:
        action: 旧格式的 action 配置
        action_config: action 中的 config 字段

    Returns:
        新格式的 notice 配置，失败时返回默认空 notice
    """
    try:
        signal = [ActionSignal.ABNORMAL, ActionSignal.NO_DATA]
        if action_config.get("send_recovery_alarm"):
            signal.append(ActionSignal.RECOVERED)

        notice_template = action.get("notice_template", {})

        return {
            "user_groups": action.get("notice_group_ids", []),
            "signal": signal,
            "options": {
                "converge_config": {"need_biz_converge": True},
            },
            "config": {
                "notify_interval": int(action_config.get("alarm_interval", 120)) * 60,
                "interval_notify_mode": "standard",
                "template": [
                    {
                        "signal": ActionSignal.ABNORMAL,
                        "message_tmpl": notice_template.get("anomaly_template", ""),
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                    },
                    {
                        "signal": ActionSignal.RECOVERED,
                        "message_tmpl": notice_template.get("recovery_template", ""),
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                    },
                    {
                        "signal": ActionSignal.CLOSED,
                        "message_tmpl": notice_template.get("anomaly_template", ""),
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                    },
                ],
            },
        }
    except Exception:
        logger.exception("_build_notice failed: action=%s", action)
        # 返回默认空 notice
        return {
            "user_groups": [],
            "signal": [],
            "options": {"converge_config": {"need_biz_converge": True}},
            "config": {
                "notify_interval": 7200,
                "interval_notify_mode": "standard",
                "template": [],
            },
        }


def _build_webhook_actions(
    action: dict[str, Any],
) -> list[dict[str, Any]]:
    """从 UserGroup 构建 webhook_actions。

    Args:
        action: 旧格式的 action 配置

    Returns:
        新格式的 actions 列表（webhook 动作），失败时返回空列表
    """
    try:
        notice_group_ids = action.get("notice_group_ids", [])
        if not notice_group_ids:
            return []

        webhook_actions: list[dict[str, Any]] = []
        for group in UserGroup.objects.filter(id__in=notice_group_ids):
            if group.webhook_action_id:
                webhook_actions.append(
                    {
                        "config_id": group.webhook_action_id,
                        "signal": [
                            ActionSignal.ABNORMAL,
                            ActionSignal.NO_DATA,
                            ActionSignal.RECOVERED,
                            ActionSignal.CLOSED,
                        ],
                        "user_groups": notice_group_ids,
                        "options": {"converge_config": {"is_enabled": False}},
                    }
                )

        return webhook_actions
    except Exception:
        logger.exception("_build_webhook_actions failed: action=%s", action)
        return []


def _transform_detects_uptime(
    strategy_json: dict[str, Any],
    action_config: dict[str, Any],
) -> None:
    """为 detects 补充 uptime 配置。

    Args:
        strategy_json: 策略配置（会被原地修改）
        action_config: action 中的 config 字段
    """
    try:
        for detect in strategy_json.get("detects", []):
            trigger_config = detect.get("trigger_config", {})
            uptime = trigger_config.get("uptime", {})

            uptime["time_ranges"] = [
                {
                    "start": action_config.get("alarm_start_time", "00:00:00"),
                    "end": action_config.get("alarm_end_time", "23:59:59"),
                }
            ]

            if "calendars" not in uptime:
                uptime["calendars"] = []

            trigger_config["uptime"] = uptime
            detect["trigger_config"] = trigger_config
    except Exception:
        logger.exception(
            "_transform_detects_uptime failed: strategy_id=%s",
            strategy_json.get("id"),
        )


def save_alarm_strategy_v2(
    bk_biz_id: int,
    strategy_json: dict[str, Any],
    operator: str,
    *,
    aiops_access_func: Callable[[int], str] | None = None,
    apply_converters: bool = True,
) -> dict[str, Any]:
    """创建或更新策略（兼容旧 API 格式）。

    该方法接收旧 API 格式的 strategy_json，先进行格式转换，再调用 save_strategy 保存。

    Args:
        bk_biz_id: 业务 ID
        strategy_json: 旧 API 格式的策略 JSON
        operator: 操作人
        aiops_access_func: 智能检测接入函数（可选）
        apply_converters: 是否在保存前 convert

    Returns:
        dict[str, Any]: 保存后的策略 ID，例如 {"id": 1}
    """
    # 转换旧 API 格式为新格式
    transformed_json = transform_strategy_json(strategy_json)

    # 调用 save_strategy 保存
    strategy = save_strategy(
        bk_biz_id=bk_biz_id,
        strategy_json=transformed_json,
        operator=operator,
        aiops_access_func=aiops_access_func,
        apply_converters=apply_converters,
    )
    strategy_id = strategy["id"]
    strategy_detail = get_strategy(bk_biz_id, strategy_id)
    return strategy_detail
