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

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.dataflow.constant import AccessStatus
from bkmonitor.views import serializers
from constants.aiops import SCENE_METRIC_MAP
from core.drf_resource import Resource
from monitor_web.aiops.ai_setting.serializers import (
    KPIAnomalyDetectionSerializer,
    MultivariateAnomalyDetectionSerializer,
)
from monitor_web.tasks import (
    access_aiops_multivariate_anomaly_detection_by_bk_biz_id,
    stop_aiops_multivariate_anomaly_detection_flow,
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

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        ai_setting = AiSetting(bk_biz_id=bk_biz_id)
        return ai_setting.to_dict()


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

        # 需要接入的场景列表
        need_access_scenes = []

        # 需要停止的flow
        need_stop_scenes = []

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
                scene_config_intelligent_detect["status"] = AccessStatus.PENDING
                need_access_scenes.append(scene)
            else:
                need_stop_scenes.append(scene)

        ai_setting.save(
            kpi_anomaly_detection=kpi_anomaly_detection,
            multivariate_anomaly_detection=multivariate_anomaly_detection_params,
        )

        # aiops异步操作
        if need_access_scenes:
            access_aiops_multivariate_anomaly_detection_by_bk_biz_id.delay(bk_biz_id, need_access_scenes)
        if need_stop_scenes:
            stop_aiops_multivariate_anomaly_detection_flow.delay(bk_biz_id, need_stop_scenes)

        return {}
