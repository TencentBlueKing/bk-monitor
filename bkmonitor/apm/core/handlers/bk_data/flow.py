"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
import time
import traceback

from django.conf import settings
from django.utils import timezone
from django.utils.datetime_safe import datetime

from apm.core.handlers.bk_data.constants import FlowStatus
from apm.models import ApmApplication, BkdataFlowConfig
from bkmonitor.dataflow.auth import check_has_permission
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from metadata.models.storage import DataBusStatus


class _BkdataFlowLogger:
    """携带基础信息日志打印"""

    def __init__(self, name, bk_biz_id, app_name, flow_instance_id):
        self.name = name
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.flow_instance_id = flow_instance_id
        self.logger = logging.getLogger("apm")
        self.extra = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "flow_instance_id": self.flow_instance_id,
            "location": self.name,
        }

    def info(self, content):
        self._log(content, self.logger.info)

    def warning(self, content):
        self._log(content, self.logger.warning)

    def exception(self, content):
        self._log(content, self.logger.exception)

    def _log(self, content, func):
        # 需要保证打印日志代码为串行执行 否则会有并发问题
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        flow = BkdataFlowConfig.objects.filter(id=self.flow_instance_id).first()
        # 打印额外信息 便于查找
        flow.process_info.append(f"[INFO] {now} {content}")
        flow.save()
        func(content, extra=self.extra)


class ApmFlow:
    _NAME = None
    _FLOW = None
    _FLOW_TYPE = None

    def __init__(self, bk_biz_id, app_name, data_id, config):
        self.data_id = data_id
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.config = config
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)

        if self.bk_biz_id > 0:
            self.bkdata_bk_biz_id = self.bk_biz_id
        else:
            # 如果为空间业务 数据源接入创建在公共业务中
            self.bkdata_bk_biz_id = settings.BK_DATA_BK_BIZ_ID

        self.flow = BkdataFlowConfig.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()
        if not self.flow:
            self.flow = BkdataFlowConfig.objects.create(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                process_info=[],
                flow_type=self._FLOW_TYPE,
                deploy_bk_biz_id=self.bkdata_bk_biz_id,
            )

        self.logger = _BkdataFlowLogger(self._NAME, self.bk_biz_id, self.app_name, self.flow.id)
        self.logger.info(f"start flow, use bkbase bk_biz_id: {self.bkdata_bk_biz_id}(app bk_biz_id: {self.bk_biz_id})")
        self.application = ApmApplication.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

    @property
    def bkbase_operator(self):
        return settings.APM_APP_BKDATA_OPERATOR

    @classmethod
    def bkbase_maintainer(cls):
        return settings.APM_APP_BKDATA_MAINTAINER

    @property
    def flow_fetch_status_threshold(self):
        return settings.APM_APP_BKDATA_FETCH_STATUS_THRESHOLD

    @property
    def bkbase_project_id(self):
        raise NotImplementedError

    @property
    def deploy_description(self):
        """数据源描述信息"""
        raise NotImplementedError

    @property
    def deploy_name(self):
        """数据源名称"""
        raise NotImplementedError

    @property
    def cleans_names(self):
        """清洗名称"""
        raise NotImplementedError

    @property
    def cleans_description(self):
        """清洗配置描述信息"""
        raise NotImplementedError

    @property
    def cleans_fields(self):
        """清洗字段配置"""
        raise NotImplementedError

    @property
    def cleans_config(self):
        """清洗配置"""
        raise NotImplementedError

    @property
    def cleans_table_id(self):
        """清洗输出表id"""
        raise NotImplementedError

    def flow_instance(self, *args, **kwargs):
        """返回Flow的实例"""
        if not self.flow.databus_clean_result_table_id:
            self._raise_exc(
                "failed to create flow instance, cleans result table id not found", FlowStatus.CONFIG_FLOW_FAILED.value
            )
        return self._FLOW(
            self.flow.databus_clean_result_table_id,
            self.bkdata_bk_biz_id,
            self.app_name,
            self.config,
            *args,
            **kwargs,
        )

    def start(self):
        # Step1: 配置数据源
        self._config_deploy()

        # Step2: 清洗配置
        self._config_cleans()
        self._start_cleans()

        # Step3: 项目授权
        self._auth_project()

        # Step4: 启动Flow
        self._start_flow()

        # Finished: 更新数据库
        self._finished_flow()

    def _finished_flow(self):
        self._update_field({"last_process_time": timezone.now()})
        if not self.flow.is_finished:
            self._update_field(
                {"is_finished": True, "finished_time": timezone.now(), "status": FlowStatus.SUCCESS.value}
            )

    @classmethod
    def _query_access_conf(cls, data_id):
        """获取data_id接入配置"""
        return resource.metadata.query_data_source(bk_data_id=data_id)

    @classmethod
    def _is_diff(cls, a, b, exclude_fields=None):
        a_copy = copy.deepcopy(a)
        b_copy = copy.deepcopy(b)
        if exclude_fields:
            for i in exclude_fields:
                a_copy.pop(i, None)
                b_copy.pop(i, None)

        return count_md5(a_copy) != count_md5(b_copy)

    @classmethod
    def get_deploy_params(cls, bk_biz_id, data_id, operator, name, deploy_description=None, extra_maintainers=None):
        """获取数据源API请求参数(接入方式: KAFKA)"""
        access_conf = cls._query_access_conf(data_id)
        # 数据管理员 = operator + APM默认维护人 + 应用创建者
        maintainers = ",".join(list(set([operator] + cls.bkbase_maintainer() + extra_maintainers or [])))

        return {
            "data_scenario": "queue",
            "bk_biz_id": bk_biz_id,
            "description": deploy_description or name,
            "bk_username": operator,
            "access_raw_data": {
                "raw_data_name": name,
                "maintainer": maintainers,
                "raw_data_alias": name,
                "data_source": "kafka",
                "data_encoding": "UTF-8",
                "sensitivity": "private",
                "description": deploy_description or name,
                "tags": [],
                "data_source_tags": ["src_kafka"],
            },
            "access_conf_info": {
                "collection_model": {"collection_type": "incr", "start_at": 1, "period": "1"},
                "resource": {
                    "type": "kafka",
                    "scope": [
                        {
                            "master": f"{access_conf['mq_config']['cluster_config']['domain_name']}"
                            f":{access_conf['mq_config']['cluster_config']['port']}",
                            "group": f"{access_conf['mq_config']['storage_config']['topic']}_0000",
                            "topic": access_conf["mq_config"]["storage_config"]["topic"],
                            "tasks": access_conf["mq_config"]["storage_config"]["partition"],
                            "use_sasl": access_conf["mq_config"]["cluster_config"]["is_ssl_verify"],
                            "security_protocol": "SASL_PLAINTEXT",
                            "sasl_mechanism": "SCRAM-SHA-512",
                            "user": access_conf["mq_config"]["auth_info"]["username"],
                            "password": access_conf["mq_config"]["auth_info"]["password"],
                        }
                    ],
                },
            },
        }

    def _config_deploy(self):
        """配置数据源"""
        params = self.get_deploy_params(
            self.bkdata_bk_biz_id,
            self.data_id,
            self.bkbase_operator,
            self.deploy_name,
            self.deploy_description,
            extra_maintainers=[self.application.create_user],
        )

        try:
            if self.flow.deploy_data_id:
                if self._is_diff(self.flow.deploy_config, params):
                    self.logger.info("datasource configuration updates!")
                    api.bkdata.update_deploy_plan(raw_data_id=self.flow.deploy_data_id, **params)
                    self._update_field({"deploy_config": params})
                    self.logger.info(
                        f"datasource configuration updates successfully, will use: {self.flow.deploy_data_id}"
                    )
                else:
                    self.logger.info(f"datasource configuration not updates, will use: {self.flow.deploy_data_id}")
            else:
                self.logger.info("flow.deploy_data_id not found, start create")
                raw_data_id = api.bkdata.access_deploy_plan(**params)["raw_data_id"]
                self._update_field({"deploy_config": params, "deploy_data_id": raw_data_id})
                self.logger.info(
                    f"create deploy successfully, "
                    f"raw_data_id: {raw_data_id}(name: {self.deploy_name}) "
                    f"in bkdata-bk_biz_id: {self.bkdata_bk_biz_id}"
                )
        except (BKAPIError, KeyError, CustomException) as e:
            self._raise_exc(f"create deploy failed: {e}", FlowStatus.CONFIG_DEPLOY_FAILED.value, traceback.format_exc())

    def _raise_exc(self, exception, status, stack=None):
        self.logger.exception(f"change status to {status}. error={exception}. stack={stack}")
        self._update_field({"status": status, "last_process_time": timezone.now()})
        raise ValueError(exception)

    def _update_field(self, field_params):
        self.flow = BkdataFlowConfig.objects.update_or_create(id=self.flow.id, defaults=field_params)[0]

    def _config_cleans(self):
        """配置清洗"""
        if not self.flow.deploy_data_id:
            self._raise_exc("deploy data id not found", FlowStatus.CONFIG_CLEANS_FAILED.value)

        params = {
            "bk_biz_id": self.bkdata_bk_biz_id,
            "bk_username": self.bkbase_operator,
            "clean_config_name": self.cleans_names,
            "description": self.cleans_description,
            "fields": self.cleans_fields,
            "json_config": json.dumps(self.cleans_config),
            "raw_data_id": self.flow.deploy_data_id,
            "result_table_name": self.cleans_table_id,
            "result_table_name_alias": self.cleans_table_id,
        }

        try:
            if self.flow.databus_clean_id:
                if self._is_diff(self.flow.databus_clean_config, params, exclude_fields=["result_table_name"]):
                    self.logger.info("databus cleans configuration updates!")
                    api.bkdata.update_databus_cleans(processing_id=self.flow.databus_clean_id, **params)
                    self.logger.info("databus cleans configuration update successfully")
                    self._update_field({"databus_clean_config": params})
            else:
                result = api.bkdata.databus_cleans(**params)
                self.logger.info(f"create databus cleans: {self.cleans_names} successfully, response: {result}")
                self._update_field(
                    {
                        "databus_clean_config": params,
                        "databus_clean_result_table_id": result["result_table_id"],
                        "databus_clean_id": result["id"],
                    }
                )
        except BKAPIError as e:
            self._raise_exc(f"create cleans failed: {e}", FlowStatus.CONFIG_CLEANS_FAILED.value, traceback.format_exc())

    def _start_cleans(self):
        """启动清洗"""

        if not self.flow.databus_clean_result_table_id:
            self._raise_exc("cleans table id not found", FlowStatus.CONFIG_CLEANS_START_FAILED.value)

        etl_status = self._get_etl_status(FlowStatus.CONFIG_CLEANS_START_FAILED.value)
        for i in range(self.flow_fetch_status_threshold):
            if etl_status == DataBusStatus.RUNNING:
                self.logger.info(f"check etl status: {etl_status}, break. loop: {i}")
                break

            try:
                response = api.bkdata.start_databus_cleans(
                    result_table_id=self.flow.databus_clean_result_table_id,
                    storages=["kafka"],
                    bk_username=self.bkbase_operator,
                )
                etl_status = self._get_etl_status(FlowStatus.CONFIG_CLEANS_START_FAILED.value)
                self.logger.info(f"check etl status: {etl_status}, response: {response}, loop: {i}")
                time.sleep(1)
            except BKAPIError as e:
                self.logger.info(f"start databus cleans failed: {e}, loop: {i}")

        if etl_status != DataBusStatus.RUNNING:
            self._raise_exc(
                "failed to start databus cleans, status is not running", FlowStatus.CONFIG_CLEANS_START_FAILED.value
            )

    def _get_etl_status(self, status):
        """获取某个清洗规则的状态"""

        if not self.flow.deploy_data_id:
            self._raise_exc("get etl status failed: deploy data id not found", status)

        return next(
            (
                i["status"]
                for i in api.bkdata.get_databus_cleans(
                    raw_data_id=self.flow.deploy_data_id, bk_username=self.bkbase_operator
                )
                if i["processing_id"] == self.flow.databus_clean_result_table_id
            ),
            None,
        )

    def _auth_project(self):
        self._update_field({"project_id": self.bkbase_project_id})

        if not check_has_permission(self.bkbase_project_id, self.flow.databus_clean_result_table_id):
            self.logger.info(
                f"project id: {self.bkbase_project_id} "
                f"cleans result table id: {self.flow.databus_clean_result_table_id} no permission, "
                f"authorization is required"
            )
            try:
                params = {
                    "project_id": self.bkbase_project_id,
                    "object_id": self.flow.databus_clean_result_table_id,
                    "bk_biz_id": self.bkdata_bk_biz_id,
                }
                response = api.bkdata.auth_result_table(**params)
                self.logger.info(f"auth project successfully, response: {response}")
            except BKAPIError as e:
                self._raise_exc(
                    f"failed to auth project, result_table_id: {self.flow.databus_clean_result_table_id}, error: {e}",
                    FlowStatus.AUTH_FAILED.value,
                )

    def _start_flow(self):
        """配置&启动flow"""

        try:
            flow = self.flow_instance()
            flow.create_flow(project_id=self.bkbase_project_id)
            flow.start_flow()
            self.logger.info(f"start flow successfully, flow_id: {flow.data_flow.flow_id}")
            self._update_field({"flow_id": flow.data_flow.flow_id})
        except Exception as e:  # noqa
            self._raise_exc(
                f"failed to start flow, error: {e}", FlowStatus.CONFIG_FLOW_FAILED.value, traceback.format_exc()
            )
