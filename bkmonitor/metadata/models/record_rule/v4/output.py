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

import logging
from typing import TYPE_CHECKING, Any

from core.drf_resource import api
from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from metadata.models.data_link import utils as data_link_utils
from metadata.models.record_rule.constants import RECORD_RULE_V4_BKMONITOR_NAMESPACE
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

if TYPE_CHECKING:
    from metadata.models.record_rule.v4.models import RecordRuleV4, RecordRuleV4Spec

logger = logging.getLogger("metadata")


class RecordRuleV4OutputResources:
    """维护 V4 recording rule 输出侧 metadata。

    ResultTable / AccessVMRecord 是 group 级资源，应该在 RecordRuleV4 创建
    后立刻准备好；指标字段随着 spec 创建和变更按 metric_name 追加维护。

    output 资源和 Flow 是两类 bkbase 资源：output 必须先注册 ResultTable /
    VmStorageBinding，Flow 才能引用目标 VMRT。因此 ensure_group_output 保持
    “创建本地配置并 apply output”的语义，Flow apply 仍由 Runner 单独负责。
    """

    @classmethod
    def ensure_group_output(cls, rule: RecordRuleV4, *, force_apply: bool = False) -> bool:
        """创建 group 输出 RT、ResultTableConfig、RT option 及对应 VM 写入映射。

        返回值表示输出 ResultTable 是否首次创建，用于调用方决定是否刷新
        space -> table_id 路由。该方法会在必要时调用 bkbase apply_data_link
        下发 output 资源，但不会创建或下发 Flow；本地 output 配置已存在且未
        处于 FAILED 时跳过重复 apply，FAILED 会触发后台自动重试，管理员也可
        传 force_apply=True 强制重试。
        """

        result_table_created = cls.ensure_result_table(rule)
        cls.ensure_result_table_options(rule)
        # VMStorageBinding 依赖 VM 集群名，必须先确定 dst_vm_storage_name 再
        # 下发链路配置，否则 output 资源会引用一个空存储名。
        vm_storage_name = cls.ensure_vm_record(rule)
        if rule.dst_vm_storage_name != vm_storage_name:
            rule.dst_vm_storage_name = vm_storage_name
            rule.save(update_fields=["dst_vm_storage_name", "updated_at"])
        cls.ensure_result_table_config(rule, force_apply=force_apply)
        return result_table_created

    @staticmethod
    def compose_result_table_config_name(table_id: str) -> str:
        """按 DataLink 规则生成 bkbase ResultTable name。"""

        return data_link_utils.compose_bkdata_table_id(table_id)

    @staticmethod
    def compose_vm_result_table_id(bk_tenant_id: str, bk_biz_id: int, result_table_config_name: str) -> str:
        """根据 ResultTableConfig.name 生成真实 VMRT。"""

        data_link_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        return f"{data_link_biz_ids.data_biz_id}_{result_table_config_name}"

    @staticmethod
    def ensure_result_table(rule: RecordRuleV4) -> bool:
        """创建输出 ResultTable，供后续 Flow output 引用。"""

        from metadata import models as metadata_models

        biz_id = metadata_models.Space.objects.get_biz_id_by_space(rule.space_type, rule.space_id)
        table_name_zh = rule.name or rule.table_id
        defaults = {
            "table_name_zh": table_name_zh,
            "is_custom_table": True,
            "default_storage": metadata_models.ClusterInfo.TYPE_VM,
            "creator": "system",
            "bk_biz_id": biz_id,
        }
        if rule.data_label:
            defaults["data_label"] = rule.data_label
        result_table, created = metadata_models.ResultTable.objects.get_or_create(
            bk_tenant_id=rule.bk_tenant_id,
            table_id=rule.table_id,
            defaults=defaults,
        )
        if not created:
            update_fields: list[str] = []
            if result_table.table_name_zh != table_name_zh:
                result_table.table_name_zh = table_name_zh
                update_fields.append("table_name_zh")
            # data_label 为空时不主动清空已有 ResultTable，仅在用户显式配置有效值时刷新。
            if rule.data_label and result_table.data_label != rule.data_label:
                result_table.data_label = rule.data_label
                update_fields.append("data_label")
            if update_fields:
                update_fields.append("last_modify_time")
                result_table.save(update_fields=update_fields)
        return created

    @staticmethod
    def ensure_result_table_options(rule: RecordRuleV4) -> None:
        """补齐输出 RT 查询依赖的固定 option。"""

        from metadata import models as metadata_models

        option_data = {
            metadata_models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT: True,
            metadata_models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST: False,
        }
        for name, value in option_data.items():
            option_value, value_type = metadata_models.ResultTableOption._parse_value(value)
            metadata_models.ResultTableOption.objects.update_or_create(
                bk_tenant_id=rule.bk_tenant_id,
                table_id=rule.table_id,
                name=name,
                defaults={
                    "value": option_value,
                    "value_type": value_type,
                    "creator": "system",
                },
            )

    @staticmethod
    def ensure_result_table_config(rule: RecordRuleV4, *, force_apply: bool = False) -> None:
        """创建输出 ResultTableConfig + VMStorageBindingConfig 并下发到 bkbase。

        本地 ResultTableConfig 维护 ``table_id <-> bkbase_table_id`` 映射；
        VMStorageBindingConfig 把输出 RT 绑定到 VM 存储。两者一起下发后，bkbase
        侧才会注册独立 ResultTable / VmStorageBinding 资源，DataLink 详情页的
        ``component_config`` / ``status`` 也才会有值。Flow 仍单独下发，互不替代。

        recording rule 输出走 VM 存储，schema 固定，这里不显式下发字段；字段随
        Flow 的 RecordingRuleNode metric_name 在 bkbase 侧补齐。下发成功后把本地
        ``status`` 置为 ``Pending``，表示已提交、等待 bkbase 调度完成。当前不
        支持 output 配置变更自动重下发；只要本地两份配置都存在且未处于 FAILED，
        后台调谐就不重复 apply。任一配置处于 FAILED 时后台会自动重试下发，
        force_apply=True 则无条件强制重试。
        """

        from metadata import models as metadata_models
        from metadata.models.data_link.constants import DataLinkResourceStatus

        if not rule.dst_vm_storage_name:
            raise ValueError("record rule dst_vm_storage_name is empty")

        result_table_config_name = RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
        result_table_defaults = {
            "table_id": rule.table_id,
            "bkbase_table_id": rule.dst_vm_table_id,
            "data_link_name": result_table_config_name,
            "bk_biz_id": rule.bk_biz_id,
        }
        vm_binding_defaults = {
            "table_id": rule.table_id,
            "bkbase_result_table_name": result_table_config_name,
            "vm_cluster_name": rule.dst_vm_storage_name,
            "data_link_name": result_table_config_name,
            "bk_biz_id": rule.bk_biz_id,
        }
        result_table_config = metadata_models.ResultTableConfig.objects.filter(
            bk_tenant_id=rule.bk_tenant_id,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=result_table_config_name,
        ).first()
        vm_storage_binding = metadata_models.VMStorageBindingConfig.objects.filter(
            bk_tenant_id=rule.bk_tenant_id,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=result_table_config_name,
        ).first()
        output_config_exists = bool(result_table_config and vm_storage_binding)
        # 任一本地配置处于 FAILED 时说明上一次下发未成功，后台调谐应自动重试，
        # 避免 output 资源永久卡在失败态、只能靠人工 force_apply 才能恢复。
        output_apply_failed = any(
            config_instance is not None and config_instance.status == DataLinkResourceStatus.FAILED.value
            for config_instance in (result_table_config, vm_storage_binding)
        )
        should_apply = force_apply or not output_config_exists or output_apply_failed

        result_table_config, _ = metadata_models.ResultTableConfig.objects.update_or_create(
            bk_tenant_id=rule.bk_tenant_id,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=result_table_config_name,
            defaults=result_table_defaults,
        )
        # binding 与 RT 同名，绑定输出 RT 到 group 的目标 VM 存储。
        # Flow 中 RecordingRuleNode.output 引用的是 rule.dst_vm_table_id，
        # 这里的绑定负责让该 VMRT 在 bkbase 侧可写入。
        vm_storage_binding, _ = metadata_models.VMStorageBindingConfig.objects.update_or_create(
            bk_tenant_id=rule.bk_tenant_id,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=result_table_config_name,
            defaults=vm_binding_defaults,
        )

        if not should_apply:
            logger.info(
                "RecordRuleV4 ensure_result_table_config skip apply: rule_id->[%s], name->[%s], status->[%s/%s]",
                rule.pk,
                result_table_config.name,
                result_table_config.status,
                vm_storage_binding.status,
            )
            return

        configs: list[dict[str, Any]] = [result_table_config.compose_config(), vm_storage_binding.compose_config()]
        # output 资源先于 Flow 独立 apply；调用方即使 auto_apply=False，也会
        # 走到这里完成前置资源注册，只是不继续 apply Flow。重复执行时本地
        # 已存在的 output 配置会被上方短路，避免 scheduler 周期性空下发。
        try:
            response = api.bkdata.apply_data_link(  # pyright: ignore[reportCallIssue]
                bk_tenant_id=rule.bk_tenant_id, config=configs
            )
        except Exception:
            for config_instance in (result_table_config, vm_storage_binding):
                if config_instance.status != DataLinkResourceStatus.FAILED.value:
                    config_instance.status = DataLinkResourceStatus.FAILED.value
                    config_instance.save(update_fields=["status", "last_modify_time"])
            raise
        logger.info(
            "RecordRuleV4 ensure_result_table_config: rule_id->[%s], name->[%s], response->[%s]",
            rule.pk,
            result_table_config.name,
            response,
        )
        for config_instance in (result_table_config, vm_storage_binding):
            if config_instance.status != DataLinkResourceStatus.PENDING.value:
                config_instance.status = DataLinkResourceStatus.PENDING.value
                config_instance.save(update_fields=["status", "last_modify_time"])

    @staticmethod
    def ensure_vm_record(rule: RecordRuleV4) -> str:
        """创建输出 RT 到 VM RT 的映射。"""

        from metadata import models as metadata_models
        from metadata.models.vm import utils as vm_utils

        vm_cluster_info = vm_utils.get_vm_cluster_id_name(
            bk_tenant_id=rule.bk_tenant_id,
            space_type=rule.space_type,
            space_id=rule.space_id,
        )
        metadata_models.AccessVMRecord.objects.update_or_create(
            bk_tenant_id=rule.bk_tenant_id,
            result_table_id=rule.table_id,
            defaults={
                "bk_base_data_id": 0,
                "vm_result_table_id": rule.dst_vm_table_id,
                "vm_cluster_id": vm_cluster_info["cluster_id"],
            },
        )
        return str(vm_cluster_info["cluster_name"])

    @staticmethod
    def ensure_metric_fields(rule: RecordRuleV4, metric_names: list[str]) -> bool:
        """补齐输出指标字段；字段删除不在这里处理。

        返回值表示是否有新字段被创建。
        """

        from metadata import models as metadata_models

        has_created = False
        for metric_name in metric_names:
            _, created = metadata_models.ResultTableField.objects.get_or_create(
                bk_tenant_id=rule.bk_tenant_id,
                table_id=rule.table_id,
                field_name=metric_name,
                defaults={
                    "field_type": metadata_models.ResultTableField.FIELD_TYPE_FLOAT,
                    "description": metric_name,
                    "tag": metadata_models.ResultTableField.FIELD_TAG_METRIC,
                    "is_config_by_user": True,
                },
            )
            has_created = has_created or created
        return has_created

    @classmethod
    def ensure_spec_metric_fields(cls, rule: RecordRuleV4, spec: RecordRuleV4Spec) -> bool:
        """按 spec records 的 metric_name 补齐输出字段。

        路由刷新由 operator 在事务外统一触发，避免 Redis 看到未提交数据。
        """

        metric_names = list(spec.records.order_by("source_index", "id").values_list("metric_name", flat=True))
        return cls.ensure_metric_fields(rule, metric_names)

    @staticmethod
    def push_output_route(rule: RecordRuleV4) -> None:
        """首次创建输出表后刷新空间索引和结果表详情。"""

        redis_client = SpaceTableIDRedis()
        redis_client.push_space_table_ids(space_type=rule.space_type, space_id=rule.space_id, is_publish=True)
        redis_client.push_table_id_detail(
            table_id_list=[rule.table_id],
            is_publish=True,
            bk_tenant_id=rule.bk_tenant_id,
        )

    @staticmethod
    def push_table_id_detail(rule: RecordRuleV4) -> None:
        """输出指标字段变化后刷新结果表详情。"""

        SpaceTableIDRedis().push_table_id_detail(
            table_id_list=[rule.table_id],
            is_publish=True,
            bk_tenant_id=rule.bk_tenant_id,
        )
