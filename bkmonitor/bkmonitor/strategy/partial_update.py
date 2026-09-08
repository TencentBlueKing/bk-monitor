"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.models import (
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyLabel,
    StrategyModel,
)
from bkmonitor.strategy.new_strategy import (
    ISSUE_CONFIG_EMPTY,
    QUERY_OUTPUT_CONFIG_EMPTY,
    Algorithm,
    Detect,
    Item,
    QueryConfig,
    Strategy,
)
from constants.strategy import CUSTOM_PRIORITY_GROUP_PREFIX


class StrictSerializer(serializers.Serializer):
    """拒绝未声明字段，避免调用方通过 patch 越权修改策略配置。"""

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError(_("期望输入为对象"))

        unknown_fields: set[str] = set(data) - set(self.fields)
        if unknown_fields:
            raise ValidationError({field: [_("不支持的策略配置字段")] for field in sorted(unknown_fields)})

        return super().to_internal_value(data)


class ItemPatchSerializer(StrictSerializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False)
    expression = serializers.CharField(required=False, allow_blank=True)
    functions = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)
    metric_type = serializers.CharField(
        required=False, allow_blank=True, max_length=ItemModel._meta.get_field("metric_type").max_length
    )
    query_configs = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=False)
    algorithms = Algorithm.Serializer(many=True, required=False)


class NoticePatchSerializer(StrictSerializer):
    user_groups = serializers.ListField(required=False, child=serializers.IntegerField(), allow_empty=True)


class StrategyConfigPatchSerializer(StrictSerializer):
    name = serializers.CharField(required=False, max_length=StrategyModel._meta.get_field("name").max_length)
    scenario = serializers.CharField(required=False, max_length=StrategyModel._meta.get_field("scenario").max_length)
    items = ItemPatchSerializer(many=True, required=False)
    detects = Detect.Serializer(many=True, required=False)
    notice = NoticePatchSerializer(required=False)
    labels = serializers.ListField(required=False, child=serializers.CharField(), allow_empty=True)
    expected_labels = serializers.ListField(required=False, child=serializers.CharField(), allow_empty=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "expected_labels" in attrs and "labels" not in attrs:
            raise ValidationError(_("expected_labels 必须与 labels 同时传入"))
        return attrs


@dataclass(slots=True)
class ItemPatchChange:
    item: Item
    fields: set[str] = field(default_factory=set)
    query_configs: bool = False
    algorithms: bool = False


@dataclass(slots=True)
class StrategyConfigPatch:
    current: Strategy
    candidate: Strategy
    strategy_fields: set[str] = field(default_factory=set)
    item_changes: dict[int, ItemPatchChange] = field(default_factory=dict)
    detects: bool = False
    notice: bool = False
    labels: bool = False
    priority_group_key: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.strategy_fields or self.item_changes or self.detects or self.notice or self.labels)

    @classmethod
    def prepare(cls, current: Strategy, patch: dict[str, Any]) -> "StrategyConfigPatch":
        return StrategyConfigUpdater.prepare(current, patch)

    def save(self) -> None:
        StrategyConfigUpdater.save(self)


class StrategyConfigUpdater:
    """公共策略配置 patch 引擎，仅处理调用方显式开放的字段。

    调用方决定哪些字段属于本次更新，本层负责合并、规范化和组件保存，不依赖 APM 的模板规则。
    prepare 在 Resource 持锁期间读取的完整策略上生成保存计划；save 在同一事务中执行计划。
    查询和算法复用 Item 的保存方法，检测复用 Detect；主表和通知关系按字段写入。
    事务、外部校验及操作历史由 Resource 编排，避免各业务入口各自维护一套保存流程。
    """

    ITEM_FIELDS: tuple[str, ...] = ("name", "expression", "functions", "metric_type")

    @classmethod
    def prepare(cls, current: Strategy, patch: dict[str, Any]) -> StrategyConfigPatch:
        """合并 patch 并生成最小保存计划。"""

        serializer = StrategyConfigPatchSerializer(data=patch)
        serializer.is_valid(raise_exception=True)
        validated_patch: dict[str, Any] = serializer.validated_data
        # 调用方根据读取时的标签拼装完整列表。这里比对锁内快照，标签已变化就拒绝覆盖。
        if "expected_labels" in validated_patch:
            expected_labels: list[str] = sorted(label.strip("/") for label in validated_patch["expected_labels"])
            if expected_labels != sorted(label.strip("/") for label in current.labels):
                raise ValidationError(_("策略标签已变化，请刷新后重试"))

        # 比较和保存都按 ID 顺序匹配子配置，保证两阶段使用同一条存量记录。
        current.items.sort(key=lambda item: item.id)
        current.detects.sort(key=lambda detect: detect.id)
        for item in current.items:
            item.query_configs.sort(key=lambda config: config.id)
            item.algorithms.sort(key=lambda algorithm: algorithm.id)
        candidate: Strategy = copy.deepcopy(
            current,
            {
                id(ISSUE_CONFIG_EMPTY): ISSUE_CONFIG_EMPTY,
                id(QUERY_OUTPUT_CONFIG_EMPTY): QUERY_OUTPUT_CONFIG_EMPTY,
            },
        )
        cls._apply_strategy_patch(candidate, validated_patch)
        cls._apply_item_patches(candidate, validated_patch.get("items", []))
        cls._apply_detect_patches(candidate, validated_patch)
        cls._apply_notice_patch(candidate, validated_patch)
        cls._apply_label_patch(candidate, validated_patch)
        candidate.inherit_dynamic_alert_level_mode()
        query_item_patches: list[dict[str, Any]] = [
            item_patch for item_patch in validated_patch.get("items", []) if "query_configs" in item_patch
        ]
        if query_item_patches:
            candidate_items: dict[int, Item] = {item.id: item for item in candidate.items}
            for item_patch in query_item_patches:
                item: Item = cls._get_patch_item(candidate.items, candidate_items, item_patch)
                candidate.supplement_inst_target_dimension(items=[item])

        # 完整序列化器检查字段之间的约束，其默认值不用于回写。优先级分组键留到差异判断后按需计算。
        strategy_dict: dict[str, Any] = candidate.to_dict(convert_dashboard=False, generate_priority_group_key=False)
        # 数据库允许旧策略的这些字段为 null，校验视图使用空值，未传字段仍不参与保存。
        for field_name in ("app", "path", "priority_group_key"):
            if strategy_dict.get(field_name) is None:
                strategy_dict[field_name] = ""
        strategy_serializer = Strategy.Serializer(data=strategy_dict)
        strategy_serializer.is_valid(raise_exception=True)

        plan = StrategyConfigPatch(current=current, candidate=candidate)
        cls._fill_strategy_changes(plan, validated_patch)
        cls._fill_item_changes(plan, validated_patch)
        cls._fill_detect_changes(plan, validated_patch)
        cls._fill_notice_changes(plan, validated_patch)
        cls._fill_label_changes(plan, validated_patch)
        cls._fill_priority_group_key(plan)
        return plan

    @staticmethod
    def lock_related(strategy_id: int, patch: dict[str, Any]) -> None:
        """在外层事务内锁住本次 patch 可能读写的子配置。"""

        # 空 items / notice 不修改配置；空 labels 则表示清空，仍需锁定待删除记录。
        if patch.get("items"):
            list(ItemModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id"))
            list(QueryConfigModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id"))
            list(AlgorithmModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id"))
        if "detects" in patch:
            list(DetectModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id"))
        if patch.get("notice"):
            list(
                StrategyActionConfigRelation.objects.select_for_update()
                .filter(
                    strategy_id=strategy_id,
                    relate_type=StrategyActionConfigRelation.RelateType.NOTICE,
                )
                .order_by("id")
            )
        if "labels" in patch:
            list(StrategyLabel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id"))

    @classmethod
    def save(cls, plan: StrategyConfigPatch) -> None:
        """按计划保存实际变化的组件，元信息由 Resource 统一维护。"""

        candidate: Strategy = plan.candidate
        if plan.strategy_fields:
            update_fields: dict[str, Any] = {
                "name": candidate.name,
                "scenario": candidate.scenario,
                "priority_group_key": plan.priority_group_key,
            }
            update_fields = {field_name: update_fields[field_name] for field_name in plan.strategy_fields}
            StrategyModel.objects.filter(id=candidate.id, bk_biz_id=candidate.bk_biz_id).update(**update_fields)

        for change in plan.item_changes.values():
            cls._save_item(change)
            if change.query_configs:
                change.item.save_query_configs()
            if change.algorithms:
                change.item.save_algorithms()

        if plan.detects:
            cls._save_detects(candidate)
        if plan.notice:
            # 完整 notice 保存还会处理高级配置，这里只写通知组，保留用户维护的其他选项。
            StrategyActionConfigRelation.objects.filter(id=candidate.notice.id).update(
                user_groups=candidate.notice.user_groups
            )
        if plan.labels:
            cls._save_labels(candidate)

    @staticmethod
    def _apply_strategy_patch(candidate: Strategy, patch: dict[str, Any]) -> None:
        if "name" in patch:
            candidate.name = patch["name"]
        if "scenario" in patch:
            candidate.scenario = patch["scenario"]

    @classmethod
    def _apply_item_patches(cls, candidate: Strategy, item_patches: list[dict[str, Any]]) -> None:
        if not item_patches:
            return

        cls._validate_item_patch_identity(candidate.items, item_patches)
        current_items: dict[int, Item] = {item.id: item for item in candidate.items}
        for item_patch in item_patches:
            item: Item = cls._get_patch_item(candidate.items, current_items, item_patch)
            for field_name in cls.ITEM_FIELDS:
                if field_name in item_patch:
                    setattr(item, field_name, copy.deepcopy(item_patch[field_name]))
            if "name" in item_patch:
                item.name = Item.truncate_name(item.name)

            if "query_configs" in item_patch:
                item.query_configs = cls._build_query_configs(item, item_patch["query_configs"])
            if "algorithms" in item_patch:
                item.algorithms = cls._build_algorithms(item, item_patch["algorithms"])
            if isinstance(item.query_output_config, dict):
                item.validate_query_output_compatibility(item.query_output_config)

    @staticmethod
    def _validate_item_patch_identity(items: list[Item], item_patches: list[dict[str, Any]]) -> None:
        item_ids: list[int] = [patch["id"] for patch in item_patches if "id" in patch]
        if len(item_ids) != len(set(item_ids)):
            raise ValidationError(detail=_("监控项 ID 不能重复"))
        if any("id" not in patch for patch in item_patches) and (len(items) != 1 or len(item_patches) != 1):
            raise ValidationError(detail=_("省略监控项 ID 仅支持单监控项策略的单条 patch"))

    @staticmethod
    def _get_patch_item(items: list[Item], current_items: dict[int, Item], item_patch: dict[str, Any]) -> Item:
        if "id" not in item_patch:
            if len(items) != 1:
                raise ValidationError(detail=_("多监控项策略更新必须指定监控项 ID"))
            return items[0]

        item: Item | None = current_items.get(item_patch["id"])
        if item is None:
            raise ValidationError(detail=_("监控项不存在或不属于当前策略"))
        return item

    @staticmethod
    def _build_query_configs(item: Item, query_configs: list[dict[str, Any]]) -> list[QueryConfig]:
        current_configs: list[QueryConfig] = item.query_configs
        built_configs: list[QueryConfig] = []
        for index, config in enumerate(query_configs):
            try:
                query_config = QueryConfig(item.strategy_id, item.id, **copy.deepcopy(config))
            except (KeyError, TypeError) as error:
                raise ValidationError(detail=_("不支持的查询配置数据源类型")) from error
            # 查询集合整体替换时复用 ID，具体增删交给公共组件保存方法。
            query_config.id = current_configs[index].id if index < len(current_configs) else 0
            query_config._clean_empty_dimension()
            query_config.supplement_adv_condition_dimension(item)
            if not query_config.metric_id:
                query_config.metric_id = query_config.get_metric_id()
            built_configs.append(query_config)
        return built_configs

    @staticmethod
    def _build_algorithms(item: Item, algorithms: list[dict[str, Any]]) -> list[Algorithm]:
        current_algorithms: list[Algorithm] = item.algorithms
        built_algorithms: list[Algorithm] = []
        for index, config in enumerate(algorithms):
            algorithm = Algorithm(item.strategy_id, item.id, **copy.deepcopy(config))
            if index < len(current_algorithms):
                algorithm.id = current_algorithms[index].id
                if current_algorithms[index].instance is not None:
                    algorithm.config = algorithm._merge_with_db_config(current_algorithms[index].instance)
            built_algorithms.append(algorithm)
        return built_algorithms

    @staticmethod
    def _apply_detect_patches(candidate: Strategy, patch: dict[str, Any]) -> None:
        if "detects" not in patch:
            return

        current_detects: list[Detect] = candidate.detects
        detects: list[Detect] = []
        for index, config in enumerate(patch["detects"]):
            detect = Detect(candidate.id, **copy.deepcopy(config))
            detect.id = current_detects[index].id if index < len(current_detects) else 0
            detects.append(detect)
        candidate.detects = detects

    @staticmethod
    def _apply_notice_patch(candidate: Strategy, patch: dict[str, Any]) -> None:
        if "notice" in patch and "user_groups" in patch["notice"]:
            candidate.notice.user_groups = list(patch["notice"]["user_groups"])

    @staticmethod
    def _apply_label_patch(candidate: Strategy, patch: dict[str, Any]) -> None:
        if "labels" in patch:
            # 候选标签只规范化一次，差异比较和保存直接使用最终结果。
            candidate.labels = sorted(set(Strategy.normalize_labels(patch["labels"])))

    @staticmethod
    def _fill_strategy_changes(plan: StrategyConfigPatch, patch: dict[str, Any]) -> None:
        for field_name in ("name", "scenario"):
            if field_name in patch and getattr(plan.current, field_name) != getattr(plan.candidate, field_name):
                plan.strategy_fields.add(field_name)

    @classmethod
    def _fill_item_changes(cls, plan: StrategyConfigPatch, patch: dict[str, Any]) -> None:
        item_patches: list[dict[str, Any]] = patch.get("items", [])
        if not item_patches:
            return

        current_items: dict[int, Item] = {item.id: item for item in plan.current.items}
        candidate_items: dict[int, Item] = {item.id: item for item in plan.candidate.items}
        for item_patch in item_patches:
            current_item: Item = cls._get_patch_item(plan.current.items, current_items, item_patch)
            candidate_item: Item = cls._get_patch_item(plan.candidate.items, candidate_items, item_patch)
            change = ItemPatchChange(item=candidate_item)
            for field_name in cls.ITEM_FIELDS:
                if field_name in item_patch and getattr(current_item, field_name) != getattr(
                    candidate_item, field_name
                ):
                    change.fields.add(field_name)
            # 查询配置保留顺序语义；算法和检测配置按无序集合比较，数据库 ID 不参与内容比较。
            if "query_configs" in item_patch and (
                [cls._without_id(config.to_dict()) for config in current_item.query_configs]
            ) != ([cls._without_id(config.to_dict()) for config in candidate_item.query_configs]):
                change.query_configs = True
            if "algorithms" in item_patch and cls._normalize_collection(
                [cls._without_id(config.to_dict()) for config in current_item.algorithms]
            ) != cls._normalize_collection([cls._without_id(config.to_dict()) for config in candidate_item.algorithms]):
                change.algorithms = True

            if change.fields or change.query_configs or change.algorithms:
                plan.item_changes[candidate_item.id] = change

    @classmethod
    def _fill_detect_changes(cls, plan: StrategyConfigPatch, patch: dict[str, Any]) -> None:
        if "detects" not in patch:
            return

        if cls._normalize_collection(
            [cls._without_id(config.to_dict()) for config in plan.current.detects]
        ) != cls._normalize_collection([cls._without_id(config.to_dict()) for config in plan.candidate.detects]):
            plan.detects = True

    @staticmethod
    def _fill_notice_changes(plan: StrategyConfigPatch, patch: dict[str, Any]) -> None:
        if "notice" in patch and "user_groups" in patch["notice"]:
            plan.notice = plan.current.notice.user_groups != plan.candidate.notice.user_groups

    @staticmethod
    def _fill_label_changes(plan: StrategyConfigPatch, patch: dict[str, Any]) -> None:
        if "labels" not in patch:
            return

        current_labels: list[str] = [f"/{label.strip('/')}/" for label in plan.current.labels]
        # 当前标签保留重复项参与比较，确保存量重复记录也能触发清理。
        plan.labels = sorted(current_labels) != plan.candidate.labels

    @classmethod
    def _fill_priority_group_key(cls, plan: StrategyConfigPatch) -> None:
        current_key: str = plan.current.priority_group_key or ""
        plan.priority_group_key = current_key
        if plan.current.priority is None:
            return
        if current_key.startswith(CUSTOM_PRIORITY_GROUP_PREFIX):
            return
        if not cls._priority_inputs_changed(plan):
            return

        plan.priority_group_key = Strategy.get_priority_group_key(
            plan.candidate.bk_biz_id, plan.candidate.items, current_key
        )
        if plan.priority_group_key != current_key:
            plan.strategy_fields.add("priority_group_key")

    @staticmethod
    def _priority_inputs_changed(plan: StrategyConfigPatch) -> bool:
        for change in plan.item_changes.values():
            if change.query_configs or {"expression", "functions"} & change.fields:
                return True
        return False

    @staticmethod
    def _save_item(change: ItemPatchChange) -> None:
        if not change.fields:
            return

        item: Item = change.item
        update_fields: dict[str, Any] = {
            field_name: copy.deepcopy(getattr(item, field_name)) for field_name in change.fields
        }
        ItemModel.objects.filter(id=item.id, strategy_id=item.strategy_id).update(**update_fields)

    @staticmethod
    def _save_detects(strategy: Strategy) -> None:
        Strategy.reuse_exists_records(
            DetectModel,
            DetectModel.objects.filter(strategy_id=strategy.id).only("id").order_by("id"),
            strategy.detects,
            Detect,
        )
        for detect in strategy.detects:
            detect.save()

    @staticmethod
    def _save_labels(strategy: Strategy) -> None:
        desired_labels: set[str] = set(strategy.labels)
        current_labels: list[StrategyLabel] = list(
            StrategyLabel.objects.filter(bk_biz_id=strategy.bk_biz_id, strategy_id=strategy.id).order_by("id")
        )
        current_label_map: dict[str, list[int]] = {}
        for label in current_labels:
            current_label_map.setdefault(label.label_name, []).append(label.id)

        delete_ids: list[int] = []
        for label_name, label_ids in current_label_map.items():
            if label_name not in desired_labels:
                delete_ids.extend(label_ids)
            else:
                # 同名标签按 ID 保留首条，清理其余重复记录，避免重建仍有效的标签行。
                delete_ids.extend(label_ids[1:])
        if delete_ids:
            StrategyLabel.objects.filter(id__in=delete_ids).delete()

        existing_labels: set[str] = set(current_label_map)
        StrategyLabel.objects.bulk_create(
            [
                StrategyLabel(label_name=label, strategy_id=strategy.id, bk_biz_id=strategy.bk_biz_id)
                for label in sorted(desired_labels - existing_labels)
            ]
        )

    @staticmethod
    def _without_id(config: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {key: value for key, value in config.items() if key != "id"}
        if "agg_dimension" in normalized:
            normalized["agg_dimension"] = sorted(normalized["agg_dimension"])
        return normalized

    @staticmethod
    def _normalize_collection(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(configs, key=lambda config: json.dumps(config, ensure_ascii=False, sort_keys=True))
