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

AI_SETTING_APPLICATION_CONFIG_KEY = "ai_setting"

DEFAULT_SENSITIVITY = 5

# ai设置单指标异常保存字段
KPI_ANOMALY_DETECTION = "kpi_anomaly_detection"

# ai设置多指标异常保存字段
MULTIVARIATE_ANOMALY_DETECTION = "multivariate_anomaly_detection"

# ai设置维度下钻保存字段
DIMENSION_DRILL = "dimension_drill"

# ai设置指标推荐保存字段
METRIC_RECOMMEND = "metric_recommend"


# 多指标异常检测主机场景默认输入字段
MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD = "metrics_json"

# 多指标异常检测主机场景默认metric_list
MULTIVARIATE_ANOMALY_DETECTION_SCENE_HOST_METRIC_LIST = [
    'system__cpu_detail__usage',
    'system__load__load5',
    'system__swap__pct_used',
    'system__mem__pct_used',
    'system__mem__psc_pct_used',
    'system__net__speed_recv',
    'system__net__speed_sent',
    'system__disk__in_use',
    'system__io__util',
    'system__env__procs',
]


class SceneSet(object):
    HOST = "host"


SCENE_METRIC_MAP = {SceneSet.HOST: MULTIVARIATE_ANOMALY_DETECTION_SCENE_HOST_METRIC_LIST}
