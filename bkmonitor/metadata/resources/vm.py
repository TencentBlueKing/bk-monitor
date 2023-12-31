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

from collections import OrderedDict

from django.db.models import Q
from rest_framework import serializers

from core.drf_resource import Resource
from metadata import models
from metadata.models.space.space_data_source import get_real_biz_id


class QueryBizByBkBase(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_base_data_id_list = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])
        bk_base_vm_table_id_list = serializers.ListField(child=serializers.CharField(), required=False, default=[])

        def validate(self, data: OrderedDict) -> OrderedDict:
            # 判断参数不能同时为空
            if not (data.get("bk_base_data_id_list") or data.get("bk_base_vm_table_id_list")):
                raise ValueError("params is null")
            return data

    def perform_request(self, data):
        bk_base_data_id_list = data.get("bk_base_data_id_list") or []
        bk_base_vm_table_id_list = data.get("bk_base_vm_table_id_list") or []

        # 获取 table id
        table_id_bk_base_data_ids = {
            qs["result_table_id"]: qs["bk_base_data_id"]
            for qs in models.AccessVMRecord.objects.filter(
                Q(bk_base_data_id__in=bk_base_data_id_list) | Q(vm_result_table_id__in=bk_base_vm_table_id_list)
            ).values("result_table_id", "bk_base_data_id")
        }

        # 通过 table id 获取对应的业务信息
        table_id_biz_ids = {
            qs["table_id"]: qs["bk_biz_id"]
            for qs in models.ResultTable.objects.filter(table_id__in=table_id_bk_base_data_ids.keys()).values(
                "table_id", "bk_biz_id"
            )
        }

        # 针对业务为`0`的业务，需要通过 tsgroup 或 eventgroup 过滤，然后通过 dataname 进行拆分
        zero_biz_table_id_list = [table_id for table_id, biz_id in table_id_biz_ids.items() if biz_id == 0]

        # 获取对应的 data id
        table_id_data_ids = {
            qs["table_id"]: qs["bk_data_id"]
            for qs in models.DataSourceResultTable.objects.filter(table_id__in=zero_biz_table_id_list).values(
                "bk_data_id", "table_id"
            )
        }
        # 获取 data name
        data_id_names = {}
        data_id_space_uid_map = {}
        for qs in models.DataSource.objects.filter(bk_data_id__in=table_id_data_ids.values()).values(
            "bk_data_id", "data_name", "space_uid"
        ):
            data_id_names[qs["bk_data_id"]] = qs["data_name"]
            data_id_space_uid_map[qs["bk_data_id"]] = qs["space_uid"]
        # 查询是否在指定的表中
        data_id_ts_group_flag = {
            obj["bk_data_id"]: True
            for obj in models.TimeSeriesGroup.objects.filter(table_id__in=zero_biz_table_id_list).values("bk_data_id")
        }
        data_id_event_group_flag = {
            obj["bk_data_id"]: True
            for obj in models.EventGroup.objects.filter(table_id__in=zero_biz_table_id_list).values("bk_data_id")
        }
        bk_base_data_id_biz_id = {}
        # 获取对应的数据
        for table_id, bk_biz_id in table_id_biz_ids.items():
            # 跳过没有匹配到数据
            bk_base_data_id = table_id_bk_base_data_ids.get(table_id)
            if not bk_base_data_id:
                continue
            # NOTE: 应该不会有小于 0 的业务，当业务 ID 大于 0 时，直接返回
            if bk_biz_id > 0:
                bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id
                continue

            # 获取 0 业务对应的真实业务 ID
            data_id = table_id_data_ids.get(table_id)
            if not data_id:
                bk_base_data_id_biz_id[bk_base_data_id] = 0

            data_name = data_id_names.get(data_id)
            space_uid = data_id_space_uid_map.get(data_id)
            is_in_ts_group = data_id_ts_group_flag.get(data_id) or False
            is_in_event_group = data_id_event_group_flag.get(data_id) or False
            bk_biz_id = get_real_biz_id(data_name, is_in_ts_group, is_in_event_group, space_uid)
            bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id

        return bk_base_data_id_biz_id
