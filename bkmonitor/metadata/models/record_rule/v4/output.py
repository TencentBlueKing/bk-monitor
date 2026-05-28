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

from typing import TYPE_CHECKING

from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from metadata.models.data_link import utils as data_link_utils
from metadata.models.record_rule.constants import RECORD_RULE_V4_BKMONITOR_NAMESPACE
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

if TYPE_CHECKING:
    from metadata.models.record_rule.v4.models import RecordRuleV4, RecordRuleV4Spec


class RecordRuleV4OutputResources:
    """维护 V4 recording rule 输出侧 metadata。

    ResultTable / AccessVMRecord 是 group 级资源，应该在 RecordRuleV4 创建
    后立刻准备好；指标字段随着 spec 创建和变更按 metric_name 追加维护。
    """

    @classmethod
    def ensure_group_output(cls, rule: RecordRuleV4) -> bool:
        """创建 group 输出 RT、ResultTableConfig、RT option 及对应 VM 写入映射。

        返回值表示输出 ResultTable 是否首次创建，用于调用方决定是否刷新
        space -> table_id 路由。
        """

        result_table_created = cls.ensure_result_table(rule)
        cls.ensure_result_table_options(rule)
        cls.ensure_result_table_config(rule)
        vm_storage_name = cls.ensure_vm_record(rule)
        if rule.dst_vm_storage_name != vm_storage_name:
            rule.dst_vm_storage_name = vm_storage_name
            rule.save(update_fields=["dst_vm_storage_name", "updated_at"])
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
    def ensure_result_table_config(rule: RecordRuleV4) -> None:
        """创建输出 ResultTableConfig，供 bkbase Flow output 引用。"""

        from metadata import models as metadata_models

        result_table_config_name = RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
        metadata_models.ResultTableConfig.objects.update_or_create(
            bk_tenant_id=rule.bk_tenant_id,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=result_table_config_name,
            defaults={
                "table_id": rule.table_id,
                "bkbase_table_id": rule.dst_vm_table_id,
                "data_link_name": result_table_config_name,
                "bk_biz_id": rule.bk_biz_id,
            },
        )

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
