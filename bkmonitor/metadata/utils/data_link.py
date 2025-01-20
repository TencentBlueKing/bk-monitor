# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

logger = logging.getLogger("metadata")


def get_record_rule_metrics_by_biz_id(bk_biz_id, with_option: bool = True):
    from metadata.models import (
        RecordRule,
        ResultTable,
        ResultTableField,
        ResultTableFieldOption,
        ResultTableOption,
        Space,
    )

    logger.info("get_record_rule_metrics_by_biz_id: try to get record rule metrics by bk_biz_id->[%s]", bk_biz_id)
    # 0. 根据bk_biz_id，获取该业务下的预计算结果表列表
    if bk_biz_id < 0:  # 业务ID为负数，表示非bkcc类型，需要转化
        logger.info(
            "get_record_rule_metrics_by_biz_id: bk_biz_id is negative, try to get space_id by bk_biz_id->[%s]",
            bk_biz_id,
        )
        space = Space.objects.get(id=abs(bk_biz_id))
        space_id = space.space_id
        logger.info("get_record_rule_metrics_by_biz_id: get space_id->[%s] by bk_biz_id->[%s]", space_id, bk_biz_id)
    else:
        space_id = bk_biz_id

    result_table_id_list = list(RecordRule.objects.filter(space_id=space_id).values_list('table_id', flat=True))
    logger.info("get_record_rule_metrics_by_biz_id: get result_table_id_list->[%s]", result_table_id_list)

    # 1. 查询所有依赖的内容
    # rt
    result_table_list = [
        result_table.to_json_self_only()
        for result_table in ResultTable.objects.filter(table_id__in=result_table_id_list)
    ]

    # 字段
    field_dict = {}
    for field in ResultTableField.objects.filter(table_id__in=result_table_id_list):
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
        field_option_dict = ResultTableFieldOption.batch_field_option(table_id_list=result_table_id_list)
        # RT的option
        rt_option_dict = ResultTableOption.batch_result_table_option(table_id_list=result_table_id_list)

        # 存储的组合
        storage_dict = {table_id: [] for table_id in result_table_id_list}

        for storage_name, storage_class in list(ResultTable.REAL_STORAGE_DICT.items()):
            for storage_info in storage_class.objects.filter(table_id__in=result_table_id_list):
                storage_dict[storage_info.table_id].append(storage_name)

    # 2. 组合
    for result_table_info in result_table_list:
        result_table_name = result_table_info["table_id"]

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
