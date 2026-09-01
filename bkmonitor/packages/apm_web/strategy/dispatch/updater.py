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
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apm_web.strategy.constants import APM_MANAGED_LABEL_PREFIXES
from bkmonitor.models import (
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
)
from bkmonitor.strategy.new_strategy import Algorithm, Detect, Item, QueryConfig, Strategy
from core.errors.strategy import CreateStrategyError
from monitor_web.strategies.resources.v2 import SaveStrategyV2Resource


class StrategyTemplateUpdater:
    """Only update fields owned by an APM strategy template."""

    @classmethod
    def update(cls, bk_biz_id: int, strategy_id: int, params: dict[str, Any]) -> int:
        candidate: Strategy = cls._build_candidate(strategy_id, params)
        SaveStrategyV2Resource.validate_realtime_kafka(candidate)
        SaveStrategyV2Resource.validate_cmdb_level(candidate)

        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            strategy: StrategyModel = StrategyModel.objects.select_for_update().get(bk_biz_id=bk_biz_id, id=strategy_id)
            items: list[ItemModel] = list(
                ItemModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id")
            )
            if len(items) != 1 or len(candidate.items) != 1:
                raise ValidationError(detail=_("策略模板仅支持更新单监控项策略"))

            notice_relations: list[StrategyActionConfigRelation] = list(
                StrategyActionConfigRelation.objects.select_for_update()
                .filter(
                    strategy_id=strategy_id,
                    relate_type=StrategyActionConfigRelation.RelateType.NOTICE,
                )
                .order_by("id")
            )
            if len(notice_relations) != 1:
                raise ValidationError(detail=_("策略模板更新要求策略存在唯一通知关系"))

            item: ItemModel = items[0]
            notice_relation: StrategyActionConfigRelation = notice_relations[0]
            query_configs: list[QueryConfigModel] = list(
                QueryConfigModel.objects.select_for_update()
                .filter(strategy_id=strategy_id, item_id=item.id)
                .order_by("id")
            )
            algorithms: list[AlgorithmModel] = list(
                AlgorithmModel.objects.select_for_update()
                .filter(strategy_id=strategy_id, item_id=item.id)
                .order_by("id")
            )
            detects: list[DetectModel] = list(
                DetectModel.objects.select_for_update().filter(strategy_id=strategy_id).order_by("id")
            )
            labels: list[StrategyLabel] = list(
                StrategyLabel.objects.select_for_update()
                .filter(bk_biz_id=bk_biz_id, strategy_id=strategy_id)
                .order_by("id")
            )

            cls._prepare_candidate(candidate, item, query_configs, algorithms, detects)
            candidate.notice.options = copy.deepcopy(notice_relation.options)
            SaveStrategyV2Resource.validate_upgrade_user_groups(candidate)

            current_projection: dict[str, Any] = cls._current_projection(
                strategy, item, query_configs, algorithms, detects, notice_relation, labels
            )
            candidate_projection: dict[str, Any] = cls._candidate_projection(candidate)
            if current_projection == candidate_projection:
                return strategy_id

            cls._validate_name(bk_biz_id, strategy_id, candidate.name)
            username: str = Strategy._get_username()
            now = timezone.now()
            StrategyModel.objects.filter(id=strategy_id, bk_biz_id=bk_biz_id).update(
                name=candidate.name,
                scenario=candidate.scenario,
                update_user=username,
                update_time=now,
                hash="",
                snippet="",
            )
            candidate_item: Item = candidate.items[0]
            ItemModel.objects.filter(id=item.id, strategy_id=strategy_id).update(
                name=candidate_item.name,
                expression=candidate_item.expression,
                functions=candidate_item.functions,
                metric_type=candidate_item.metric_type,
            )

            cls._save_query_configs(candidate_item, query_configs)
            cls._save_algorithms(candidate_item, algorithms)
            cls._save_detects(candidate.detects, detects)
            StrategyActionConfigRelation.objects.filter(id=notice_relation.id).update(
                user_groups=candidate.notice.user_groups
            )
            cls._save_labels(bk_biz_id, strategy_id, labels, candidate.labels)

            persisted_strategy: Strategy = Strategy.from_models(
                [StrategyModel.objects.get(id=strategy_id, bk_biz_id=bk_biz_id)]
            )[0]
            StrategyHistoryModel.objects.create(
                strategy_id=strategy_id,
                create_user=username,
                content=persisted_strategy.get_history_content(),
                operate="update",
                status=True,
            )

        return strategy_id

    @staticmethod
    def _build_candidate(strategy_id: int, params: dict[str, Any]) -> Strategy:
        serializer = Strategy.Serializer(data={**params, "id": strategy_id})
        serializer.is_valid(raise_exception=True)
        candidate = Strategy(**serializer.validated_data)
        candidate.convert()
        for item in candidate.items:
            item.metric_type = item.query_configs[0].data_type_label if item.query_configs else ""
        Strategy.Serializer.validate_dynamic_alert_level(candidate.to_dict())
        return candidate

    @classmethod
    def _prepare_candidate(
        cls,
        candidate: Strategy,
        item: ItemModel,
        query_configs: list[QueryConfigModel],
        algorithms: list[AlgorithmModel],
        detects: list[DetectModel],
    ) -> None:
        candidate.id = item.strategy_id
        candidate_item: Item = candidate.items[0]
        candidate_item.id = item.id
        candidate_item.name = Item.truncate_name(candidate_item.name)

        for query_config, current_query_config in zip(candidate_item.query_configs, query_configs):
            query_config.id = current_query_config.id
        for query_config in candidate_item.query_configs[len(query_configs) :]:
            query_config.id = 0
        for query_config in candidate_item.query_configs:
            query_config._clean_empty_dimension()
            query_config.supplement_adv_condition_dimension(candidate_item)
            query_config.to_dict()

        for algorithm, current_algorithm in zip(candidate_item.algorithms, algorithms):
            algorithm.id = current_algorithm.id
            algorithm.config = algorithm._merge_with_db_config(current_algorithm)
        for algorithm in candidate_item.algorithms[len(algorithms) :]:
            algorithm.id = 0

        for detect, current_detect in zip(candidate.detects, detects):
            detect.id = current_detect.id
        for detect in candidate.detects[len(detects) :]:
            detect.id = 0

    @classmethod
    def _current_projection(
        cls,
        strategy: StrategyModel,
        item: ItemModel,
        query_configs: list[QueryConfigModel],
        algorithms: list[AlgorithmModel],
        detects: list[DetectModel],
        notice_relation: StrategyActionConfigRelation,
        labels: list[StrategyLabel],
    ) -> dict[str, Any]:
        return {
            "strategy": {"name": strategy.name, "scenario": strategy.scenario},
            "item": {
                "name": item.name,
                "expression": item.expression,
                "functions": item.functions,
                "metric_type": item.metric_type,
                "query_configs": [cls._without_id(obj.to_dict()) for obj in QueryConfig.from_models(query_configs)],
                "algorithms": cls._normalize_unordered(
                    [cls._without_id(obj.to_dict()) for obj in Algorithm.from_models(algorithms)],
                    ("level", "type"),
                ),
            },
            "detects": cls._normalize_unordered(
                [cls._without_id(obj.to_dict()) for obj in Detect.from_models(detects)],
                ("level", "connector"),
            ),
            "notice": {"user_groups": notice_relation.user_groups},
            "labels": sorted(
                label.label_name.strip("/") for label in labels if cls._is_apm_managed_label(label.label_name)
            ),
        }

    @classmethod
    def _candidate_projection(cls, candidate: Strategy) -> dict[str, Any]:
        item: Item = candidate.items[0]
        return {
            "strategy": {"name": candidate.name, "scenario": candidate.scenario},
            "item": {
                "name": item.name,
                "expression": item.expression,
                "functions": item.functions,
                "metric_type": item.metric_type,
                "query_configs": [cls._without_id(obj.to_dict()) for obj in item.query_configs],
                "algorithms": cls._normalize_unordered(
                    [cls._without_id(obj.to_dict()) for obj in item.algorithms],
                    ("level", "type"),
                ),
            },
            "detects": cls._normalize_unordered(
                [cls._without_id(obj.to_dict()) for obj in candidate.detects],
                ("level", "connector"),
            ),
            "notice": {"user_groups": candidate.notice.user_groups},
            "labels": cls._normalize_apm_labels(candidate.labels),
        }

    @staticmethod
    def _without_id(config: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in config.items() if key != "id"}

    @staticmethod
    def _normalize_unordered(configs: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
        return sorted(
            configs,
            key=lambda config: (
                *(config.get(field) for field in key_fields),
                json.dumps(config, ensure_ascii=False, sort_keys=True),
            ),
        )

    @staticmethod
    def _is_apm_managed_label(label: str) -> bool:
        normalized_label = label.strip("/")
        return any(normalized_label.startswith(prefix) for prefix in APM_MANAGED_LABEL_PREFIXES)

    @classmethod
    def _normalize_apm_labels(cls, labels: list[str]) -> list[str]:
        normalized_labels: set[str] = set()
        for label in labels:
            normalized_label = label.strip("/")
            if not cls._is_apm_managed_label(normalized_label):
                continue
            wrapped_label = f"/{normalized_label}/"
            if len(wrapped_label) > StrategyLabel._meta.get_field("label_name").max_length:
                raise ValidationError(_("标签长度超长，请调整后重试"))
            normalized_labels.add(normalized_label)

        redundant_labels: set[str] = set()
        for label in normalized_labels:
            redundant_labels.update(
                other_label
                for other_label in normalized_labels
                if label != other_label and label.startswith(f"{other_label}/")
            )
        return sorted(normalized_labels - redundant_labels)

    @staticmethod
    def _validate_name(bk_biz_id: int, strategy_id: int, name: str) -> None:
        if StrategyModel.objects.filter(bk_biz_id=bk_biz_id, name=name).exclude(id=strategy_id).exists():
            raise CreateStrategyError(msg=_("策略名称({})不能重复").format(name))

    @staticmethod
    def _save_query_configs(item: Item, current_configs: list[QueryConfigModel]) -> None:
        extra_ids: list[int] = [obj.id for obj in current_configs[len(item.query_configs) :]]
        if extra_ids:
            QueryConfigModel.objects.filter(id__in=extra_ids).delete()
        for query_config in item.query_configs:
            query_config.save(item)

    @staticmethod
    def _save_algorithms(item: Item, current_algorithms: list[AlgorithmModel]) -> None:
        extra_ids: list[int] = [obj.id for obj in current_algorithms[len(item.algorithms) :]]
        if extra_ids:
            AlgorithmModel.objects.filter(id__in=extra_ids).delete()
        for algorithm in item.algorithms:
            algorithm.save()

    @staticmethod
    def _save_detects(detects: list[Detect], current_detects: list[DetectModel]) -> None:
        extra_ids: list[int] = [obj.id for obj in current_detects[len(detects) :]]
        if extra_ids:
            DetectModel.objects.filter(id__in=extra_ids).delete()
        for detect in detects:
            detect.save()

    @classmethod
    def _save_labels(
        cls,
        bk_biz_id: int,
        strategy_id: int,
        current_labels: list[StrategyLabel],
        candidate_labels: list[str],
    ) -> None:
        desired_labels: set[str] = {f"/{label}/" for label in cls._normalize_apm_labels(candidate_labels)}
        current_managed_labels: dict[str, list[int]] = {}
        for label in current_labels:
            if cls._is_apm_managed_label(label.label_name):
                current_managed_labels.setdefault(label.label_name, []).append(label.id)

        delete_ids: list[int] = []
        for label_name, label_ids in current_managed_labels.items():
            if label_name not in desired_labels:
                delete_ids.extend(label_ids)
            else:
                delete_ids.extend(label_ids[1:])
        if delete_ids:
            StrategyLabel.objects.filter(id__in=delete_ids).delete()

        existing_label_names: set[str] = set(current_managed_labels)
        StrategyLabel.objects.bulk_create(
            [
                StrategyLabel(label_name=label, strategy_id=strategy_id, bk_biz_id=bk_biz_id)
                for label in sorted(desired_labels - existing_label_names)
            ]
        )
