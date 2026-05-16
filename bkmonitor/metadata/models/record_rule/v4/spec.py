"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import copy
from typing import Any, cast

from django.db import transaction

from metadata.models.record_rule.v4.models import (
    RecordRuleV4,
    RecordRuleV4Spec,
    RecordRuleV4SpecRecord,
    generate_record_key,
    normalize_labels,
    stable_hash,
)
from metadata.models.record_rule.v4.types import RecordRuleV4RecordInput


class RecordRuleV4SpecBuilder:
    """负责创建用户声明快照，以及为组内 record 分配稳定 key。

    SpecBuilder 只处理用户输入层，不调用 unify-query，也不生成 Flow。
    """

    def __init__(self, rule: RecordRuleV4, source: str = "system", operator: str = "") -> None:
        self.rule = rule
        self.source = source
        self.operator = operator

    @property
    def actor(self) -> str:
        return self.operator or self.source

    def create_spec(
        self,
        *,
        records: list[RecordRuleV4RecordInput],
        raw_config: dict[str, Any],
        interval: str,
        desired_status: str,
        labels: list[dict[str, Any]] | None = None,
    ) -> RecordRuleV4Spec:
        """创建一份新的 spec 快照和对应的 spec records。

        raw_config 只记录调用方原始完整配置，便于审计和回显；它不参与
        spec 语义指纹。spec record 才是 resolver 消费的规范输入，
        避免同一层存在两份执行真值源。
        """

        RecordRuleV4.validate_desired_status(desired_status)
        RecordRuleV4.validate_interval(interval)
        group_labels = normalize_labels(labels)
        normalized_records = [self.normalize_record_payload(record) for record in records]
        generation = self.rule.generation + 1
        # spec content_hash 表达用户声明内容；resolved 漂移和 Flow 模板变化
        # 都不应该混入这一层。
        content_payload = {
            "records": [self.record_content_payload(record) for record in normalized_records],
            "interval": interval,
            "labels": group_labels,
            "desired_status": desired_status,
        }

        with transaction.atomic():
            spec = RecordRuleV4Spec.objects.create(
                rule=self.rule,
                generation=generation,
                raw_config=copy.deepcopy(raw_config),
                interval=interval,
                labels=copy.deepcopy(group_labels),
                desired_status=desired_status,
                content_hash=stable_hash(content_payload),
                source=self.source,
                operator=self.operator,
                creator=self.actor,
                updater=self.actor,
            )
            for source_index, record in enumerate(self.assign_record_keys(normalized_records)):
                RecordRuleV4SpecRecord.objects.create(
                    spec=spec,
                    source_index=source_index,
                    record_key=record["record_key"],
                    content_hash=record["content_hash"],
                    input_type=record["input_type"],
                    input_config=record["input_config"],
                    metric_name=record["metric_name"],
                    labels=record["labels"],
                    creator=self.actor,
                    updater=self.actor,
                )
        return spec

    def normalize_record_payload(self, record: RecordRuleV4RecordInput) -> dict[str, Any]:
        """归一化单条用户 record，并校验输入类型。"""

        record_payload = cast(dict[str, Any], copy.deepcopy(dict(record)))
        normalized = RecordRuleV4SpecRecord.normalize_record_payload(record_payload)
        RecordRuleV4.validate_input_type(normalized["input_type"])
        return normalized

    @staticmethod
    def record_content_payload(record: dict[str, Any]) -> dict[str, Any]:
        """返回参与单条 record 内容指纹计算的字段。"""

        return {
            "input_type": record["input_type"],
            "input_config": record["input_config"],
            "metric_name": record["metric_name"],
            "labels": record["labels"],
        }

    def assign_record_keys(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """为 records 分配稳定 record_key。

        API 模式可以显式传 record_key。隐藏 key 的模式无法提供业务侧稳定 ID，
        只能用启发式匹配上一版记录：先比较 input_config，再退回比较 metric_name。
        匹配不到时生成新的 record_key。
        """

        previous_records = []
        if self.rule.current_spec_id:
            previous_records = list(self.rule.current_spec.records.all())

        seen_keys: set[str] = set()
        result: list[dict[str, Any]] = []
        for record in records:
            explicit_key = record.get("record_key") or ""
            if explicit_key:
                record_key = explicit_key
            elif previous_record := self.match_previous_record(previous_records, seen_keys, record):
                record_key = previous_record.record_key
            else:
                record_key = generate_record_key()

            if record_key in seen_keys:
                raise ValueError(f"duplicate record_key in group: {record_key}")
            seen_keys.add(record_key)

            next_record = dict(record)
            next_record["record_key"] = record_key
            next_record["content_hash"] = stable_hash(self.record_content_payload(record))
            result.append(next_record)
        return result

    @staticmethod
    def match_previous_record(
        previous_records: list[RecordRuleV4SpecRecord],
        used_record_keys: set[str],
        record: dict[str, Any],
    ) -> RecordRuleV4SpecRecord | None:
        """为未显式传 key 的 record 匹配上一版记录。

        input_config 相等说明查询声明本身没有变化，优先继承该记录的 key；
        如果查询声明已经变化，再用 metric_name 做弱匹配。used_record_keys
        确保重复 metric_name 或重复 input_config 时不会复用同一个旧 key。
        """

        for previous_record in previous_records:
            if (
                previous_record.record_key not in used_record_keys
                and previous_record.input_config == record["input_config"]
            ):
                return previous_record

        for previous_record in previous_records:
            if (
                previous_record.record_key not in used_record_keys
                and previous_record.metric_name == record["metric_name"]
            ):
                return previous_record

        return None

    @staticmethod
    def dump_spec_records(spec: RecordRuleV4Spec) -> list[RecordRuleV4RecordInput]:
        """把已有 spec records 还原成 create_spec 可消费的输入结构。"""

        records: list[RecordRuleV4RecordInput] = []
        for record in spec.records.order_by("source_index", "id"):
            records.append(
                {
                    "record_key": record.record_key,
                    "input_type": record.input_type,
                    "input_config": copy.deepcopy(record.input_config),
                    "metric_name": record.metric_name,
                    "labels": copy.deepcopy(record.labels),
                }
            )
        return records
