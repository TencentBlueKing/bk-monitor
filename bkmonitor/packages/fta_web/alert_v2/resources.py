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

from bkmonitor.documents import AlertDocument
from constants.alert import K8STargetType
from core.drf_resource import Resource, resource
from fta_web.alert.resources import AlertDetailResource as BaseAlertDetailResource
from monitor_web.data_explorer.event.resources import EventLogsResource


class AlertDetailResource(BaseAlertDetailResource):
    """
    告警详情
    """

    @classmethod
    def add_graph_extra_info(cls, alert, data):
        """
        添加图形额外信息
        """
        try:
            # ['f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554140.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554200.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554260.2860.2978.2',
            #  'f1c6877ba046e2d32bfd8393b4dd26f7.1763554320.2860.2978.2']

            anomaly_ids = data["extra_info"]["origin_alarm"]["trigger"]["anomaly_ids"]
        except KeyError:
            anomaly_ids = []
        data["anomaly_timestamps"] = sorted(int(i.split(".", 2)[1]) for i in anomaly_ids)
        return data


class AlertEventsResource(Resource):
    """
    根据告警 id 获取告警的关联事件
    """

    time_range_params = None

    class RequestSerializer(serializers.Serializer):
        alert_id = serializers.CharField(label="告警 id")
        limit = serializers.IntegerField(label="数量限制", required=False, default=10)
        offset = serializers.IntegerField(label="偏移量", required=False, default=0)

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        alert = AlertDocument.get(alert_id)
        target_type = alert.event.target_type
        self.time_range_params = {
            # 告警开始前五分钟
            "start_time": alert.first_anomaly_time - 5 * 60,
            # 告警产生后最多24小时
            "end_time": alert.end_time if alert.end_time else alert.first_anomaly_time + 24 * 60 * 60,
        }
        if target_type == "host":
            # 主机对象告警
            return self.query_events_by_host(validated_request_data, alert, target_type)
        elif target_type.startswith("K8S"):
            # 容器对象告警: event.target_type示例: K8S:Pod
            return self.query_events_by_k8s_target(validated_request_data, alert, target_type)

        raise ValueError(f"unsupported alert target type: {target_type}")

    def query_events_by_host(self, validated_request_data, alert, target_type):
        """
        根据告警对象: 主机 获取主机关联的事件
        """
        host_event_table_id = "gse_system_event"
        query_params = {
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "event",
                    "table": host_event_table_id,
                    "query_string": "",
                    "where": [
                        {
                            "condition": "and",
                            "key": "target",
                            "method": "eq",
                            "value": [f"{alert.event.bk_tareget_ip}:{alert.event.ip}"],
                        }
                    ],
                    "group_by": ["type"],
                    "filter_dict": {},
                }
            ],
            "bk_biz_id": alert.bk_biz_id,
            "limit": validated_request_data["limit"],
            "offset": validated_request_data["offset"],
            "sort": [],
        }
        query_params.update(self.time_range_params)
        return EventLogsResource()(query_params)

    def query_events_by_k8s_target(self, validated_request_data, alert, target_type):
        resource_type = target_type.split(":")[-1]
        # bcs_cluster_id = alert.event.bcs_cluster_id
        if resource_type == "Node":
            pass
        if resource_type == "Pod":
            pass
        if resource_type == "Workload":
            pass


class AlertK8sScenarioListResource(Resource):
    """
    根据告警 id 获取告警关联容器场景列表
    """

    K8sTargetScenarioMap = {
        K8STargetType.POD: ["performance", "network"],
        K8STargetType.WORKLOAD: ["performance", "network"],
        K8STargetType.NODE: ["capacity"],
        K8STargetType.SERVICE: ["network"],
    }

    class RequestSerializer(serializers.Serializer):
        alert_id = serializers.CharField(label="告警 id")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        alert = AlertDocument.get(alert_id)
        target_type = alert.event.target_type
        if target_type in [K8STargetType.POD, K8STargetType.WORKLOAD, K8STargetType.NODE, K8STargetType.SERVICE]:
            return self.K8sTargetScenarioMap[target_type]
        # todo: support other target type(apm)

        raise []


class AlertK8sMetricListResource(Resource):
    """
    根据容器观测场景 获取对应场景配置的指标列表
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.CharField(label="场景")

    def perform_request(self, validated_request_data):
        return resource.k8s.scenario_metric_list(scenario=validated_request_data["scenario"])


class AlertK8sTargetResource(Resource):
    """
    根据告警 id 获取告警关联容器对象
    """

    class RequestSerializer(serializers.Serializer):
        alert_id = serializers.CharField(label="告警 id")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        alert = AlertDocument.get(alert_id)
        target_type = alert.event.target_type
        if target_type in [K8STargetType.POD, K8STargetType.WORKLOAD, K8STargetType.NODE, K8STargetType.SERVICE]:
            return {"target_type": target_type, "target": alert.event.target}
        # todo: support other target type(apm)

        raise {"target_type": "", "target": None}
