"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from fta_web.alert.serializers import BaseSearchSerializer, SearchConditionSerializer


class IssueSearchSerializer(BaseSearchSerializer):
    """Issue 搜索基础序列化器"""

    status = serializers.ListField(
        label="筛选项",
        required=False,
        child=serializers.CharField(),
        help_text="MY_ISSUE(我负责的) / NO_ASSIGNEE(未分派)",
    )
    conditions = SearchConditionSerializer(label="搜索条件", many=True, default=[])
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    # 按指纹精确过滤"同一具体问题"的全部 Issue（含已解决历史），用于详情页"该问题历史"等场景
    fingerprint = serializers.CharField(label="Issue 指纹", required=False, allow_blank=True, default="")
