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
from monitor_web.incident.metrics.constants import MetricType

class MetricsSearchSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", default=None)
    metric_type = serializers.CharField(label=" node - 节点指标 / dependency|ebpf_call - 边指标", default=None)
    index_info = serializers.JSONField(label="索引信息", default=None)
    start_time = serializers.IntegerField(label="开始时间", default=None)
    end_time = serializers.IntegerField(label="结束时间", default=None)

    def validate(self, attrs):
        index_info = attrs.get("index_info")
        if not isinstance(index_info, dict):
            raise serializers.ValidationError("index_info must be a json object")
        metric_type = attrs.get("metric_type")
        valid_metric_types = [choice[0] for choice in MetricType.choices()]
        if metric_type not in valid_metric_types:
            raise serializers.ValidationError(f"metric_type must be one of {valid_metric_types}")
        return attrs
