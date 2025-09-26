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
import json
import time
import traceback

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apm import constants
from apm.core.handlers.bk_data.flow import ApmFlow
from apm.models import ApmApplication
from bkmonitor.dataflow.auth import check_has_permission
from bkmonitor.dataflow.task.apm_metrics import APMVirtualMetricTask
from common.log import logger
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from metadata.models.storage import DataBusStatus


class Config:
    """虚拟指标配置项"""

    # 数据源id
    RAW_DATA_ID = "raw_data_id"
    # 数据源清洗配置
    DATABUS_CLEANS_JSON_CONFIG = "databus_cleans_json_config"
    # dataflow id
    DATAFLOW_ID = "dataflow_id"
    # dataflow 项目id
    PROJECT_ID = "project_id"


class VirtualMetricFlow:
    PREFIX = "bkapm_virtual_metric"

    def __init__(self, metric_datasource):
        self.bk_biz_id = metric_datasource.bk_biz_id
        self.app_name = metric_datasource.app_name
        self.metric_datasource = metric_datasource
        self.bkbase_operator = settings.APM_APP_BKDATA_OPERATOR
        self.bkbase_project_id = settings.APM_APP_BKDATA_VIRTUAL_METRIC_PROJECT_ID
        self.application = ApmApplication.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @property
    def datasource_name(self):
        # 数据源id
        return f"{self.PREFIX}_{self.app_name}"[-50:]

    @property
    def datasource_cleans_table_id(self):
        # 数据源清洗结果表id
        return f"{self.PREFIX}_{self.app_name}"

    @property
    def datasource_cleans_table_id_with_biz(self):
        # 完整数据源清洗结果表id
        return f"{self.bk_biz_id}_{self.datasource_cleans_table_id}"

    @property
    def description(self):
        # 数据描述信息
        return _("APM({})虚拟指标").format(self.app_name)

    def update_or_create(self):
        try:
            if self.metric_datasource.bk_data_virtual_metric_config:
                raw_data_id = self.get_config(Config.RAW_DATA_ID)
            else:
                # 创建数据源
                raw_data_id = self._create_deploy()

            # 创建/更新&启动清洗配置
            self._upsert_and_start_cleans(raw_data_id)

            # 项目授权
            self._auth_project()

            # 启动flow
            self._create_start_flow()

            logger.info(
                f"[BkBaseVirtualMetricHandler] bk_biz_id: {self.bk_biz_id} app_name: {self.app_name} " f"创建虚拟指标成功"
            )
        except Exception as e:  # noqa
            msg = f"APM bk_biz_id: {self.bk_biz_id} app_name: {self.app_name} 创建虚拟指标失败: {e} {traceback.format_exc()}"
            logger.exception(msg)
            raise ValueError(msg)

    def _auth_project(self):
        if not check_has_permission(self.bkbase_project_id, self.datasource_cleans_table_id_with_biz):
            try:
                params = {
                    "project_id": self.bkbase_project_id,
                    "object_id": self.datasource_cleans_table_id_with_biz,
                    "bk_biz_id": self.bk_biz_id,
                }
                api.bkdata.auth_result_table(**params)
            except BKAPIError as e:
                logger.exception(f"grant result table to project failed: {e}")
                raise ValueError(_("结果表授权失败"))

    def _create_start_flow(self):
        task = APMVirtualMetricTask(self.datasource_cleans_table_id_with_biz, self.bk_biz_id, self.app_name)
        task.create_flow(project_id=self.bkbase_project_id)
        task.start_flow()

        self.update_config({Config.PROJECT_ID: self.bkbase_project_id, Config.DATAFLOW_ID: task.data_flow.flow_id})

    def _get_metric_datasource(self):
        # 接入的数据源为kafka
        metric_data_id = self.metric_datasource.bk_data_id
        return resource.metadata.query_data_source(bk_data_id=metric_data_id)

    def _upsert_and_start_cleans(self, raw_data_id):
        params = {
            "bk_biz_id": self.bk_biz_id,
            "bk_username": self.bkbase_operator,
            "clean_config_name": "bkapm_metric",
            "description": _("APM应用{}虚拟指标清洗").format(self.app_name),
            "fields": constants.databus_cleans_fields,
            "json_config": json.dumps(constants.databus_cleans_json_config),
            "raw_data_id": raw_data_id,
            "result_table_name": self.datasource_cleans_table_id,
            "result_table_name_alias": self.datasource_cleans_table_id,
        }

        if self.get_config(Config.DATABUS_CLEANS_JSON_CONFIG):
            if constants.databus_cleans_json_config != self.get_config(Config.DATABUS_CLEANS_JSON_CONFIG):
                # 更新
                try:
                    api.bkdata.stop_databus_cleans(
                        result_table_id=f"{self.bk_biz_id}_{self.datasource_cleans_table_id}",
                        storages=["kafka"],
                        bk_username=self.bkbase_operator,
                    )
                    params["processing_id"] = f"{self.bk_biz_id}_{self.datasource_cleans_table_id}"
                    api.bkdata.update_databus_cleans(**params)
                except BKAPIError as e:
                    raise ValueError(_("更新清洗配置失败: {} {}").format(e, traceback.format_exc()))
        else:
            # 创建
            try:
                result = api.bkdata.databus_cleans(**params)
                logger.info(f"create databus cleans success, result: {result}")
            except BKAPIError as e:
                raise ValueError(_("创建清洗配置失败: {} {}").format(e, traceback.format_exc()))

        self.update_config({Config.DATABUS_CLEANS_JSON_CONFIG: constants.databus_cleans_json_config})

        # 开启清洗任务
        start_result = api.bkdata.start_databus_cleans(
            result_table_id=self.datasource_cleans_table_id_with_biz,
            storages=["kafka"],
            bk_username=self.bkbase_operator,
        )
        logger.info(f"start bkdata databus clean , result: {start_result}")

        etl_status = self._get_etl_status(raw_data_id)

        # 检查清洗状态
        retry = 1
        while etl_status != DataBusStatus.RUNNING:
            if retry > 3:
                raise ValueError(_("开启清洗任务失败"))
            try:
                api.bkdata.start_databus_cleans(result_table_id=self.datasource_cleans_table_id, storages=["kafka"])
                etl_status = self._get_etl_status(raw_data_id)

                logger.warning(f"retry: {retry} start databus clean, status: {etl_status}")
                time.sleep(1)
            except BKAPIError as e:
                logger.exception(f"start databus occur exception: {e}")

            retry += 1

    def _get_etl_status(self, raw_data_id):
        # 获取此raw_data_id当前清洗的状态
        return next(
            (
                i["status"]
                for i in api.bkdata.get_databus_cleans(raw_data_id=raw_data_id, bk_username=self.bkbase_operator)
                if i["processing_id"] == self.datasource_cleans_table_id_with_biz
            ),
            None,
        )

    def _create_deploy(self):
        params = ApmFlow.get_deploy_params(
            self.bk_biz_id,
            self.metric_datasource.bk_data_id,
            self.bkbase_operator,
            self.datasource_name,
            self.description,
            extra_maintainers=[self.application.create_user],
        )

        try:
            result = api.bkdata.access_deploy_plan(**params)
            self.update_config({Config.RAW_DATA_ID: result["raw_data_id"]})
            return result["raw_data_id"]
        except BKAPIError as e:
            raise ValueError(_("APM虚拟指标: 计算平台创建数据源失败 {}").format(e))

    def update_config(self, config):
        if not self.metric_datasource.bk_data_virtual_metric_config:
            self.metric_datasource.bk_data_virtual_metric_config = config
        else:
            self.metric_datasource.bk_data_virtual_metric_config.update(config)
        self.metric_datasource.save()

    def get_config(self, key):
        return self.metric_datasource.bk_data_virtual_metric_config.get(key)
