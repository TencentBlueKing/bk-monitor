# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from datetime import datetime

from rest_framework import serializers

from fta_web.alert.serializers import SearchConditionSerializer


class IncidentSearchSerializer(serializers.Serializer):
    bk_biz_ids = serializers.ListField(label="业务ID", default=None)
    status = serializers.ListField(label="状态", required=False, child=serializers.CharField())
    conditions = SearchConditionSerializer(label="搜索条件", many=True, default=[])
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])

    def validate_conditions(self, value):
        for condition in value:
            # 对时间字段进行转换 统一转换成时间戳
            # 时间可能是 2025-09-10 10:00:00 或者 纯时间戳
            if condition["key"] in ["create_time", "update_time", "begin_time", "end_time"]:
                for index, condition_value in enumerate(condition["value"]):
                    condition_value = str(condition_value).strip()
                    if condition_value.isdigit() and len(condition_value) in [10]:
                        condition["value"][index] = condition_value
                        continue
                    try:
                        dt = datetime.strptime(condition_value, "%Y-%m-%d %H:%M:%S")
                        condition["value"][index] = str(int(dt.timestamp()))

                    except ValueError:
                        raise serializers.ValidationError(
                            f'{condition["key"]}字段值必须是字符串时间戳10位或者文本日期格式，当前值为：{condition_value}'
                        )

        return value