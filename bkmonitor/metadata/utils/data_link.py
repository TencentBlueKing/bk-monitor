"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("metadata")


def get_record_rule_metrics_by_biz_id(bk_biz_id: int | None, bk_tenant_id: str, with_option: bool = True):
    from metadata.models import (
        RecordRule,
        RecordRuleV4,
        ResultTable,
        ResultTableField,
        ResultTableFieldOption,
        ResultTableOption,
        Space,
    )

    # 普通业务和负数空间 ID 都必须在指定租户下解析，不能仅凭 space_id 匹配。
    filters = {"bk_tenant_id": bk_tenant_id}
    if bk_biz_id is not None:
        spaces = Space.objects.filter(bk_tenant_id=bk_tenant_id)
        if bk_biz_id < 0:
            space = spaces.filter(id=abs(bk_biz_id)).first()
        else:
            space = spaces.filter(space_type_id="bkcc", space_id=str(bk_biz_id)).first()
        if space is None:
            return []
        filters.update(space_type=space.space_type_id, space_id=space.space_id)

    result_table_id_list = list(
        set(RecordRule.objects.filter(**filters).values_list("table_id", flat=True))
        | set(
            RecordRuleV4.objects.filter(**filters, is_deleted=False, deleted_at__isnull=True)
            .exclude(desired_status="deleted")
            .values_list("table_id", flat=True)
        )
    )

    # 1. 查询所有依赖的内容
    # rt
    result_table_list = [
        result_table.to_json_self_only()
        for result_table in ResultTable.objects.filter(
            table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id, is_deleted=False
        )
    ]

    # 字段
    field_dict = {}
    for field in ResultTableField.objects.filter(table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id):
        try:
            field_dict[field.table_id].append(field.to_json_self_only())
        except KeyError:
            logger.error(
                "get_record_rule_metrics_by_biz_id: field_dict error, table_id->[%s],field_name->[%s]",
                field.table_id,
                field.field_name,
            )
            field_dict[field.table_id] = [field.to_json_self_only()]

    field_option_dict = {}
    rt_option_dict = {}
    storage_dict = {}
    if with_option:
        # 字段option
        field_option_dict = ResultTableFieldOption.batch_field_option(
            table_id_list=result_table_id_list, bk_tenant_id=bk_tenant_id
        )
        # RT的option
        rt_option_dict = ResultTableOption.batch_result_table_option(
            table_id_list=result_table_id_list, bk_tenant_id=bk_tenant_id
        )

        # 存储的组合
        storage_dict = {table_id: [] for table_id in result_table_id_list}

        for storage_name, storage_class in list(ResultTable.REAL_STORAGE_DICT.items()):
            for storage_info in storage_class.objects.filter(
                table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id
            ):
                storage_dict[storage_info.table_id].append(storage_name)

    # 2. 组合
    for result_table_info in result_table_list:
        result_table_name = result_table_info["table_id"]

        # 预计算输出没有 DataSourceResultTable，直接补齐指标缓存所需的数据源信息。
        result_table_info.update(
            table_type="recording_rule",
            source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            type_label=DataTypeLabel.TIME_SERIES,
        )

        # 追加字段名的内容，如果不存在，提供空数组
        result_table_info["field_list"] = field_dict.get(result_table_name, [])

        if with_option:
            for field_info in result_table_info["field_list"]:
                field_info["option"] = field_option_dict.get(result_table_name, {}).get(field_info["field_name"], {})

            # 追加结果表的option
            result_table_info["option"] = rt_option_dict.get(result_table_name, {})
            # 追加存储信息
            result_table_info["storage_list"] = storage_dict[result_table_name]

    return result_table_list
