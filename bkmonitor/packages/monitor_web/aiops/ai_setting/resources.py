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
import logging

from django.conf import settings

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.dataflow.constant import AccessStatus
from bkmonitor.documents import AlertDocument
from bkmonitor.views import serializers
from constants.aiops import SCENE_METRIC_MAP
from core.drf_resource import Resource
from monitor_web.aiops.ai_setting.serializers import (
    KPIAnomalyDetectionSerializer,
    MultivariateAnomalyDetectionSerializer,
)

logger = logging.getLogger("monitor_web")


def build_plan_args(metric_list, sensitivity):
    return {"$metric_list": metric_list, "$sensitivity": sensitivity}


class FetchAiSettingResource(Resource):
    """
    拉取业务ai设置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        alert_id = serializers.IntegerField(required=False)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        alert_id = validated_request_data.get("alert_id")

        query_configs = []
        if alert_id:
            alert_doc = AlertDocument.get(alert_id)
            query_configs = alert_doc.strategy["items"][0]["query_configs"]

        ai_setting = AiSetting(bk_biz_id=bk_biz_id)
        results = ai_setting.to_dict(query_configs)

        results["wx_cs_link"] = ""
        for item in settings.BK_DATA_ROBOT_LINK_LIST:
            if item["icon_name"] == "icon-kefu":
                results["wx_cs_link"] = item["link"]
        return results


class SaveAiSettingResource(Resource):
    """
    保存业务ai设置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        kpi_anomaly_detection = KPIAnomalyDetectionSerializer()
        multivariate_anomaly_detection = MultivariateAnomalyDetectionSerializer()

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        kpi_anomaly_detection = validated_request_data["kpi_anomaly_detection"]
        multivariate_anomaly_detection_params = validated_request_data["multivariate_anomaly_detection"]

        ai_setting = AiSetting(bk_biz_id=bk_biz_id)

        for scene, scene_config in multivariate_anomaly_detection_params.items():
            # 取参数中的is_enabled和数据库中的is_enabled进行比对
            params_scene_setting_is_enabled = scene_config.get("is_enabled", False)

            # 一些计算数据的保存
            sensitivity = scene_config.get("default_sensitivity")
            metric_list = ",".join(SCENE_METRIC_MAP.get(scene))
            plan_args = build_plan_args(metric_list, sensitivity)
            scene_config.update({"plan_args": plan_args})

            # 参数is_enabled为True为需要接入，为False则需要关闭
            if params_scene_setting_is_enabled:
                scene_config_intelligent_detect = scene_config.setdefault("intelligent_detect", {})

            # 不需要另外接入扫描任务，默认所有都成功
            scene_config_intelligent_detect["status"] = AccessStatus.SUCCESS

        ai_setting.save(
            kpi_anomaly_detection=kpi_anomaly_detection,
            multivariate_anomaly_detection=multivariate_anomaly_detection_params,
        )

        return {}
