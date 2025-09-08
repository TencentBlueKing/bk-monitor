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
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils.translation import gettext as _

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
from constants.data_source import DATA_TYPE_LABEL_ALIAS, DataSourceLabel, DataTypeLabel

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
    is_sdk_enabled: bool = field(default=True)


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
    is_supported: bool = field(default=True)
    error_msg: str = field(default="")


@dataclass
class MetricRecommend(BaseAnomalyConfig):
    # 指标推荐
    is_enabled: bool = field(default=False)
    result_table_id: str = field(default="")
    is_supported: bool = field(default=True)
    error_msg: str = field(default="")


class ReadOnlyAiSetting:
    def __init__(self, bk_biz_id: int, config: Optional[Dict[str, Dict[str, Any]]] = None):
        self.bk_biz_id = bk_biz_id
        config = config or self.default_config

        kpi_anomaly_detection = KpiAnomalyConfig().from_dict(config[KPI_ANOMALY_DETECTION])
        kpi_anomaly_detection.is_sdk_enabled = (
            True if kpi_anomaly_detection.is_sdk_enabled is None else kpi_anomaly_detection.is_sdk_enabled
        )
        multivariate_anomaly_detection = MultivariateAnomalyDetection.from_dict(config[MULTIVARIATE_ANOMALY_DETECTION])
        if DIMENSION_DRILL in config:
            dimension_drill = DimensionDrill.from_dict(config[DIMENSION_DRILL])
            dimension_drill.is_supported = (
                True if dimension_drill.is_supported is None else dimension_drill.is_supported
            )
        else:
            dimension_drill = DimensionDrill()
        if METRIC_RECOMMEND in config:
            metric_recommend = MetricRecommend.from_dict(config[METRIC_RECOMMEND])
            metric_recommend.is_supported = (
                True if metric_recommend.is_supported is None else metric_recommend.is_supported
            )
        else:
            metric_recommend = MetricRecommend()

        self.kpi_anomaly_detection = kpi_anomaly_detection
        self.multivariate_anomaly_detection = multivariate_anomaly_detection
        self.dimension_drill = dimension_drill
        self.metric_recommend = metric_recommend

    def to_dict(self, query_configs=None):
        query_configs = query_configs or []

        results = {
            KPI_ANOMALY_DETECTION: self.kpi_anomaly_detection.to_dict(),
            MULTIVARIATE_ANOMALY_DETECTION: self.multivariate_anomaly_detection.to_dict(),
            DIMENSION_DRILL: self.dimension_drill.to_dict(),
            METRIC_RECOMMEND: self.metric_recommend.to_dict(),
        }

        # 多指标不支持
        not_supported_msg = ""
        if len(query_configs) > 1:
            results[DIMENSION_DRILL]["is_supported"] = False
            results[METRIC_RECOMMEND]["is_supported"] = False
            not_supported_msg = _("多指标计算")
        elif len(query_configs) == 1:
            if query_configs[0]["data_type_label"] != DataTypeLabel.TIME_SERIES:
                results[DIMENSION_DRILL]["is_supported"] = False
                results[METRIC_RECOMMEND]["is_supported"] = False
                not_supported_msg = DATA_TYPE_LABEL_ALIAS[query_configs[0]["data_type_label"]]
            elif query_configs[0]["data_source_label"] not in (
                DataSourceLabel.BK_MONITOR_COLLECTOR,
                DataSourceLabel.BK_DATA,
                DataSourceLabel.CUSTOM,
            ):
                results[DIMENSION_DRILL]["is_supported"] = False
                results[METRIC_RECOMMEND]["is_supported"] = False

                if query_configs[0]["data_source_label"] == DataSourceLabel.PROMETHEUS:
                    not_supported_msg = _("PromSQL查询的指标")
                elif query_configs[0]["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH:
                    not_supported_msg = _("日志平台指标")

        results[DIMENSION_DRILL]["error_msg"] = not_supported_msg
        results[METRIC_RECOMMEND]["error_msg"] = not_supported_msg

        return results

    def scene_is_access_aiops(self, scene):
        scene_config = getattr(self, scene)
        if scene in MultivariateAnomalyDetection.get_scene_list():
            return scene_config.is_enabled and scene_config.intelligent_detect.get("status") == AccessStatus.SUCCESS
        else:
            err_msg = "ai setting(bk_biz_id:{}) unknow scene({})".format(self.bk_biz_id, scene)
            logger.error(err_msg)
            raise AiSettingException(err_msg)

    @property
    def default_config(self):
        multivariate_anomaly_detection = MultivariateAnomalyDetection()
        for scene in MultivariateAnomalyDetection.get_scene_list():
            setattr(multivariate_anomaly_detection, scene, MultivariateAnomalySceneConfig())

        return {
            KPI_ANOMALY_DETECTION: KpiAnomalyConfig().to_dict(),
            MULTIVARIATE_ANOMALY_DETECTION: multivariate_anomaly_detection.to_dict(),
            DIMENSION_DRILL: DimensionDrill().to_dict(),
            METRIC_RECOMMEND: MetricRecommend().to_dict(),
        }


class AiSetting(ReadOnlyAiSetting):
    def __init__(self, bk_biz_id: int):
        multivariate_anomaly_detection = MultivariateAnomalyDetection()
        for scene in MultivariateAnomalyDetection.get_scene_list():
            setattr(multivariate_anomaly_detection, scene, MultivariateAnomalySceneConfig())

        self.ai_setting, __ = AIFeatureSettings.objects.get_or_create(
            bk_biz_id=bk_biz_id, defaults={"config": self.default_config}
        )

        super().__init__(bk_biz_id, self.ai_setting.config)

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
