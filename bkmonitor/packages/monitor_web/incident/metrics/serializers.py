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
from monitor_web.incident.metrics.constants import MetricType, EntityType


class MetricsSearchSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", default=None)
    metric_type = serializers.CharField(label=" node - 节点指标 / dependency|ebpf_call - 边指标", default=None)
    index_info = serializers.JSONField(label="索引信息", default=None)
    start_time = serializers.IntegerField(label="开始时间", default=None)
    end_time = serializers.IntegerField(label="结束时间", default=None)
    interval = serializers.IntegerField(label="时间间隔", default=None)

    def validate_node(self, index_info: dict):
        entity_type = index_info.get("entity_type", "")
        valid_entity_types = EntityType.choices()
        if entity_type not in valid_entity_types:
            raise serializers.ValidationError(f"entity_type must be one of {valid_entity_types}")
        dimensions = index_info.get("dimensions", {})

        # 定义各entity_type所需的必填维度字段
        required_dimensions = {
            EntityType.APMService.value: ["apm_service_name", "apm_application_name"],
            EntityType.BcsPod.value: ["cluster_id", "namespace", "pod_name"],
            EntityType.BkNodeHost.value: ["inner_ip", "bk_cloud_id"],
            EntityType.UnKnown.value: [],
        }

        # 获取当前entity_type所需的必填字段列表，如果entity_type不在配置中则默认为空列表
        required_fields = required_dimensions.get(entity_type, [])

        # 遍历必填字段并进行校验
        for field in required_fields:
            if not dimensions.get(field):
                raise serializers.ValidationError(f"dimension.{field} is required")

    def validate_edge(self, index_info: dict):
        source_type = index_info.get("source_type", "")
        target_type = index_info.get("target_type", "")
        valid_entity_types = EntityType.choices()
        if source_type not in valid_entity_types:
            raise serializers.ValidationError(f"source_type must be one of {valid_entity_types}")
        if target_type not in valid_entity_types:
            raise serializers.ValidationError(f"target_type must be one of {valid_entity_types}")

    def validate(self, attrs):
        index_info = attrs.get("index_info")
        if not isinstance(index_info, dict):
            raise serializers.ValidationError("index_info must be a json object")

        metric_type = attrs.get("metric_type")
        valid_metric_types = MetricType.choices()
        if metric_type not in valid_metric_types:
            raise serializers.ValidationError(f"metric_type must be one of {valid_metric_types}")

        if metric_type == MetricType.NODE.value:
            self.validate_node(index_info)

        elif metric_type == MetricType.EBPF_CALL.value or metric_type == MetricType.DEPENDENCY.value:
            self.validate_edge(index_info)

        return attrs
