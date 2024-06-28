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

import json
from typing import List

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata.config import METADATA_RESULT_TABLE_WHITE_LIST
from metadata.models import AccessVMRecord
from metadata.utils.redis_tools import RedisTools


class AddBkDataTableIdsResource(Resource):
    """添加访问计算平台指标发现的结果表"""

    class RequestSerializer(serializers.Serializer):
        bkdata_table_ids = serializers.ListField(child=serializers.CharField(), required=True)

    def perform_request(self, data):
        bkdata_table_ids = data["bkdata_table_ids"]
        self._add_tid_list(bkdata_table_ids)

    def _add_tid_list(self, bkdata_table_ids: List):
        tid_list = list(
            AccessVMRecord.objects.filter(vm_result_table_id__in=bkdata_table_ids).values_list(
                "result_table_id", flat=True
            )
        )
        if not tid_list:
            raise ValidationError("not found bkmonitor table id")

        # 获取已有的数据
        data = RedisTools.get_list(METADATA_RESULT_TABLE_WHITE_LIST)
        data.extend(tid_list)
        # 去重
        data = list(set(data))
        # 保存到redis
        RedisTools.set(METADATA_RESULT_TABLE_WHITE_LIST, json.dumps(data))
