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
import logging
from typing import Any, cast

from django.db import models, transaction

from core.drf_resource import api
from metadata.models.record_rule.constants import (
    RecordRuleV4DesiredStatus,
    RecordRuleV4InputType,
)
from metadata.models.record_rule.v4.models import (
    CONDITION_FALSE,
    CONDITION_RESOLVED,
    CONDITION_TRUE,
    CONDITION_UPDATE_AVAILABLE,
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Resolved,
    RecordRuleV4ResolvedRecord,
    RecordRuleV4Spec,
    RecordRuleV4SpecRecord,
    merge_labels,
    now,
    stable_hash,
)
from metadata.models.record_rule.v4.source import ResolvedVmResultTableConfig, resolve_vm_result_table_configs
from metadata.models.record_rule.v4.types import (
    CheckQueryPromQLInput,
    CheckQueryTsInput,
    RecordRuleV4QueryTsInputConfig,
    StructuredQueryConfigInput,
    StructuredQueryInput,
)

logger = logging.getLogger("metadata")


class RecordRuleV4Resolver:
    """将当前 spec 解析为 resolved 快照。

    Resolver 的职责边界是调用 unify-query check，并把 check 结果沉淀成
    Resolved / ResolvedRecord。是否生成 Flow、是否下发都不在这里处理。
    """

    def __init__(self, rule: RecordRuleV4, source: str = "system", operator: str = "") -> None:
        self.rule = rule
        self.source = source
        self.operator = operator

    @property
    def actor(self) -> str:
        return self.operator or self.source

    def reload_rule(self, for_update: bool = False) -> RecordRuleV4:
        """重新加载 rule，避免 resolve 长流程使用过期指针。"""

        queryset = RecordRuleV4.objects
        if for_update:
            queryset = queryset.select_for_update()
        self.rule = queryset.get(pk=self.rule.pk)
        return self.rule

    def resolve_current(self, force: bool = False) -> RecordRuleV4Resolved | None:
        """解析当前 spec，语义变化时创建新的 resolved 快照。"""

        self.reload_rule()
        spec = self.rule.current_spec
        if spec is None:
            self.rule.set_condition(CONDITION_RESOLVED, CONDITION_FALSE, "SpecMissing", "current spec is missing")
            self.rule.last_error = "current spec is missing"
            self.rule.sync_phase()
            self.rule.save()
            RecordRuleV4Event.record_resolve_failed(
                self.rule, source=self.source, operator=self.operator, message=self.rule.last_error
            )
            return None

        if spec.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            return None

        try:
            # 外部 check 可能耗时或失败，先在事务外完成，避免长时间持有行锁。
            runtime_records = [
                self.build_runtime_record(record) for record in spec.records.order_by("source_index", "id")
            ]
        except Exception as err:
            if not self.is_spec_current(spec):
                # 用户在 check 过程中更新了 spec，本次结果已经过期，直接丢弃。
                return None
            self.rule.last_error = str(err)
            self.rule.last_check_time = now()
            self.rule.set_condition(CONDITION_RESOLVED, CONDITION_FALSE, "ResolveFailed", str(err))
            self.rule.sync_phase()
            self.rule.save()
            RecordRuleV4Event.record_resolve_failed(
                self.rule,
                spec=spec,
                source=self.source,
                operator=self.operator,
                message=str(err),
            )
            logger.exception("RecordRuleV4 resolve failed, id: %s", self.rule.pk)
            return None

        if not self.is_spec_current(spec):
            return None

        # resolved content_hash 只包含解析语义结果，不包含后续 Flow 模板。
        resolved_config = {"records": [record["resolved_payload"] for record in runtime_records]}
        content_hash = stable_hash(resolved_config)

        with transaction.atomic():
            self.reload_rule(for_update=True)
            if self.rule.current_spec_id != spec.pk or self.rule.generation != spec.generation:
                return None

            latest_resolved = self.rule.latest_resolved
            if not force and latest_resolved and latest_resolved.content_hash == content_hash:
                # 解析语义未变时只更新时间和 condition，不推进 resolved 版本。
                self.rule.last_error = ""
                self.rule.last_check_time = now()
                if self.rule.applied_flow_id and self.rule.applied_flow_id == self.rule.latest_flow_id:
                    self.rule.observed_generation = max(self.rule.observed_generation, spec.generation)
                    self.rule.update_available = False
                    self.rule.set_condition(CONDITION_UPDATE_AVAILABLE, CONDITION_FALSE, "ResolvedUnchanged")
                self.rule.set_condition(CONDITION_RESOLVED, CONDITION_TRUE, "Unchanged")
                self.rule.sync_phase()
                self.rule.save()
                RecordRuleV4Event.record_resolve_unchanged(
                    self.rule,
                    spec,
                    latest_resolved,
                    source=self.source,
                    operator=self.operator,
                )
                return latest_resolved

            # 解析语义变化才创建新版本，用于后续生成部署计划。
            resolved = RecordRuleV4Resolved.objects.create(
                rule=self.rule,
                spec=spec,
                generation=spec.generation,
                resolve_version=self.next_resolve_version(spec),
                resolved_config=resolved_config,
                content_hash=content_hash,
                source=self.source,
                creator=self.actor,
                updater=self.actor,
            )
            for runtime_record in runtime_records:
                # resolved record 保留每条逻辑 record 的 metricql / VMRT 范围，
                # 后续部署策略只消费这一层结构。
                spec_record = runtime_record["spec_record"]
                RecordRuleV4ResolvedRecord.objects.create(
                    resolved=resolved,
                    spec_record=spec_record,
                    record_key=spec_record.record_key,
                    content_hash=runtime_record["content_hash"],
                    metricql=runtime_record["metricql"],
                    labels=runtime_record["labels"],
                    src_vm_table_ids=runtime_record["src_vm_table_ids"],
                    src_result_table_configs=runtime_record["src_result_table_configs"],
                    creator=self.actor,
                    updater=self.actor,
                )
            self.rule.use_resolved(resolved)
            RecordRuleV4Event.record_resolve_changed(
                self.rule,
                spec,
                resolved,
                source=self.source,
                operator=self.operator,
            )
            return resolved

    def is_spec_current(self, spec: RecordRuleV4Spec) -> bool:
        self.reload_rule()
        return self.rule.current_spec_id == spec.pk and self.rule.generation == spec.generation

    def build_runtime_record(self, spec_record: RecordRuleV4SpecRecord) -> dict[str, Any]:
        """将一条 spec record 解析成运行时 record payload。"""

        check_result = self.run_check(spec_record)
        data = check_result.get("data") or []
        if not data:
            raise ValueError(f"unify-query check data is empty, record_key: {spec_record.record_key}")

        self.validate_storage_type(data, spec_record.record_key)
        metricql = self.extract_metricql(data, spec_record.record_key)
        src_vm_table_ids = self.normalize_src_vm_table_ids(self.extract_src_vm_table_ids(data))
        if not src_vm_table_ids:
            raise ValueError(f"unify-query check src vm table ids is empty, record_key: {spec_record.record_key}")
        src_result_table_configs = self.resolve_src_result_table_configs(src_vm_table_ids)
        labels = merge_labels(spec_record.spec.labels, spec_record.labels)

        resolved_payload = {
            "record_key": spec_record.record_key,
            "metricql": metricql,
            "labels": labels,
            "interval": spec_record.spec.interval,
            "src_vm_table_ids": src_vm_table_ids,
            "src_result_table_configs": src_result_table_configs,
        }
        return {
            "spec_record": spec_record,
            "metricql": metricql,
            "labels": labels,
            "src_vm_table_ids": src_vm_table_ids,
            "src_result_table_configs": src_result_table_configs,
            "resolved_payload": resolved_payload,
            "content_hash": stable_hash(resolved_payload),
        }

    def run_check(self, spec_record: RecordRuleV4SpecRecord) -> dict[str, Any]:
        """根据输入类型调用 unify-query 的预览接口。"""

        if spec_record.input_type == RecordRuleV4InputType.QUERY_TS.value:
            params = self.build_check_query_ts_params(
                cast(RecordRuleV4QueryTsInputConfig, spec_record.input_config or {})
            )
            params.setdefault("space_uid", self.rule.space_uid)
            result = api.unify_query.check_query_ts(bk_tenant_id=self.rule.bk_tenant_id, **params)
        elif spec_record.input_type == RecordRuleV4InputType.PROMQL.value:
            params = self.build_check_promql_params(cast(CheckQueryPromQLInput, spec_record.input_config or {}))
            result = api.unify_query.check_query_ts_by_promql(bk_tenant_id=self.rule.bk_tenant_id, **params)
        else:
            raise ValueError(f"unsupported input_type: {spec_record.input_type}")
        return result or {}

    def build_check_promql_params(self, input_config: CheckQueryPromQLInput) -> CheckQueryPromQLInput:
        """补齐 /check/query/ts/promql 需要的最小参数。

        PromQL 表达式本身才是 record rule 的稳定输入；start/end 只用于
        unify-query check 接口完成解析预览，缺省时使用最近一小时。
        """

        params: CheckQueryPromQLInput = copy.deepcopy(input_config)
        if params.get("start") in (None, "") or params.get("end") in (None, ""):
            start, end = self.resolve_default_check_time_range_seconds()
            params["start"] = str(start)
            params["end"] = str(end)
        return params

    def build_check_query_ts_params(self, input_config: RecordRuleV4QueryTsInputConfig) -> CheckQueryTsInput:
        """把用户输入归一为 /check/query/ts 可消费的 QueryTs 参数。

        V4 预计算允许直接传 QueryTs，也允许传 SaaS 结构化查询配置。后者
        使用现有 UnifyQuery builder 生成结构化查询，避免在预计算模块里
        重新实现函数、聚合和条件的转换规则。
        """

        if "query_list" in input_config:
            params: CheckQueryTsInput = copy.deepcopy(cast(CheckQueryTsInput, input_config))
        elif "query_configs" in input_config:
            params = self.build_check_query_ts_params_from_structured_query(cast(StructuredQueryInput, input_config))
        else:
            params = copy.deepcopy(cast(CheckQueryTsInput, input_config))

        params.setdefault("space_uid", self.rule.space_uid)
        return params

    def build_check_query_ts_params_from_structured_query(
        self, input_config: StructuredQueryInput
    ) -> CheckQueryTsInput:
        """使用 UnifyQuery 将 SaaS 结构化查询转换为 QueryTs check 参数。"""

        from bkmonitor.data_source.data_source import load_data_source
        from bkmonitor.data_source.unify_query.query import UnifyQuery

        bk_biz_id = int(input_config.get("bk_biz_id") or self.rule.bk_biz_id)
        query_configs = self.normalize_structured_query_configs(input_config.get("query_configs") or [])
        if not query_configs:
            raise ValueError("structured query input_config requires query_configs")
        start_time, end_time = self.resolve_structured_query_check_time_range(input_config)

        # load_data_source + UnifyQuery 是 SaaS 查询配置到 QueryTs 的既有真值源；
        # resolver 只负责补齐 check 场景需要的时间和空间参数。
        data_sources = []
        for query_config in query_configs:
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_sources.append(
                data_source_class(
                    bk_biz_id=bk_biz_id,
                    use_full_index_names=True,
                    **query_config,
                )
            )

        unify_query = UnifyQuery(
            bk_biz_id=bk_biz_id,
            data_sources=data_sources,
            expression=input_config.get("expression") or "",
            functions=input_config.get("functions") or [],
            bk_tenant_id=self.rule.bk_tenant_id,
        )
        raw_params = unify_query.get_unify_query_params(
            start_time=start_time,
            end_time=end_time,
            time_alignment=False,
            order_by=input_config.get("order_by"),
        )
        raw_params.pop("bk_tenant_id", None)
        params = cast(CheckQueryTsInput, raw_params)
        params["space_uid"] = self.rule.space_uid
        return params

    def resolve_structured_query_check_time_range(self, input_config: StructuredQueryInput) -> tuple[int, int]:
        """生成 check 接口需要的时间范围。

        recording rule 的最终 MetricQL 不应依赖用户查询窗口；这里保留用户
        显式传入的时间仅用于复现预览，缺省时统一使用最近一小时满足
        unify-query check 的请求格式。
        """

        start_time = input_config.get("start_time")
        end_time = input_config.get("end_time")
        if start_time not in (None, "") and end_time not in (None, ""):
            return (
                self.normalize_timestamp_to_milliseconds(start_time),
                self.normalize_timestamp_to_milliseconds(end_time),
            )

        start, end = self.resolve_default_check_time_range_seconds()
        return start * 1000, end * 1000

    @staticmethod
    def resolve_default_check_time_range_seconds() -> tuple[int, int]:
        """返回默认 check 时间窗口，单位为秒。"""

        default_end_time = int(now().timestamp())
        return default_end_time - 3600, default_end_time

    def normalize_structured_query_configs(
        self, query_configs: list[StructuredQueryConfigInput]
    ) -> list[dict[str, Any]]:
        """归一化 SaaS query_configs，使其满足 DataSource 构造参数约定。

        返回值刻意使用普通 dict：TypedDict 描述的是 API 入参形态，
        DataSource 构造函数接收的是运行时 kwargs，两者不应该继续绑定，
        否则静态检查会在 **kwargs 展开时误报字段类型不兼容。
        """

        normalized_configs: list[dict[str, Any]] = []
        for query_config in query_configs:
            normalized: dict[str, Any] = dict(copy.deepcopy(query_config))
            interval_unit = normalized.get("interval_unit") or "s"
            normalized["interval"] = self.normalize_interval_to_seconds(
                normalized.get("interval"),
                str(interval_unit),
            )
            normalized_configs.append(normalized)
        return normalized_configs

    @staticmethod
    def normalize_interval_to_seconds(interval: Any, interval_unit: str) -> Any:
        """把结构化查询的 interval/interval_unit 转成 UnifyQuery 使用的秒。"""

        if interval in (None, ""):
            return interval
        try:
            interval_value = int(interval)
        except (TypeError, ValueError):
            return interval

        unit = interval_unit.lower()
        if unit in {"ms", "millisecond", "milliseconds"}:
            return max(interval_value // 1000, 1)
        if unit in {"m", "min", "minute", "minutes"}:
            return interval_value * 60
        if unit in {"h", "hour", "hours"}:
            return interval_value * 3600
        return interval_value

    @staticmethod
    def normalize_timestamp_to_milliseconds(value: Any) -> int:
        """UnifyQuery builder 接收毫秒时间戳；用户输入可能是秒或毫秒。"""

        timestamp = int(value)
        if timestamp > 10_000_000_000:
            return timestamp
        return timestamp * 1000

    def next_resolve_version(self, spec: RecordRuleV4Spec) -> int:
        """获取同一 spec 下的下一个解析版本号。"""

        latest = RecordRuleV4Resolved.objects.filter(rule=self.rule, spec=spec).order_by("-resolve_version").first()
        return 1 if latest is None else latest.resolve_version + 1

    @staticmethod
    def validate_storage_type(data: list[dict[str, Any]], record_key: str) -> None:
        """校验 check data 只包含 V4 recording rule 支持的 VM 查询体。"""

        unsupported_storage_types = sorted(
            {str(item.get("storage_type") or "") for item in data if item.get("storage_type") != "victoria_metrics"}
        )
        if unsupported_storage_types:
            raise ValueError(
                "unify-query check storage_type is not supported, "
                f"record_key: {record_key}, storage_type: {unsupported_storage_types}"
            )

    @staticmethod
    def extract_metricql(data: list[dict[str, Any]], record_key: str = "") -> str:
        """从 check data 中提取唯一 MetricQL。"""

        metricql: list[str] = []
        for item in data:
            value = item.get("metricql")
            if value and value not in metricql:
                metricql.append(value)
        if not metricql:
            raise ValueError(f"unify-query check metricql is empty, record_key: {record_key}")
        if len(metricql) > 1:
            raise ValueError(f"unify-query check got multiple metricql, record_key: {record_key}, metricql: {metricql}")
        return metricql[0]

    @staticmethod
    def extract_src_vm_table_ids(data: list[dict[str, Any]]) -> list[str]:
        """从 check data 中提取源 VM 结果表。"""

        table_ids: list[str] = []
        for item in data:
            result_table_id = item.get("result_table_id") or []
            if isinstance(result_table_id, str):
                result_table_id = [result_table_id]
            for table_id in result_table_id:
                if table_id and table_id not in table_ids:
                    table_ids.append(table_id)
        return table_ids

    def normalize_src_vm_table_ids(self, table_ids: list[str]) -> list[str]:
        """把源 RT 统一转换成 VM RT，并排除当前预计算自己的输出表。"""

        from metadata import models as metadata_models

        exclude_table_ids = {self.rule.table_id, self.rule.dst_vm_table_id}
        vm_records = metadata_models.AccessVMRecord.objects.filter(bk_tenant_id=self.rule.bk_tenant_id).filter(
            models.Q(vm_result_table_id__in=table_ids) | models.Q(result_table_id__in=table_ids)
        )
        vm_map: dict[str, str] = {}
        for record in vm_records:
            vm_map[record.vm_result_table_id] = record.vm_result_table_id
            vm_map[record.result_table_id] = record.vm_result_table_id

        result: list[str] = []
        missing: list[str] = []
        for table_id in table_ids:
            vm_table_id = vm_map.get(table_id)
            if not vm_table_id:
                missing.append(table_id)
                continue
            if table_id in exclude_table_ids or vm_table_id in exclude_table_ids:
                # 解析结果可能因为已有预计算链路而包含自身输出；这里必须跳过，
                # 否则会生成自引用的 VmSourceNode。
                logger.info(
                    "RecordRuleV4 normalize_src_vm_table_ids: skip self reference table_id->[%s], "
                    "vm_table_id->[%s], rule_table_id->[%s]",
                    table_id,
                    vm_table_id,
                    self.rule.table_id,
                )
                continue
            if vm_table_id not in result:
                result.append(vm_table_id)
        if missing:
            raise ValueError(f"source result tables are not access vm storage: {missing}")
        return result

    def resolve_src_result_table_configs(self, vm_table_ids: list[str]) -> list[ResolvedVmResultTableConfig]:
        """把源 VMRT 固化成 bkbase ResultTableConfig.name 快照。"""

        return resolve_vm_result_table_configs(
            bk_tenant_id=self.rule.bk_tenant_id,
            vm_result_table_ids=vm_table_ids,
        )
