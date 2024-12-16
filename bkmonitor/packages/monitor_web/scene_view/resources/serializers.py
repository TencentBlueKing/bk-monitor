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

from rest_framework import serializers


# 注: 此序列化器的参数在 apm_web.k8s.resources.ListServicePodsResource 也使用到
class KubernetesListRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    keyword = serializers.CharField(required=False, allow_null=True, label="查询关键词", allow_blank=True)
    status = serializers.CharField(required=False, allow_null=True, label="状态过滤", allow_blank=True)
    condition_list = serializers.ListField(required=False, allow_null=True)
    filter_dict = serializers.DictField(required=False, allow_null=True, label="枚举列过滤")
    sort = serializers.CharField(required=False, allow_null=True, label="排序", allow_blank=True)
    page = serializers.IntegerField(required=False, allow_null=True, label="页码")
    page_size = serializers.IntegerField(required=False, allow_null=True, label="每页条数")
