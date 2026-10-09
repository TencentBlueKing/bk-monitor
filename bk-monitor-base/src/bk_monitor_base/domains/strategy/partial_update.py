"""strategy 域：策略局部更新（partial update）。

目标：
- 提供一个集中封装的“局部字段更新”能力，供 application 层调用。
- 支持的字段与参数格式对齐 bkmonitor 的 `UpdatePartialStrategyV2Resource`（仅关注字段集合与数据格式）。

设计边界（刻意保持简单）：
- **不引入新的 DRF Serializer**：仅用 TypedDict 描述入参结构，运行时做必要的类型检查。
- **按模型分组落库**：尽量通过 bulk_update/bulk_create 提升效率；对 actions/algorithms 等复用既有领域保存逻辑。
- **通用更新独立步骤**：update_user/update_time、history、hash/snippet 与具体字段更新解耦。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict, cast, final

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from bk_monitor_base.domains.strategy.constants import ActionSignal, SDKDetectStatus
from bk_monitor_base.domains.strategy.models import (
    ActionConfig,
    DetectModel,
    ItemModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyModel,
)
from bk_monitor_base.domains.strategy.strategy import ActionRelation, Algorithm, NoticeRelation, Strategy

logger = logging.getLogger(__name__)


class LabelsEditData(TypedDict, total=False):
    """labels 局部更新参数。

    与 bkmonitor `UpdatePartialStrategyV2Resource` 对齐：
    - labels: 标签列表（不带前后斜杠也可以，落库会统一格式化）
    - append_keys: 若包含 "labels"，则进行追加（集合并）；否则替换
    """

    labels: list[str]
    append_keys: list[str]


Target = list[list[dict[str, Any]]]


class EditData(TypedDict, total=False):
    """partial update 的 edit_data 结构（与 bkmonitor 对齐）。"""

    is_enabled: bool
    notice_group_list: list[int]
    labels: LabelsEditData
    trigger_config: dict[str, Any]
    recovery_config: dict[str, Any]
    alarm_interval: int
    send_recovery_alarm: bool
    message_template: str
    no_data_config: dict[str, Any]
    notice: dict[str, Any]
    target: Target
    actions: list[dict[str, Any]]
    algorithms: list[dict[str, Any]]


@dataclass(slots=True)
class _BulkOp:
    cls: type
    keys: tuple[str, ...]
    objs: list[Any]


@final
class StrategyPartialUpdater:
    """策略局部更新执行器。"""

    SUPPORTED_FIELDS: set[str] = {
        "is_enabled",
        "notice_group_list",
        "labels",
        "trigger_config",
        "recovery_config",
        "alarm_interval",
        "send_recovery_alarm",
        "message_template",
        "no_data_config",
        "notice",
        "target",
        "actions",
        "algorithms",
    }

    def __init__(self, bk_biz_id: int, ids: list[int], edit_data: EditData):
        self.bk_biz_id: int = bk_biz_id
        self.ids: list[int] = ids
        self.edit_data: EditData = edit_data

        # 执行期上下文（在 execute 初始化）
        self._notice_relations: dict[int, list[StrategyActionConfigRelation]] = {}
        self._notice_action_configs: dict[int, ActionConfig] = {}
        self._updates: dict[tuple[type, tuple[str, ...]], _BulkOp] = {}
        self._creates: dict[type, list[Any]] = defaultdict(list)
        self._histories: list[StrategyHistoryModel] = []
        self._now: datetime = timezone.now()
        self._operator: str = ""

    @staticmethod
    def _update_dict_recursive(src: dict[str, Any], dst: dict[str, Any]) -> dict[str, Any]:
        """递归合并字典（dst 覆盖/补充到 src）。"""
        for key, value in dst.items():
            if key not in src:
                src[key] = value
                continue
            if isinstance(value, dict) and isinstance(src.get(key), dict):
                StrategyPartialUpdater._update_dict_recursive(
                    cast(dict[str, Any], src[key]),
                    cast(dict[str, Any], value),
                )
            else:
                src[key] = value
        return src

    @staticmethod
    def _get_notice_relations(
        strategy_ids: list[int],
    ) -> tuple[list[int], dict[int, list[StrategyActionConfigRelation]]]:
        """批量获取 NOTICE 关系与对应的 ActionConfig IDs。"""
        action_config_ids: set[int] = set()
        relations: dict[int, list[StrategyActionConfigRelation]] = defaultdict(list)
        qs = StrategyActionConfigRelation.objects.filter(
            strategy_id__in=strategy_ids,
            relate_type=StrategyActionConfigRelation.RelateType.NOTICE,
        )
        for rel in qs:
            relations[rel.strategy_id].append(rel)
            action_config_ids.add(int(rel.config_id))
        return list(action_config_ids), relations

    @staticmethod
    def _get_action_configs(action_config_ids: list[int]) -> dict[int, ActionConfig]:
        """批量获取 ActionConfig 映射。"""
        if not action_config_ids:
            return {}
        qs = ActionConfig.objects.filter(id__in=action_config_ids)
        return {int(obj.pk): obj for obj in qs}

    @staticmethod
    def _merge_append_keys(old: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        """对 notice 的 append_keys 语义做兼容处理（与 bkmonitor 对齐）。"""
        new_data = deepcopy(incoming)
        append_keys = new_data.get("append_keys")
        if isinstance(append_keys, list):
            for key in cast(list[str], append_keys):
                if key not in new_data:
                    continue
                if isinstance(new_data.get(key), list) and isinstance(old.get(key), list):
                    for v in old.get(key, []):
                        if v not in new_data[key]:
                            new_data[key].append(v)
            new_data.pop("append_keys", None)
        StrategyPartialUpdater._update_dict_recursive(old, new_data)
        return old

    def execute(self, operator: str) -> list[int]:
        """执行局部更新并返回实际更新的策略 ID 列表。"""
        if not operator:
            raise ValidationError("operator is required")

        strategy_models = list(StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, id__in=self.ids))
        if not strategy_models:
            return []
        strategy_ids = [int(s.pk) for s in strategy_models]

        self._init_context(strategy_ids, operator)

        with transaction.atomic():
            for strategy in Strategy.from_models(strategy_models):
                strategy_model = cast(StrategyModel, strategy.instance)
                assert strategy_model is not None

                edit = self.edit_data

                self._apply_base_fields(strategy_model, strategy, edit)
                self._apply_notice_fields(strategy, edit)
                self._apply_actions(strategy, edit)
                self._apply_algorithms(strategy, edit)
                self._apply_common_updates(strategy_model, strategy, edit)

            # 批量更新已收集的模型变更
            for op in self._updates.values():
                if not op.objs:
                    continue
                op.cls.objects.bulk_update(op.objs, list(op.keys))

            # 批量创建新增记录
            for cls, objs in self._creates.items():
                if not objs:
                    continue
                cls.objects.bulk_create(objs)

            # 写入策略历史记录
            if self._histories:
                StrategyHistoryModel.objects.bulk_create(self._histories, batch_size=100)

            # 重置 AsCode 字段
            StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, id__in=strategy_ids).update(hash="", snippet="")

        return strategy_ids

    def _init_context(self, strategy_ids: list[int], operator: str) -> None:
        """初始化执行期上下文（关系缓存、批量写入容器、时间与操作人）"""
        notice_action_config_ids, notice_relations = self._get_notice_relations(strategy_ids)
        self._notice_relations = notice_relations
        self._notice_action_configs = self._get_action_configs(notice_action_config_ids)
        self._updates = {}
        self._creates = defaultdict(list)
        self._histories = []
        self._now = timezone.now()
        self._operator = operator

    def _add_update(self, cls: type, keys: list[str], objs: list[Any]) -> None:
        """收集 bulk_update 的变更集合（按模型与字段分组）"""
        if not objs:
            return
        key_tuple = tuple(keys)
        op_key = (cls, key_tuple)
        if op_key not in self._updates:
            self._updates[op_key] = _BulkOp(cls=cls, keys=key_tuple, objs=[])
        self._updates[op_key].objs.extend(objs)

    def _merge_bulk_datas(self, datas: dict[str, list[dict[str, Any]]]) -> None:
        """合并 bulk_save 返回的 create/update 数据"""
        for item in datas.get("update_data", []):
            self._add_update(item["cls"], cast(list[str], item["keys"]), cast(list[Any], item["objs"]))
        for item in datas.get("create_data", []):
            self._creates[item["cls"]].extend(cast(list[Any], item["objs"]))

    def _apply_base_fields(self, strategy_model: StrategyModel, strategy: Strategy, edit: EditData) -> None:
        """处理主表/检测/监控项/标签等基础字段更新"""
        if "is_enabled" in edit:
            strategy_model.is_enabled = bool(edit["is_enabled"])

        if "trigger_config" in edit:
            trigger_patch = edit["trigger_config"]
            for detect in strategy.detects:
                detect_model = cast(DetectModel, detect.instance)
                assert detect_model is not None
                detect_model.trigger_config.update(trigger_patch)
        if "recovery_config" in edit:
            recovery_cfg = edit["recovery_config"]
            for detect in strategy.detects:
                detect_model = cast(DetectModel, detect.instance)
                assert detect_model is not None
                detect_model.recovery_config = recovery_cfg

        if "target" in edit:
            target = edit["target"]
            # target 为空或首个 value 为空时视为清空
            if not target or not target[0] or not target[0][0].get("value"):
                target = []
            for item in strategy.items:
                item_model = cast(ItemModel, item.instance)
                assert item_model is not None
                item_model.target = target
        if "no_data_config" in edit:
            patch = edit["no_data_config"]
            for item in strategy.items:
                item_model = cast(ItemModel, item.instance)
                assert item_model is not None
                self._update_dict_recursive(item_model.no_data_config, patch)

        if "labels" in edit:
            labels_data = edit["labels"]
            old_labels = list(getattr(strategy, "labels", []) or [])
            new_labels = list(labels_data.get("labels", []) or [])
            append_keys = labels_data.get("append_keys") or []
            # append_keys 包含 labels 时走追加语义，否则替换
            if "labels" in append_keys:
                merged = list(set(old_labels) | set(new_labels))
            else:
                merged = new_labels
            strategy.labels = merged
            strategy.save_labels()

    def _apply_notice_fields(self, strategy: Strategy, edit: EditData) -> None:
        """处理通知相关字段更新，并同步 notice/actions 关联"""
        notice_changed = False
        action_relation_changed = False

        if "notice" in edit:
            old_notice = strategy.notice.to_dict()
            # notice 支持 append_keys 语义，需要基于旧配置做合并
            merged = self._merge_append_keys(old_notice, edit["notice"])
            strategy.notice = NoticeRelation(strategy.id, **merged)
            notice_changed = True

        if "notice_group_list" in edit:
            groups = edit["notice_group_list"]
            strategy.notice.user_groups = groups
            for action in strategy.actions:
                action.user_groups = groups
            notice_changed = True
            action_relation_changed = True

        if "alarm_interval" in edit:
            alarm_interval = int(edit["alarm_interval"])
            strategy.notice.config.setdefault("notify_interval", 0)
            strategy.notice.config["notify_interval"] = alarm_interval * 60
            notice_changed = True

        if "send_recovery_alarm" in edit:
            send_recovery_alarm = bool(edit["send_recovery_alarm"])
            if send_recovery_alarm and ActionSignal.RECOVERED not in strategy.notice.signal:
                strategy.notice.signal.append(ActionSignal.RECOVERED)
            if not send_recovery_alarm and ActionSignal.RECOVERED in strategy.notice.signal:
                strategy.notice.signal.remove(ActionSignal.RECOVERED)
            notice_changed = True

        if "message_template" in edit:
            message_template = edit["message_template"]
            templates_raw: Any = strategy.notice.config.get("template")
            templates_any: Any = templates_raw or []
            if isinstance(templates_any, list):
                templates = cast(list[dict[str, Any]], templates_any)
                for t in templates:
                    t["message_tmpl"] = message_template
            notice_changed = True

        if notice_changed:
            # notice 更新需要同步到 actions 的通知组与生效时间
            for action in strategy.actions:
                action.user_groups = strategy.notice.user_groups
                action.options.update(
                    {
                        "start_time": strategy.notice.options.get("start_time", "00:00:00"),
                        "end_time": strategy.notice.options.get("end_time", "23:59:59"),
                    }
                )
            action_relation_changed = True

            # 使用 bulk_save_notice 返回的数据进行批量落库
            extra = strategy.bulk_save_notice(
                self._notice_relations, self._notice_action_configs, operator=self._operator
            )
            self._merge_bulk_datas(extra)

        if action_relation_changed and "actions" not in edit:
            # 没有走 save_actions 时，需要手动批量同步关系表字段
            for action in strategy.actions:
                relation_model = cast(StrategyActionConfigRelation, action.instance)
                assert relation_model is not None
                relation_model.user_groups = action.user_groups
                relation_model.options = action.options
                relation_model.update_user = self._operator
                relation_model.update_time = self._now
            self._add_update(
                StrategyActionConfigRelation,
                ["user_groups", "options", "update_user", "update_time"],
                [a.instance for a in strategy.actions if a.instance is not None],
            )

    def _apply_actions(self, strategy: Strategy, edit: EditData) -> None:
        """处理 actions 全量替换更新"""
        if "actions" not in edit:
            return
        actions_payload = edit["actions"]
        new_actions: list[ActionRelation] = []
        for action_dict in actions_payload:
            slz = ActionRelation.Serializer(data=action_dict)
            slz.is_valid(raise_exception=True)
            action_data = cast(dict[str, Any], slz.validated_data)
            action_rel = ActionRelation(strategy.id, **action_data)
            action_rel.user_groups = strategy.notice.user_groups
            action_rel.options.update(
                {
                    "start_time": strategy.notice.options.get("start_time", "00:00:00"),
                    "end_time": strategy.notice.options.get("end_time", "23:59:59"),
                }
            )
            new_actions.append(action_rel)
        strategy.actions = new_actions
        strategy.save_actions()

    def _apply_algorithms(self, strategy: Strategy, edit: EditData) -> None:
        """处理 algorithms 覆盖更新"""
        if "algorithms" not in edit:
            return
        algorithms_payload = edit["algorithms"]
        for item in strategy.items:
            item.algorithms = [Algorithm(strategy.id, item.id, **data) for data in algorithms_payload]
            item.save_algorithms()

    def _apply_common_updates(self, strategy_model: StrategyModel, strategy: Strategy, edit: EditData) -> None:
        """处理通用更新（update_user/update_time/history/SDK 状态等）"""
        strategy_model.update_user = self._operator
        strategy_model.update_time = self._now
        self._add_update(StrategyModel, ["update_user", "update_time", "is_enabled"], [strategy_model])

        if "trigger_config" in edit or "recovery_config" in edit:
            self._add_update(
                DetectModel,
                ["trigger_config", "recovery_config"],
                [d.instance for d in strategy.detects if d.instance is not None],
            )
        if "target" in edit or "no_data_config" in edit:
            self._add_update(
                ItemModel,
                ["target", "no_data_config"],
                [i.instance for i in strategy.items if i.instance is not None],
            )

        if "is_enabled" in edit:
            # 智能检测使用 SDK 时需要重置状态触发重新拉取
            for item in strategy.items:
                if not item.query_configs:
                    continue
                qc = item.query_configs[0]
                intelligent_detect = getattr(qc, "intelligent_detect", None)
                if not intelligent_detect or not isinstance(intelligent_detect, dict):
                    continue
                if intelligent_detect.get("use_sdk", False):
                    intelligent_detect["status"] = SDKDetectStatus.PREPARING
                    qc.intelligent_detect = intelligent_detect
                    qc.save(item)

        self._histories.append(
            StrategyHistoryModel(
                create_user=self._operator,
                strategy_id=strategy.id,
                operate="update",
                content=strategy.to_dict(),
            )
        )
