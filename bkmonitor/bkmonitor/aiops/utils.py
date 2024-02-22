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
from dataclasses import asdict, dataclass, field, fields

from django.conf import settings

from bkmonitor.dataflow.constant import AccessStatus
from bkmonitor.models.aiops import AIFeatureSettings
from constants.aiops import (
    AI_SETTING_APPLICATION_CONFIG_KEY,
    DEFAULT_SENSITIVITY,
    DIMENSION_DRILL,
    KPI_ANOMALY_DETECTION,
    METRIC_RECOMMEND,
    MULTIVARIATE_ANOMALY_DETECTION,
)

logger = logging.getLogger("bkmonitor.aiops")


class AiSettingException(Exception):
    pass


class BaseAnomalyConfig:
    to_dict = asdict

    @classmethod
    def from_dict(cls, data):
        init_fields = {f.name for f in fields(cls) if f.init}
        filtered_data = {k: data.pop(k, None) for k in init_fields}
        instance = cls(**filtered_data)
        return instance


@dataclass
class KpiAnomalyConfig(BaseAnomalyConfig):
    # 单指标异常检测
    default_plan_id: int = field(default_factory=lambda: settings.BK_DATA_PLAN_ID_INTELLIGENT_DETECTION)


@dataclass
class MultivariateAnomalySceneConfig(BaseAnomalyConfig):
    # 多指标异常检测下的场景配置
    default_plan_id: int = field(default=0)
    default_sensitivity: int = field(default=DEFAULT_SENSITIVITY)
    is_enabled: bool = field(default=False)
    exclude_target: list = field(default_factory=list)
    intelligent_detect: dict = field(default_factory=dict)
    plan_args: dict = field(default_factory=dict)

    def is_access_aiops(self):
        return (
            settings.IS_ACCESS_BK_DATA
            and self.is_enabled
            and self.intelligent_detect.get("status") == AccessStatus.SUCCESS
        )


@dataclass
class MultivariateAnomalyDetection:
    # 多指标异常检测
    # 主机场景
    host: MultivariateAnomalySceneConfig = field(default_factory=MultivariateAnomalySceneConfig)

    @classmethod
    def from_dict(cls, data):
        init_fields = cls.get_scene_list()
        instance = cls()
        for scene, scene_config in data.items():
            if scene not in init_fields:
                continue
            setattr(instance, scene, MultivariateAnomalySceneConfig.from_dict(scene_config))
        return instance

    def to_dict(self):
        result = {}
        for scene in self.get_scene_list():
            result.update({scene: getattr(self, scene, MultivariateAnomalySceneConfig()).to_dict()})
        return result

    @classmethod
    def get_scene_list(cls):
        return {f.name for f in fields(cls) if f.init}


@dataclass
class DimensionDrill(BaseAnomalyConfig):
    # 维度下钻
    is_enabled: bool = field(default=False)


@dataclass
class MetricRecommend(BaseAnomalyConfig):
    # 指标推荐
    is_enabled: bool = field(default=False)
    result_table_id: str = field(default="")


class AiSetting:
    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id

        kpi_anomaly_detection = KpiAnomalyConfig()
        multivariate_anomaly_detection = MultivariateAnomalyDetection()
        for scene in MultivariateAnomalyDetection.get_scene_list():
            setattr(multivariate_anomaly_detection, scene, MultivariateAnomalySceneConfig())

        dimension_drill = DimensionDrill()
        metric_recommend = MetricRecommend()

        self.ai_setting, created = AIFeatureSettings.objects.get_or_create(
            bk_biz_id=bk_biz_id,
            defaults={
                "config": {
                    KPI_ANOMALY_DETECTION: kpi_anomaly_detection.to_dict(),
                    MULTIVARIATE_ANOMALY_DETECTION: multivariate_anomaly_detection.to_dict(),
                    DIMENSION_DRILL: dimension_drill.to_dict(),
                    METRIC_RECOMMEND: metric_recommend.to_dict(),
                }
            },
        )

        if not created:
            kpi_anomaly_detection = KpiAnomalyConfig().from_dict(self.ai_setting.config[KPI_ANOMALY_DETECTION])
            multivariate_anomaly_detection = MultivariateAnomalyDetection.from_dict(
                self.ai_setting.config[MULTIVARIATE_ANOMALY_DETECTION]
            )
            if DIMENSION_DRILL in self.ai_setting.config:
                dimension_drill = DimensionDrill.from_dict(self.ai_setting.config[DIMENSION_DRILL])
            if METRIC_RECOMMEND in self.ai_setting.config:
                metric_recommend = MetricRecommend.from_dict(self.ai_setting.config[METRIC_RECOMMEND])

        self.kpi_anomaly_detection = kpi_anomaly_detection
        self.multivariate_anomaly_detection = multivariate_anomaly_detection
        self.dimension_drill = dimension_drill
        self.metric_recommend = metric_recommend

    def scene_is_access_aiops(self, scene):
        scene_config = getattr(self, scene)
        if scene in MultivariateAnomalyDetection.get_scene_list():
            return scene_config.is_enabled and scene_config.intelligent_detect.get("status") == AccessStatus.SUCCESS
        else:
            err_msg = "ai setting(bk_biz_id:{}) unknow scene({})".format(self.bk_biz_id, scene)
            logger.error(err_msg)
            raise AiSettingException(err_msg)

    def create(self, kpi_anomaly_detection, multivariate_anomaly_detection):
        value = {
            KPI_ANOMALY_DETECTION: kpi_anomaly_detection,
            MULTIVARIATE_ANOMALY_DETECTION: multivariate_anomaly_detection,
            DIMENSION_DRILL: self.dimension_drill.to_dict(),
            METRIC_RECOMMEND: self.metric_recommend.to_dict(),
        }
        AIFeatureSettings.objects.create(cc_biz_id=self.bk_biz_id, key=AI_SETTING_APPLICATION_CONFIG_KEY, value=value)

    def save(self, kpi_anomaly_detection=None, multivariate_anomaly_detection=None):
        kpi_anomaly_detection = (
            kpi_anomaly_detection if kpi_anomaly_detection is not None else self.kpi_anomaly_detection.to_dict()
        )
        multivariate_anomaly_detection = (
            multivariate_anomaly_detection
            if multivariate_anomaly_detection is not None
            else self.multivariate_anomaly_detection.to_dict()
        )

        self.ai_setting.config = {
            KPI_ANOMALY_DETECTION: kpi_anomaly_detection,
            MULTIVARIATE_ANOMALY_DETECTION: multivariate_anomaly_detection,
            DIMENSION_DRILL: self.dimension_drill.to_dict(),
            METRIC_RECOMMEND: self.metric_recommend.to_dict(),
        }

        self.ai_setting.save()

        self.kpi_anomaly_detection = KpiAnomalyConfig.from_dict(kpi_anomaly_detection)
        self.multivariate_anomaly_detection = MultivariateAnomalyDetection.from_dict(multivariate_anomaly_detection)

    def to_dict(self):
        return {
            KPI_ANOMALY_DETECTION: self.kpi_anomaly_detection.to_dict(),
            MULTIVARIATE_ANOMALY_DETECTION: self.multivariate_anomaly_detection.to_dict(),
            DIMENSION_DRILL: self.dimension_drill.to_dict(),
            METRIC_RECOMMEND: self.metric_recommend.to_dict(),
        }
