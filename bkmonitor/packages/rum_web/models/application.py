"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property

from bkm_space.api import SpaceApi
from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel
from bkmonitor.utils.time_tools import get_datetime_range
from bkmonitor.utils.request import get_request
from common.log import logger
from constants.common import DEFAULT_TENANT_ID
from constants.rum import TelemetryDataType
from core.drf_resource import api

from rum_web.constants import DataStatus, DEFAULT_NO_DATA_PERIOD


class Application(AbstractRecordModel):
    """
    RUM SaaS 侧镜像应用表
    """

    NO_DATA_CONFIG_KEY = "no_data_config"

    class NoDataConfig:
        no_data_period = "no_data_period"

    APPLICATION_DATASOURCE_CONFIG_KEY = "application_datasource_config"
    APDEX_CONFIG_KEY = "application_apdex_config"
    QPS_CONFIG_KEY = "application_qps_config"

    application_id = models.BigIntegerField("应用Id", primary_key=True)
    bk_tenant_id = models.CharField("租户ID", max_length=64, default=DEFAULT_TENANT_ID)
    bk_biz_id = models.IntegerField("业务id", db_index=True)
    app_name = models.CharField("应用名称", max_length=50)
    app_alias = models.CharField("应用别名", max_length=128)
    description = models.CharField("应用描述", max_length=255, default="")
    client_type = models.CharField("前端类型", max_length=32, default="web")

    metric_result_table_id = models.CharField("聚合指标结果表", max_length=128, default="")
    span_result_table_id = models.CharField("原始日志结果表", max_length=128, default="")
    time_series_group_id = models.IntegerField("时序分组ID", default=0)

    source = models.CharField("来源系统", default=get_source_app_code, max_length=32)
    apm_application_id = models.BigIntegerField("关联 APM 应用ID", null=True, blank=True)

    data_status = models.CharField("数据状态", max_length=32, default="no_data")

    class Meta:
        ordering = ["-update_time", "-application_id"]
        index_together = [["bk_biz_id", "app_name"], ["update_time", "application_id"]]

    def __str__(self):
        return f"<RumApplication {self.application_id} {self.app_name}>"

    def __repr__(self):
        return self.__str__()

    @classmethod
    @atomic
    def create_application(
        cls,
        bk_tenant_id,
        bk_biz_id,
        app_name,
        app_alias,
        description,
        storage_options=None,
    ):
        create_params = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "app_alias": app_alias,
            "description": description,
            "es_storage_config": storage_options,
        }
        application_info = api.rum_api.create_application(create_params)
        application = cls.objects.create(
            bk_tenant_id=bk_tenant_id,
            application_id=application_info["application_id"],
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            app_alias=app_alias,
            description=description,
        )

        # 初始化应用配置
        application.set_init_datasource_config(application_info.get("datasource_option"))
        application.set_init_apdex_config()
        application.set_init_qps_config()

        return Application.objects.get(application_id=application.application_id)

    @classmethod
    def get_application_by_app_id(cls, application_id):
        instance = cls.objects.filter(application_id=application_id).first()
        if not instance:
            raise ValueError(f"rum application(id: {application_id}) not found.")
        return instance

    @classmethod
    def get_application_id_by_app_name(cls, app_name: str):
        request = get_request()
        biz_id: int | None = request.biz_id

        if biz_id is None:
            try:
                data = json.loads(request.body.decode("utf-8"))
            except (TypeError, json.JSONDecodeError):
                raise ValueError(f"application({app_name}) not found")

            # space_uid to biz_id
            if "space_uid" in data:
                biz_id = SpaceApi.get_space_detail(space_uid=data["space_uid"]).bk_biz_id

        try:
            return cls.objects.filter(bk_biz_id=biz_id, app_name=app_name).values_list("application_id", flat=True)[0]
        except IndexError:
            raise ValueError(f"application({app_name}) not found")

    def sync_datasource(self):
        """同步数据源到 SaaS 中"""
        detail = api.rum_api.detail_application(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

        rum_ds_info = detail.get("rum_config")
        metric_ds_info = detail.get("metric_config")
        if not rum_ds_info or not metric_ds_info:
            logger.warning(f"[SyncDatasource] rum-api create failed(id: {self.application_id}), skip")
            return

        self.span_result_table_id = rum_ds_info["result_table_id"]
        self.metric_result_table_id = metric_ds_info["result_table_id"]
        self.time_series_group_id = metric_ds_info["time_series_group_id"]
        self.save()

    @cached_property
    def no_data_period(self):
        no_data_config = self.get_config_by_key(self.NO_DATA_CONFIG_KEY)
        if no_data_config:
            return no_data_config.config_value[self.NoDataConfig.no_data_period]
        return DEFAULT_NO_DATA_PERIOD

    def set_data_status(self):
        """刷新数据状态"""
        from rum_web.handlers.backend_data_handler import telemetry_handler_registry

        start_time, end_time = get_datetime_range("minute", self.no_data_period)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

        if not getattr(self, "is_enabled", False):
            data_status = DataStatus.DISABLED
        else:
            try:
                count = telemetry_handler_registry(TelemetryDataType.RUM.value, app=self).get_data_count(
                    start_time, end_time
                )
                if count:
                    logger.info(
                        f"[Application] set_data_status ->  "
                        f"bk_biz_id: {self.bk_biz_id} app: {self.app_name}"
                        f"have data in {self.no_data_period} period"
                    )

                    data_status = DataStatus.NORMAL
                else:
                    data_status = DataStatus.NO_DATA
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"[Application] set app: {self.app_name} data_status failed: {e}")
                data_status = DataStatus.NO_DATA

        # 这里通过update方式，指定字段更新，是为了不自动变更 update_user， update_time 字段
        Application.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).update(data_status=data_status)

    def get_all_config(self):
        return RumAppConfig.get_all_application_config_value(self.application_id)

    def get_config_by_key(self, key: str):
        return RumAppConfig.get_application_config_value(self.application_id, key)

    def set_init_apdex_config(self):
        """初始化 Apdex 默认配置，对齐 apm_web.Application.set_init_apdex_config"""
        from rum_web.constants import DEFAULT_RUM_APDEX_CONFIG

        RumAppConfig.application_config_setup(self.application_id, self.APDEX_CONFIG_KEY, DEFAULT_RUM_APDEX_CONFIG)

    def set_init_qps_config(self):
        """初始化 QPS 默认配置，对齐 apm_web.Application.set_init_qps_config"""
        from rum_web.constants import DEFAULT_RUM_APP_QPS

        RumAppConfig.application_config_setup(self.application_id, self.QPS_CONFIG_KEY, DEFAULT_RUM_APP_QPS)

    def set_init_datasource_config(self, datasource_option=None):
        """初始化存储配置"""
        if datasource_option:
            config_value = datasource_option
        else:
            from django.conf import settings

            config_value = {
                "es_storage_cluster": settings.RUM_APP_DEFAULT_ES_STORAGE_CLUSTER,
                "es_retention": settings.RUM_APP_DEFAULT_ES_RETENTION,
                "es_number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
                "es_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
                "es_slice_size": settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT,
            }
        RumAppConfig.application_config_setup(self.application_id, self.APPLICATION_DATASOURCE_CONFIG_KEY, config_value)


class RumAppConfig(models.Model):
    """
    RUM SaaS 侧通用配置
    """

    APPLICATION_LEVEL = "application_level"

    config_level = models.CharField("配置级别", max_length=128)
    level_key = models.CharField("配置目标key", max_length=512)
    config_key = models.CharField("config key", max_length=255)
    config_value = JsonField("配置信息")

    class Meta:
        unique_together = [["config_level", "level_key", "config_key"]]
        app_label = "rum_web"

    @classmethod
    def get_all_application_config_value(cls, application_id):
        return cls.objects.filter(config_level=cls.APPLICATION_LEVEL, level_key=application_id)

    @classmethod
    def get_application_config_value(cls, application_id, config_key: str):
        return cls.objects.filter(
            config_key=config_key, config_level=cls.APPLICATION_LEVEL, level_key=application_id
        ).first()

    @classmethod
    def application_config_setup(cls, application_id, config_key, config_value):
        return cls._setup(cls.APPLICATION_LEVEL, application_id, config_key, config_value)

    @classmethod
    def delete_application_config(cls, application_id):
        """删除应用级别所有配置，用于应用删除时清理"""
        cls.objects.filter(config_level=cls.APPLICATION_LEVEL, level_key=application_id).delete()

    @classmethod
    def _setup(cls, config_level, level_key, config_key, config_value):
        qs = cls.objects.filter(config_level=config_level, level_key=level_key, config_key=config_key)
        if qs.exists():
            qs.update(config_value=config_value)
            return

        cls.objects.create(
            config_level=config_level, level_key=level_key, config_key=config_key, config_value=config_value
        )
