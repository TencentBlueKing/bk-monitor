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
from dataclasses import dataclass

from django.conf import settings

from bkmonitor.models import AlgorithmModel
from core.drf_resource import api


class VisualType:
    """
    可视化类型
    """

    # 只显示异常点
    NONE = "none"

    # 上下界
    BOUNDARY = "boundary"

    # 异常分值
    SCORE = "score"

    # 时序预测
    FORECASTING = "forecasting"


class AccessStatus:
    """
    数据接入的状态
    注意：这里不是指 flow 的状态，而是监控对 flow 接入流程的自身状态流转
    """

    # 等待中
    PENDING = "pending"

    # 已创建
    CREATED = "created"

    # 执行中
    RUNNING = "running"

    # 成功
    SUCCESS = "success"

    # 失败
    FAILED = "failed"


class RTAccessBkDataStatus:
    # 等待中
    PENDING = "pending"

    # 执行中
    RUNNING = "running"

    # 成功
    SUCCESS = "success"

    # 失败
    FAILED = "failed"


def get_scene_id_by_name(scene_name):
    """
    根据场景名称获取场景ID
    """
    for scene in api.bkdata.list_scene_service():
        if scene["scene_name"] == scene_name:
            return scene["scene_id"]
    return 0


@dataclass
class AlgorithmInfo:
    env_scene_variate_name: str
    env_plan_variate_name: str
    bk_base_name: str


METRIC_RECOMMENDATION_SCENE_NAME = "MetricRecommendation"

ALGORITHM_INFO_MAP = {
    AlgorithmModel.AlgorithmChoices.IntelligentDetect: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_INTELLIGENT_DETECTION",
        env_plan_variate_name="BK_DATA_PLAN_ID_INTELLIGENT_DETECTION",
        bk_base_name="KPIAnomalyDetection",
    ),
    AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_TIME_SERIES_FORECASTING",
        env_plan_variate_name="",
        bk_base_name="TimeSeriesForecasting",
    ),
    AlgorithmModel.AlgorithmChoices.AbnormalCluster: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_ABNORMAL_CLUSTER",
        env_plan_variate_name="",
        bk_base_name="AbnormalCluster",
    ),
    AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION",
        env_plan_variate_name="BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION",
        bk_base_name="MultivariateAnomalyDetection",
    ),
    METRIC_RECOMMENDATION_SCENE_NAME: AlgorithmInfo(
        env_scene_variate_name="BK_DATA_SCENE_ID_METRIC_RECOMMENDATION",
        env_plan_variate_name="BK_DATA_PLAN_ID_METRIC_RECOMMENDATION",
        bk_base_name="MetricRecommendation",
    ),
}


def get_scene_id_by_algorithm(algorithm_id):
    """
    获取算法场景ID
    """
    if not settings.IS_ACCESS_BK_DATA:
        # 未接入数据平台直接跳过
        return 0

    if algorithm_id not in ALGORITHM_INFO_MAP:
        return 0

    algorithm_info = ALGORITHM_INFO_MAP[algorithm_id]
    if not getattr(settings, algorithm_info.env_scene_variate_name):
        setattr(settings, algorithm_info.env_scene_variate_name, get_scene_id_by_name(algorithm_info.bk_base_name))
    return getattr(settings, algorithm_info.env_scene_variate_name)


AI_SETTING_ALGORITHMS = [
    AlgorithmModel.AlgorithmChoices.IntelligentDetect,
    AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection,
]


def get_plan_id_by_algorithm(algorithm_id):
    if not settings.IS_ACCESS_BK_DATA:
        # 未接入数据平台直接跳过
        return 0

    if algorithm_id not in ALGORITHM_INFO_MAP:
        return 0

    algorithm_info = ALGORITHM_INFO_MAP[algorithm_id]

    if not algorithm_info.env_plan_variate_name:
        return 0

    if not getattr(settings, algorithm_info.env_plan_variate_name):
        plans = api.bkdata.list_scene_service_plans(scene_id=get_scene_id_by_algorithm(algorithm_id))

        if not plans:
            return 0

        setattr(settings, algorithm_info.env_plan_variate_name, plans[0]["plan_id"])
    return getattr(settings, algorithm_info.env_plan_variate_name)


def get_aiops_env_bkdata_biz_id():
    result = api.bkdata.get_aiops_envs()
    return result.get("BKDATA_BIZ_ID")
