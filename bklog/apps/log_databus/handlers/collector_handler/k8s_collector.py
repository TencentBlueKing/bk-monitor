"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import copy
import datetime
from typing import Any
from collections import defaultdict
import yaml
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.api import NodeApi, TransferApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import (
    BCS_DEPLOYMENT_TYPE,
)
from apps.log_databus.constants import (
    META_DATA_ENCODING,
    ArchiveInstanceType,
    ContainerCollectorType,
    ContainerCollectStatus,
    Environment,
    ETLProcessorChoices,
    TopoType,
    WorkLoadType,
    RETRIEVE_CHAIN,
)
from apps.log_databus.exceptions import (
    AllNamespaceNotAllowedException,
    CollectorActiveException,
    CollectorBkDataNameDuplicateException,
    CollectorConfigNameDuplicateException,
    CollectorConfigNameENDuplicateException,
    CollectorResultTableIDDuplicateException,
    ContainerCollectConfigValidateYamlException,
    PublicESClusterNotExistException,
    RuleCollectorException,
)
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom
from apps.log_databus.handlers.collector_scenario.utils import (
    convert_filters_to_collector_condition,
    deal_collector_scenario_param,
)
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.collector_handler.base_collector import (
    BaseCollectorHandler,
    get_data_link_id,
    get_random_public_cluster_id,
    build_bk_data_name,
    build_result_table_id,
)
from apps.log_databus.models import (
    ArchiveConfig,
    BcsRule,
    CollectorConfig,
    CollectorPlugin,
    ContainerCollectorConfig,
)
from apps.log_databus.serializers import ContainerCollectorYamlSerializer
from apps.log_databus.tasks.bkdata import async_create_bkdata_data_id
from apps.log_search.constants import (
    CollectorScenarioEnum,
    CustomTypeEnum,
)
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import (
    IndexSetTag,
    LogIndexSet,
)
from apps.models import model_to_dict
from apps.utils.bcs import Bcs
from apps.utils.function import map_if
from apps.utils.local import get_request_username
from apps.utils.log import logger


class K8sCollectorHandler(BaseCollectorHandler):
    # 统一调用
    def add_container_configs(self, collector_config, context):
        """
        add_container_configs
        @param collector_config:
        @param context:
        @return:
        """
        container_configs = []
        for config in ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id):
            container_configs.append(model_to_dict(config))

        collector_config["configs"] = container_configs
        return collector_config

    def retrieve(self, use_request=True):
        """
        获取采集配置
        @param use_request:
        @return:
        """
        context = self._multi_info_get(use_request)
        collector_config = model_to_dict(self.data)
        for process in RETRIEVE_CHAIN:
            collector_config = getattr(self, process, lambda x, y: x)(collector_config, context)
            logger.info(f"[databus retrieve] process => [{process}] collector_config => [{collector_config}]")
        if self.data.table_id:
            result_table = TransferApi.get_result_table({"table_id": self.data.table_id})
            alias_dict = result_table.get("query_alias_settings", dict())
            if alias_dict:
                collector_config.update({"alias_settings": alias_dict})

        # 添加索引集相关信息
        log_index_set_obj = LogIndexSet.objects.filter(collector_config_id=self.collector_config_id).first()
        if log_index_set_obj:
            collector_config.update(
                {"sort_fields": log_index_set_obj.sort_fields, "target_fields": log_index_set_obj.target_fields}
            )

        return collector_config

    # 接口调用 自定义上报-更新自定义采集配置-里面有self.retrieve()必须要放这里
    def custom_update(
        self,
        collector_config_name=None,
        category_id=None,
        description=None,
        etl_config=None,
        etl_params=None,
        fields=None,
        storage_cluster_id=None,
        retention=7,
        allocation_min_days=0,
        storage_replies=1,
        es_shards=settings.ES_SHARDS,
        is_display=True,
        sort_fields=None,
        target_fields=None,
    ):
        collector_config_update = {
            "collector_config_name": collector_config_name,
            "category_id": category_id,
            "description": description or collector_config_name,
            "is_display": is_display,
        }

        _collector_config_name = self.data.collector_config_name
        bk_data_name = build_bk_data_name(
            bk_biz_id=self.data.get_bk_biz_id(), collector_config_name_en=self.data.collector_config_name_en
        )
        if self.data.bk_data_id and self.data.bk_data_name != bk_data_name:
            TransferApi.modify_data_id({"data_id": self.data.bk_data_id, "data_name": bk_data_name})
            self.data.bk_data_name = bk_data_name
            logger.info(
                "[modify_data_name] bk_data_id=>{}, data_name {}=>{}".format(
                    self.data.bk_data_id, self.data.bk_data_name, bk_data_name
                )
            )

        for key, value in collector_config_update.items():
            setattr(self.data, key, value)
        try:
            self.data.save()
        except IntegrityError:
            logger.warning(f"collector config name duplicate => [{collector_config_name}]")
            raise CollectorConfigNameDuplicateException()

        # collector_config_name更改后更新索引集名称
        if _collector_config_name != self.data.collector_config_name and self.data.index_set_id:
            index_set_name = _("[采集项]") + self.data.collector_config_name
            LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).update(index_set_name=index_set_name)

        custom_config = get_custom(self.data.custom_type)
        if etl_params and fields:
            # 1. 传递了清洗参数，则优先级最高
            etl_params, etl_config, fields = etl_params, etl_config, fields
        elif self.data.etl_config:
            # 2. 如果本身配置过清洗，则直接使用
            collector_detail = self.retrieve()
            # need drop built in field
            collector_detail["fields"] = map_if(
                collector_detail["fields"], if_func=lambda field: not field["is_built_in"]
            )
            etl_params = collector_detail["etl_params"]
            etl_config = collector_detail["etl_config"]
            fields = collector_detail["fields"]
        else:
            # 3. 默认清洗规则，根据自定义类型来
            etl_params = custom_config.etl_params
            etl_config = custom_config.etl_config
            fields = custom_config.fields

        # 仅在传入集群ID时更新
        if storage_cluster_id:
            from apps.log_databus.handlers.etl import EtlHandler

            etl_handler = EtlHandler.get_instance(self.data.collector_config_id)
            etl_params = {
                "table_id": self.data.collector_config_name_en,
                "storage_cluster_id": storage_cluster_id,
                "retention": retention,
                "es_shards": es_shards,
                "allocation_min_days": allocation_min_days,
                "storage_replies": storage_replies,
                "etl_params": etl_params,
                "etl_config": etl_config,
                "fields": fields,
                "sort_fields": sort_fields,
                "target_fields": target_fields,
            }
            etl_handler.update_or_create(**etl_params)

        custom_config.after_hook(self.data)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.UPDATE,
            "params": model_to_dict(self.data, exclude=["deleted_at", "created_at", "updated_at"]),
        }
        user_operation_record.delay(operation_record)

    @transaction.atomic
    def destroy(self, **kwargs):
        """
        删除采集配置
        :return: task_id
        """
        # 1. 重新命名采集项名称
        collector_config_name = (
            self.data.collector_config_name + "_delete_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        )

        # 2. 停止采集（删除配置文件）
        self.stop()

        ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id).delete()

        # 3. 节点管理-删除订阅配置
        self._delete_subscription()

        # 4. 删除索引集
        if self.data.index_set_id:
            index_set_handler = IndexSetHandler(index_set_id=self.data.index_set_id)
            index_set_handler.delete(self.data.collector_config_name)

        # 5. 删除CollectorConfig记录
        self.data.collector_config_name = collector_config_name
        self.data.save()
        self.data.delete()

        # 6. 删除META采集项：直接重命名采集项名称
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=self.data.collector_scenario_id)
        if self.data.bk_data_id:
            collector_scenario.delete_data_id(self.data.bk_data_id, collector_config_name)

        # 7. 如果存在归档使用了当前采集项, 则删除归档
        qs = ArchiveConfig.objects.filter(
            instance_id=self.data.collector_config_id, instance_type=ArchiveInstanceType.COLLECTOR_CONFIG.value
        )
        if qs.exists():
            qs.delete()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.DESTROY,
            "params": "",
        }
        user_operation_record.delay(operation_record)

        return True

    @transaction.atomic
    def start(self, **kwargs):
        """
        启动采集配置
        :return: task_id
        """
        self._itsm_start_judge()

        self.data.is_active = True
        self.data.save()

        # 启用采集项
        if self.data.index_set_id:
            index_set_handler = IndexSetHandler(self.data.index_set_id)
            index_set_handler.start()

        # 创建容器采集配置
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id)
        for container_config in container_configs:
            self.create_container_release(container_config)

        # 启动节点管理订阅功能
        if self.data.subscription_id:
            NodeApi.switch_subscription({"subscription_id": self.data.subscription_id, "action": "enable"})

        # 存在RT则启用RT
        if self.data.table_id:
            _, table_id = self.data.table_id.split(".")  # pylint: disable=unused-variable
            etl_storage = EtlStorage.get_instance(self.data.etl_config)
            etl_storage.switch_result_table(collector_config=self.data, is_enable=True)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.START,
            "params": "",
        }
        user_operation_record.delay(operation_record)

        if self.data.subscription_id:
            return self._run_subscription_task()
        return True

    @transaction.atomic
    def stop(self, **kwargs):
        """
        停止采集配置
        :return: task_id
        """
        self.data.is_active = False
        self.data.save()

        # 停止采集项
        if self.data.index_set_id:
            index_set_handler = IndexSetHandler(self.data.index_set_id)
            index_set_handler.stop()

        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id)
        for container_config in container_configs:
            self.delete_container_release(container_config)

        if self.data.subscription_id:
            # 停止节点管理订阅功能
            NodeApi.switch_subscription({"subscription_id": self.data.subscription_id, "action": "disable"})

        # 存在RT则停止RT
        if self.data.table_id:
            _, table_id = self.data.table_id.split(".")  # pylint: disable=unused-variable
            etl_storage = EtlStorage.get_instance(self.data.etl_config)
            etl_storage.switch_result_table(collector_config=self.data, is_enable=False)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.STOP,
            "params": "",
        }
        user_operation_record.delay(operation_record)

        if self.data.subscription_id:
            return self._run_subscription_task("STOP")
        return True

    def retry_instances(self, instance_id_list):
        return self.retry_container_collector(instance_id_list)

    def get_task_status(self, id_list):
        return self.get_container_collect_status(container_collector_config_id_list=id_list)

    def get_subscription_status(self):
        """
        查看订阅的插件运行状态
        :return:
        """
        # 容器采集特殊处理
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.data.collector_config_id)

        contents = []
        for container_config in container_configs:
            contents.append({"status": container_config.status, "container_collector_config_id": container_config.id})
        return {
            "contents": [
                {
                    "collector_config_id": self.data.collector_config_id,
                    "collector_config_name": self.data.collector_config_name,
                    "child": contents,
                }
            ]
        }

    def get_container_collect_status(self, container_collector_config_id_list):
        """
        查询容器采集任务状态
        """
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.data.collector_config_id)
        if container_collector_config_id_list:
            container_configs = container_configs.filter(id__in=container_collector_config_id_list)

        contents = []
        for container_config in container_configs:
            contents.append(
                {
                    "message": container_config.status_detail,
                    "status": container_config.status,
                    "container_collector_config_id": container_config.id,
                    "name": self.generate_bklog_config_name(container_config.id),
                }
            )
        return {
            "contents": [
                {
                    "collector_config_id": self.data.collector_config_id,
                    "collector_config_name": self.data.collector_config_name,
                    "child": contents,
                }
            ]
        }

    # 类内调用和接口调用
    def update_container_config(self, data):
        bk_biz_id = data["bk_biz_id"]
        collector_config_update = {
            "collector_config_name": data["collector_config_name"],
            "description": data["description"] or data["collector_config_name"],
            "environment": Environment.CONTAINER,
            "collector_scenario_id": data["collector_scenario_id"],
            "bcs_cluster_id": data["bcs_cluster_id"],
            "add_pod_label": data["add_pod_label"],
            "add_pod_annotation": data["add_pod_annotation"],
            "extra_labels": data["extra_labels"],
            "yaml_config_enabled": data["yaml_config_enabled"],
            "yaml_config": data["yaml_config"],
        }

        if data["yaml_config_enabled"]:
            # yaml 模式，先反序列化解出来，覆盖到config字段上面
            validate_result = self.validate_container_config_yaml(
                bk_biz_id, data["bcs_cluster_id"], data["yaml_config"]
            )
            if not validate_result["parse_status"]:
                raise ContainerCollectConfigValidateYamlException()
            data["configs"] = validate_result["parse_result"]["configs"]

        # 效验共享集群命名空间是否在允许的范围
        for config in data["configs"]:
            if config.get("namespaces"):
                self.check_cluster_config(
                    bk_biz_id=bk_biz_id,
                    collector_type=config["collector_type"],
                    bcs_cluster_id=data["bcs_cluster_id"],
                    namespace_list=config["namespaces"],
                )

        _collector_config_name = self.data.collector_config_name
        for key, value in collector_config_update.items():
            setattr(self.data, key, value)

        try:
            self.data.save()
        except IntegrityError:
            logger.warning(f"collector config name duplicate => [{data['collector_config_name']}]")
            raise CollectorConfigNameDuplicateException()

        # collector_config_name更改后更新索引集名称
        if _collector_config_name != self.data.collector_config_name and self.data.index_set_id:
            index_set_name = _("[采集项]") + self.data.collector_config_name
            LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).update(index_set_name=index_set_name)

        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.UPDATE,
            "params": model_to_dict(self.data, exclude=["deleted_at", "created_at", "updated_at"]),
        }
        user_operation_record.delay(operation_record)
        self.compare_config(data=data, collector_config_id=self.data.collector_config_id)

        self.data.task_id_list = list(
            ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id).values_list(
                "id", flat=True
            )
        )
        self.data.save()

        return {
            "collector_config_id": self.data.collector_config_id,
            "index_set_id": self.data.index_set_id,
            "bk_data_id": self.data.bk_data_id,
        }

    # 接口调用
    def fast_contain_update(self, params: dict) -> dict:
        if self.data and not self.data.is_active:
            raise CollectorActiveException()
        # 补充缺少的清洗配置参数
        params.setdefault("fields", [])
        # 更新采集项
        self.update_container_config(params)
        params["table_id"] = self.data.collector_config_name_en
        self.create_or_update_clean_config(True, params)
        return {"collector_config_id": self.data.collector_config_id}

    # 类内调用和接口调用
    def create_container_config(self, data):
        # 使用采集插件补全参数
        collector_plugin_id = data.get("collector_plugin_id")
        if collector_plugin_id:
            from apps.log_databus.handlers.collector_plugin.base import (
                CollectorPluginHandler,
                get_collector_plugin_handler,
            )

            collector_plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
            plugin_handler: CollectorPluginHandler = get_collector_plugin_handler(
                collector_plugin.etl_processor, collector_plugin_id
            )
            data = plugin_handler.build_instance_params(data)
        data_link_id = int(data.get("data_link_id") or 0)
        data_link_id = get_data_link_id(bk_biz_id=data["bk_biz_id"], data_link_id=data_link_id)
        collector_config_params = {
            "bk_biz_id": data["bk_biz_id"],
            "collector_config_name": data["collector_config_name"],
            "collector_config_name_en": data["collector_config_name_en"],
            "collector_scenario_id": data["collector_scenario_id"],
            "custom_type": CustomTypeEnum.LOG.value,
            "category_id": data["category_id"],
            "description": data["description"] or data["collector_config_name"],
            "data_link_id": int(data_link_id),
            "environment": Environment.CONTAINER,
            "bcs_cluster_id": data["bcs_cluster_id"],
            "add_pod_label": data["add_pod_label"],
            "add_pod_annotation": data["add_pod_annotation"],
            "extra_labels": data["extra_labels"],
            "yaml_config_enabled": data["yaml_config_enabled"],
            "yaml_config": data["yaml_config"],
            "bkdata_biz_id": data.get("bkdata_biz_id"),
            "collector_plugin_id": collector_plugin_id,
            "is_display": data.get("is_display", True),
            "etl_processor": data.get("etl_processor", ETLProcessorChoices.TRANSFER.value),
        }
        bkdata_biz_id = data.get("bkdata_biz_id") or data["bk_biz_id"]
        if self._pre_check_collector_config_en(model_fields=collector_config_params, bk_biz_id=bkdata_biz_id):
            logger.error(
                "collector_config_name_en {collector_config_name_en} already exists".format(
                    collector_config_name_en=data["collector_config_name_en"]
                )
            )
            raise CollectorConfigNameENDuplicateException(
                CollectorConfigNameENDuplicateException.MESSAGE.format(
                    collector_config_name_en=data["collector_config_name_en"]
                )
            )
        # 判断是否已存在同bk_data_name, result_table_id
        bk_data_name = build_bk_data_name(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=data["collector_config_name_en"]
        )
        result_table_id = build_result_table_id(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=data["collector_config_name_en"]
        )
        if self._pre_check_bk_data_name(model_fields=collector_config_params, bk_data_name=bk_data_name):
            logger.error(f"bk_data_name {bk_data_name} already exists")
            raise CollectorBkDataNameDuplicateException(
                CollectorBkDataNameDuplicateException.MESSAGE.format(bk_data_name=bk_data_name)
            )
        if self._pre_check_result_table_id(model_fields=collector_config_params, result_table_id=result_table_id):
            logger.error(f"result_table_id {result_table_id} already exists")
            raise CollectorResultTableIDDuplicateException(
                CollectorResultTableIDDuplicateException.MESSAGE.format(result_table_id=result_table_id)
            )

        with transaction.atomic():
            try:
                self.data = CollectorConfig.objects.create(**collector_config_params)
            except IntegrityError:
                logger.warning(f"collector config name duplicate => [{data['collector_config_name']}]")
                raise CollectorConfigNameDuplicateException()

            if self.data.yaml_config_enabled:
                # yaml 模式，先反序列化解出来，再保存
                result = self.validate_container_config_yaml(
                    data["bk_biz_id"], data["bcs_cluster_id"], self.data.yaml_config
                )
                if not result["parse_status"]:
                    raise ContainerCollectConfigValidateYamlException()
                container_configs = result["parse_result"]["configs"]
            else:
                # 效验共享集群命名空间是否在允许的范围
                for config in data["configs"]:
                    if config.get("namespaces"):
                        self.check_cluster_config(
                            bk_biz_id=data["bk_biz_id"],
                            collector_type=config["collector_type"],
                            bcs_cluster_id=data["bcs_cluster_id"],
                            namespace_list=config["namespaces"],
                        )

                # 原生模式，直接通过结构化数据生成
                container_configs = data["configs"]

            ContainerCollectorConfig.objects.bulk_create(
                ContainerCollectorConfig(
                    collector_config_id=self.data.collector_config_id,
                    collector_type=config["collector_type"],
                    namespaces=config["namespaces"],
                    namespaces_exclude=config["namespaces_exclude"],
                    any_namespace=not any([config["namespaces"], config["namespaces_exclude"]]),
                    data_encoding=config["data_encoding"],
                    params=config["params"],
                    workload_type=config["container"]["workload_type"],
                    workload_name=config["container"]["workload_name"],
                    container_name=config["container"]["container_name"],
                    container_name_exclude=config["container"]["container_name_exclude"],
                    match_labels=config["label_selector"]["match_labels"],
                    match_expressions=config["label_selector"]["match_expressions"],
                    match_annotations=config["annotation_selector"]["match_annotations"],
                    all_container=not any(
                        [
                            config["container"]["workload_type"],
                            config["container"]["workload_name"],
                            config["container"]["container_name"],
                            config["container"]["container_name_exclude"],
                            config["label_selector"]["match_labels"],
                            config["label_selector"]["match_expressions"],
                            config["annotation_selector"]["match_annotations"],
                        ]
                    ),
                    # yaml 原始配置，如果启用了yaml，则把解析后的原始配置保存下来用于下发
                    raw_config=config.get("raw_config") if self.data.yaml_config_enabled else None,
                )
                for config in container_configs
            )

            collector_scenario = CollectorScenario.get_instance(CollectorScenarioEnum.CUSTOM.value)
            self.data.bk_data_id = collector_scenario.update_or_create_data_id(
                bk_data_id=self.data.bk_data_id,
                data_link_id=self.data.data_link_id,
                data_name=build_bk_data_name(self.data.get_bk_biz_id(), data["collector_config_name_en"]),
                description=collector_config_params["description"],
                encoding=META_DATA_ENCODING,
            )
            self.data.task_id_list = list(
                ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id).values_list(
                    "id", flat=True
                )
            )

            self.data.save()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.CREATE,
            "params": model_to_dict(self.data, exclude=["deleted_at", "created_at", "updated_at"]),
        }
        user_operation_record.delay(operation_record)

        self._authorization_collector(self.data)
        # 创建数据平台data_id
        # 兼容平台账号
        async_create_bkdata_data_id.delay(self.data.collector_config_id, data.get("platform_username"))

        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.data.collector_config_id)
        for config in container_configs:
            self.create_container_release(config)
        return {
            "collector_config_id": self.data.collector_config_id,
            "collector_config_name": self.data.collector_config_name,
            "bk_data_id": self.data.bk_data_id,
            "subscription_id": self.data.subscription_id,
            "task_id_list": self.data.task_id_list,
        }

    # 接口调用
    def fast_contain_create(self, params: dict) -> dict:
        # 补充缺少的容器参数
        container_configs = params["configs"]
        for container_config in container_configs:
            if not container_config.get("container"):
                container_config["container"] = {
                    "workload_type": "",
                    "workload_name": "",
                    "container_name": "",
                    "container_name_exclude": "",
                }
            if not container_config.get("data_encoding"):
                container_config["data_encoding"] = "UTF-8"

            if not container_config.get("label_selector"):
                container_config["label_selector"] = {"match_labels": [], "match_expressions": []}
            if not container_config["params"].get("conditions", {}).get("type"):
                container_config["params"]["conditions"] = {"type": "none"}
        # 补充缺少的清洗配置参数
        if not params.get("fields"):
            params["fields"] = []
        # 如果没传入集群ID, 则随机给一个公共集群
        if not params.get("storage_cluster_id"):
            storage_cluster_id = get_random_public_cluster_id(bk_biz_id=params["bk_biz_id"])
            if not storage_cluster_id:
                raise PublicESClusterNotExistException()
            params["storage_cluster_id"] = storage_cluster_id
        # 如果没传入数据链路ID, 则按照优先级选取一个集群ID
        data_link_id = int(params.get("data_link_id") or 0)
        params["data_link_id"] = get_data_link_id(bk_biz_id=params["bk_biz_id"], data_link_id=data_link_id)
        # 创建采集项
        self.create_container_config(params)
        params["table_id"] = params["collector_config_name_en"]
        index_set_id = self.create_or_update_clean_config(False, params).get("index_set_id", 0)
        self.send_create_notify(self.data)
        return {
            "collector_config_id": self.data.collector_config_id,
            "bk_data_id": self.data.bk_data_id,
            "subscription_id": self.data.subscription_id,
            "task_id_list": self.data.task_id_list,
            "index_set_id": index_set_id,
        }

    @classmethod
    def format_bcs_container_config(
        cls, collector_config: CollectorConfig, container_config: ContainerCollectorConfig
    ) -> dict[str, Any]:
        enable_stdout = container_config.collector_type == ContainerCollectorType.STDOUT
        return {
            "created_by": collector_config.created_by,
            "updated_by": collector_config.updated_by,
            "created_at": collector_config.created_at,
            "updated_at": collector_config.updated_at,
            "rule_id": collector_config.rule_id,
            "collector_config_name": collector_config.collector_config_name,
            "bk_biz_id": collector_config.bk_biz_id,
            "description": collector_config.description,
            "collector_config_name_en": collector_config.collector_config_name_en,
            "environment": collector_config.environment,
            "bcs_cluster_id": collector_config.bcs_cluster_id,
            "extra_labels": collector_config.extra_labels,
            "add_pod_label": collector_config.add_pod_label,
            "rule_file_index_set_id": None,
            "rule_std_index_set_id": None,
            "file_index_set_id": collector_config.index_set_id
            if not enable_stdout
            else None,  # TODO: 兼容代码4.8需删除
            "std_index_set_id": collector_config.index_set_id if enable_stdout else None,  # TODO: 兼容代码4.8需删除
            "container_config": [
                {
                    "id": container_config.id,
                    "bk_data_id": collector_config.bk_data_id if not enable_stdout else None,
                    "bkdata_data_id": collector_config.bkdata_data_id if not enable_stdout else None,
                    "namespaces": container_config.namespaces,
                    "any_namespace": container_config.any_namespace,
                    "data_encoding": container_config.data_encoding,
                    "params": container_config.params,
                    "container": {
                        "workload_type": container_config.workload_type,
                        "workload_name": container_config.workload_name,
                        "container_name": container_config.container_name,
                    },
                    "label_selector": {
                        "match_labels": container_config.match_labels,
                        "match_expressions": container_config.match_expressions,
                    },
                    "annotation_selector": {
                        "match_annotations": container_config.match_annotations,
                    },
                    "all_container": container_config.all_container,
                    "status": container_config.status,
                    "status_detail": container_config.status_detail,
                    "enable_stdout": enable_stdout,
                    "stdout_conf": {
                        "bk_data_id": collector_config.bk_data_id if enable_stdout else None,
                        "bkdata_data_id": collector_config.bkdata_data_id if enable_stdout else None,
                    },
                }
            ],
        }

    # 接口调用
    @classmethod
    def list_bcs_collector_without_rule(cls, bcs_cluster_id: str, bk_biz_id: int):
        """
        该函数是为了获取容器采集项, 但是不是通过BCS规则创建的采集项
        """
        # 通用函数, 获取非BCS创建的容器采集项, 以及对应容器采集的map
        queryset = CollectorConfig.objects.filter(
            rule_id=0,
            environment=Environment.CONTAINER,
            bk_biz_id=bk_biz_id,
            bcs_cluster_id=bcs_cluster_id,
            # 过滤掉未完成的采集项, 因为未完成的采集项table_id会为空
            table_id__isnull=False,
        )
        collectors = queryset.all()
        # 获取采集项对应的容器采集配置
        container_collector_configs = ContainerCollectorConfig.objects.filter(
            collector_config_id__in=list(collectors.values_list("collector_config_id", flat=True)),
            collector_type__in=[ContainerCollectorType.CONTAINER, ContainerCollectorType.STDOUT],
        ).all()
        container_config_map: dict[int, ContainerCollectorConfig] = {
            c.collector_config_id: c for c in container_collector_configs
        }
        return [
            cls.format_bcs_container_config(
                collector_config=collector, container_config=container_config_map[collector.collector_config_id]
            )
            for collector in collectors
            if collector.collector_config_id in container_config_map
        ]

    # 接口调用
    @transaction.atomic
    def create_bcs_container_config(self, data, bk_app_code="bk_bcs"):
        conf = self.get_bcs_config(
            bk_biz_id=data["bk_biz_id"],
            bcs_cluster_id=data["bcs_cluster_id"],
            storage_cluster_id=data.get("storage_cluster_id"),
        )
        bcs_collector_config_name = self.generate_collector_config_name(
            bcs_cluster_id=data["bcs_cluster_id"],
            collector_config_name=data["collector_config_name"],
            collector_config_name_en=data["collector_config_name_en"],
        )
        bcs_rule = BcsRule.objects.create(rule_name=data["collector_config_name"], bcs_project_id=data["project_id"])

        # 默认设置为空,做为一个标识
        path_collector_config = std_collector_config = ""
        parent_container_config_id = 0
        # 注入索引集标签
        tag_id = IndexSetTag.get_tag_id(data["bcs_cluster_id"])
        is_send_create_notify = False
        for config in data["config"]:
            if config["paths"]:
                # 创建路径采集项
                path_collector_config = self.create_bcs_collector(
                    {
                        "bk_biz_id": data["bk_biz_id"],
                        "collector_config_name": bcs_collector_config_name["bcs_path_collector"][
                            "collector_config_name"
                        ],
                        "collector_config_name_en": bcs_collector_config_name["bcs_path_collector"][
                            "collector_config_name_en"
                        ],
                        "collector_scenario_id": CollectorScenarioEnum.ROW.value,
                        "custom_type": data["custom_type"],
                        "category_id": data["category_id"],
                        "description": data["description"],
                        "data_link_id": int(conf["data_link_id"]),
                        "bk_app_code": bk_app_code,
                        "environment": Environment.CONTAINER,
                        "bcs_cluster_id": data["bcs_cluster_id"],
                        "add_pod_label": data["add_pod_label"],
                        "extra_labels": data["extra_labels"],
                        "rule_id": bcs_rule.id,
                    },
                    conf=conf,
                    async_bkdata=False,
                )
                is_send_create_notify = True
                # 注入索引集标签
                IndexSetHandler(path_collector_config.index_set_id).add_tag(tag_id=tag_id)

            if config["enable_stdout"]:
                # 创建标准输出采集项
                std_collector_config = self.create_bcs_collector(
                    {
                        "bk_biz_id": data["bk_biz_id"],
                        "collector_config_name": bcs_collector_config_name["bcs_std_collector"][
                            "collector_config_name"
                        ],
                        "collector_config_name_en": bcs_collector_config_name["bcs_std_collector"][
                            "collector_config_name_en"
                        ],
                        "collector_scenario_id": CollectorScenarioEnum.ROW.value,
                        "custom_type": data["custom_type"],
                        "category_id": data["category_id"],
                        "description": data["description"],
                        "data_link_id": int(conf["data_link_id"]),
                        "bk_app_code": bk_app_code,
                        "environment": Environment.CONTAINER,
                        "bcs_cluster_id": data["bcs_cluster_id"],
                        "add_pod_label": data["add_pod_label"],
                        "extra_labels": data["extra_labels"],
                        "rule_id": bcs_rule.id,
                    },
                    conf=conf,
                    async_bkdata=False,
                )
                # 注入索引集标签
                IndexSetHandler(std_collector_config.index_set_id).add_tag(tag_id=tag_id)
                # 获取父配置id
                collector_config_obj = CollectorConfig.objects.filter(
                    rule_id=bcs_rule.id,
                    collector_config_name_en=bcs_collector_config_name["bcs_path_collector"][
                        "collector_config_name_en"
                    ],
                ).first()
                if collector_config_obj:
                    parent_container_config_id = collector_config_obj.collector_config_id

        container_collector_config_list = []
        for config in data["config"]:
            workload_type = config["container"].get("workload_type", "")
            workload_name = config["container"].get("workload_name", "")
            container_name = config["container"].get("container_name", "")
            match_labels = config["label_selector"].get("match_labels", [])
            match_expressions = config["label_selector"].get("match_expressions", [])
            match_annotations = config["annotation_selector"].get("match_annotations", [])

            is_all_container = not any(
                [workload_type, workload_name, container_name, match_labels, match_expressions, match_annotations]
            )

            if config["paths"]:
                # 配置了文件路径才需要下发路径采集
                container_collector_config_list.append(
                    ContainerCollectorConfig(
                        collector_config_id=path_collector_config.collector_config_id,
                        collector_type=ContainerCollectorType.CONTAINER,
                        namespaces=config["namespaces"],
                        any_namespace=not config["namespaces"],
                        data_encoding=config["data_encoding"],
                        params={
                            "paths": config["paths"],
                            "conditions": config["conditions"]
                            if config.get("conditions")
                            else {"type": "match", "match_type": "include", "match_content": ""},
                            **config.get("multiline", {}),
                        },
                        workload_type=workload_type,
                        workload_name=workload_name,
                        container_name=container_name,
                        match_labels=match_labels,
                        match_expressions=match_expressions,
                        match_annotations=match_annotations,
                        all_container=is_all_container,
                        rule_id=bcs_rule.id,
                    )
                )

            if config["enable_stdout"]:
                container_collector_config_list.append(
                    ContainerCollectorConfig(
                        collector_config_id=std_collector_config.collector_config_id,
                        collector_type=ContainerCollectorType.STDOUT,
                        namespaces=config["namespaces"],
                        any_namespace=not config["namespaces"],
                        data_encoding=config["data_encoding"],
                        params={
                            "paths": [],
                            "conditions": config["conditions"]
                            if config.get("conditions")
                            else {"type": "match", "match_type": "include", "match_content": ""},
                            **config.get("multiline", {}),
                        },
                        workload_type=workload_type,
                        workload_name=workload_name,
                        container_name=container_name,
                        match_labels=match_labels,
                        match_expressions=match_expressions,
                        match_annotations=match_annotations,
                        all_container=is_all_container,
                        rule_id=bcs_rule.id,
                        parent_container_config_id=parent_container_config_id,
                    )
                )

        ContainerCollectorConfig.objects.bulk_create(container_collector_config_list)

        if is_send_create_notify:
            self.send_create_notify(path_collector_config)

        return {
            "rule_id": bcs_rule.id,
            "rule_file_index_set_id": path_collector_config.index_set_id if path_collector_config else 0,
            "rule_file_collector_config_id": path_collector_config.collector_config_id if path_collector_config else 0,
            "rule_std_index_set_id": std_collector_config.index_set_id if std_collector_config else 0,
            "rule_std_collector_config_id": std_collector_config.collector_config_id if std_collector_config else 0,
            "file_index_set_id": path_collector_config.index_set_id
            if path_collector_config
            else 0,  # TODO: 兼容代码4.8需删除
            "std_index_set_id": std_collector_config.index_set_id
            if std_collector_config
            else 0,  # TODO: 兼容代码4.8需删除
            "bk_data_id": path_collector_config.bk_data_id if path_collector_config else 0,
            "stdout_conf": {"bk_data_id": std_collector_config.bk_data_id if std_collector_config else 0},
        }

    # 接口调用
    @staticmethod
    def sync_bcs_container_bkdata_id(data: dict[str, Any]):
        """同步bcs容器采集项bkdata_id"""
        if data["rule_file_collector_config_id"]:
            async_create_bkdata_data_id.delay(data["rule_file_collector_config_id"])
        if data["rule_std_collector_config_id"]:
            async_create_bkdata_data_id.delay(data["rule_std_collector_config_id"])

    # 接口调用
    def sync_bcs_container_task(self, data: dict[str, Any]):
        """
        同步bcs容器采集项任务
        需要在create_bcs_container_config函数执行之后运行
        因为create_bcs_container_config函数在事务里, 异步任务可能会执行失败, 需要在事务完成之后单独执行
        """
        file_collector_config_id = data["rule_file_collector_config_id"]
        std_collector_config_id = data["rule_std_collector_config_id"]
        for collector_config_id in [file_collector_config_id, std_collector_config_id]:
            if not collector_config_id:
                continue
            collector_config = CollectorConfig.objects.filter(
                collector_config_id=collector_config_id,
            ).first()
            if not collector_config:
                continue
            container_config = ContainerCollectorConfig.objects.filter(
                collector_config_id=collector_config_id,
            ).first()
            if not container_config:
                continue
            self.deal_self_call(
                collector_config_id=collector_config.collector_config_id,
                collector=collector_config,
                func=self.create_container_release,
                container_config=container_config,
            )

    # 接口调用
    @transaction.atomic
    def update_bcs_container_config(self, data, rule_id, bk_app_code="bk_bcs"):
        conf = self.get_bcs_config(
            bk_biz_id=data["bk_biz_id"],
            bcs_cluster_id=data["bcs_cluster_id"],
            storage_cluster_id=data.get("storage_cluster_id"),
        )
        bcs_collector_config_name = self.generate_collector_config_name(
            bcs_cluster_id=data["bcs_cluster_id"],
            collector_config_name=data["collector_config_name"],
            collector_config_name_en=data["collector_config_name_en"],
        )
        bcs_path_collector_config_name_en = bcs_collector_config_name["bcs_path_collector"]["collector_config_name_en"]
        bcs_std_collector_config_name_en = bcs_collector_config_name["bcs_std_collector"]["collector_config_name_en"]

        # 默认设置为空,做为一个标识
        path_collector = std_collector = None
        path_collector_config = std_collector_config = None
        # 注入索引集标签
        tag_id = IndexSetTag.get_tag_id(data["bcs_cluster_id"])
        is_send_path_create_notify = is_send_std_create_notify = False
        # 容器配置是否创建标识
        is_exist_bcs_path = False
        is_exist_bcs_std = False
        for config in data["config"]:
            collector_config_name_en_list = CollectorConfig.objects.filter(
                rule_id=rule_id,
                collector_config_name_en__in=[bcs_path_collector_config_name_en, bcs_std_collector_config_name_en],
            ).values_list("collector_config_name_en", flat=True)

            for collector_config_name_en in collector_config_name_en_list:
                if collector_config_name_en.endswith("_path"):
                    is_exist_bcs_path = True
                elif collector_config_name_en.endswith("_std"):
                    is_exist_bcs_std = True

            # 如果还没有创建容器配置，那么当config["paths"]或config["enable_stdout"]存在时需要创建容器配置
            if config["paths"] and not is_exist_bcs_path:
                # 创建路径采集项
                path_collector_config = self.create_bcs_collector(
                    {
                        "bk_biz_id": data["bk_biz_id"],
                        "collector_config_name": bcs_collector_config_name["bcs_path_collector"][
                            "collector_config_name"
                        ],
                        "collector_config_name_en": bcs_collector_config_name["bcs_path_collector"][
                            "collector_config_name_en"
                        ],
                        "collector_scenario_id": CollectorScenarioEnum.ROW.value,
                        "custom_type": data["custom_type"],
                        "category_id": data["category_id"],
                        "description": data["description"],
                        "data_link_id": int(conf["data_link_id"]),
                        "bk_app_code": bk_app_code,
                        "environment": Environment.CONTAINER,
                        "bcs_cluster_id": data["bcs_cluster_id"],
                        "add_pod_label": data["add_pod_label"],
                        "extra_labels": data["extra_labels"],
                        "rule_id": rule_id,
                    },
                    conf=conf,
                    async_bkdata=False,
                )
                is_send_path_create_notify = True
                # 注入索引集标签
                IndexSetHandler(path_collector_config.index_set_id).add_tag(tag_id=tag_id)
            if config["enable_stdout"] and not is_exist_bcs_std:
                # 创建标准输出采集项
                std_collector_config = self.create_bcs_collector(
                    {
                        "bk_biz_id": data["bk_biz_id"],
                        "collector_config_name": bcs_collector_config_name["bcs_std_collector"][
                            "collector_config_name"
                        ],
                        "collector_config_name_en": bcs_collector_config_name["bcs_std_collector"][
                            "collector_config_name_en"
                        ],
                        "collector_scenario_id": CollectorScenarioEnum.ROW.value,
                        "custom_type": data["custom_type"],
                        "category_id": data["category_id"],
                        "description": data["description"],
                        "data_link_id": int(conf["data_link_id"]),
                        "bk_app_code": bk_app_code,
                        "environment": Environment.CONTAINER,
                        "bcs_cluster_id": data["bcs_cluster_id"],
                        "add_pod_label": data["add_pod_label"],
                        "extra_labels": data["extra_labels"],
                        "rule_id": rule_id,
                    },
                    conf=conf,
                    async_bkdata=False,
                )
                # 注入索引集标签
                is_send_std_create_notify = True
                IndexSetHandler(std_collector_config.index_set_id).add_tag(tag_id=tag_id)

        collectors = CollectorConfig.objects.filter(rule_id=rule_id)
        if not collectors:
            raise RuleCollectorException(RuleCollectorException.MESSAGE.format(rule_id=rule_id))
        for collector in collectors:
            if collector.collector_config_name_en.endswith("_path"):
                collector.description = data["description"]
                collector.bcs_cluster_id = data["bcs_cluster_id"]
                collector.add_pod_label = data["add_pod_label"]
                collector.extra_labels = data["extra_labels"]
                collector.save()
                path_collector = collector
            if collector.collector_config_name_en.endswith("_std"):
                collector.description = data["description"]
                collector.bcs_cluster_id = data["bcs_cluster_id"]
                collector.add_pod_label = data["add_pod_label"]
                collector.extra_labels = data["extra_labels"]
                collector.save()
                std_collector = collector

        path_container_config, std_container_config = self.get_container_configs(
            data["config"], path_collector=path_collector, rule_id=rule_id
        )
        if path_collector:
            self.deal_self_call(
                collector_config_id=path_collector.collector_config_id,
                collector=path_collector,
                func=self.compare_config,
                **{"data": {"configs": path_container_config}},
            )
        if std_collector:
            self.deal_self_call(
                collector_config_id=std_collector.collector_config_id,
                collector=std_collector,
                func=self.compare_config,
                **{"data": {"configs": std_container_config}},
            )

        if is_send_path_create_notify:
            self.send_create_notify(path_collector_config)

        if is_send_std_create_notify:
            self.send_create_notify(std_collector_config)

        return {
            "rule_id": rule_id,
            "rule_file_index_set_id": path_collector.index_set_id if path_collector else 0,
            "rule_std_index_set_id": std_collector.index_set_id if std_collector else 0,
            "file_index_set_id": path_collector.index_set_id if path_collector else 0,  # TODO: 兼容代码4.8需删除
            "std_index_set_id": std_collector.index_set_id if std_collector else 0,  # TODO: 兼容代码4.8需删除
            "bk_data_id": path_collector.bk_data_id if path_collector else 0,
            "stdout_conf": {"bk_data_id": std_collector.bk_data_id if std_collector else 0},
        }

    @classmethod
    def get_container_configs(cls, config, path_collector, rule_id):
        path_container_config = []
        std_container_config = []
        for conf in config:
            if conf["paths"]:
                path_container_config.append(
                    {
                        "namespaces": conf["namespaces"],
                        "namespaces_exclude": conf["namespaces_exclude"],
                        "any_namespace": not conf["namespaces"],
                        "data_encoding": conf["data_encoding"],
                        "params": {
                            "paths": conf["paths"],
                            "conditions": conf["conditions"]
                            if conf.get("conditions")
                            else {"type": "match", "match_type": "include", "match_content": ""},
                            **conf.get("multiline", {}),
                        },
                        "container": {
                            "workload_type": conf["container"].get("workload_type", ""),
                            "workload_name": conf["container"].get("workload_name", ""),
                            "container_name": conf["container"].get("container_name", ""),
                            "container_name_exclude": conf["container"].get("container_name_exclude", ""),
                        },
                        "label_selector": {
                            "match_labels": conf["label_selector"].get("match_labels", []),
                            "match_expressions": conf["label_selector"].get("match_expressions", []),
                        },
                        "annotation_selector": {
                            "match_annotations": conf["annotation_selector"].get("match_annotations", []),
                        },
                        "rule_id": rule_id,
                        "parent_container_config_id": 0,
                        "collector_type": ContainerCollectorType.CONTAINER,
                    }
                )

            if conf["enable_stdout"]:
                std_container_config.append(
                    {
                        "namespaces": conf["namespaces"],
                        "namespaces_exclude": conf["namespaces_exclude"],
                        "any_namespace": not conf["namespaces"],
                        "data_encoding": conf["data_encoding"],
                        "params": {
                            "paths": [],
                            "conditions": conf["conditions"]
                            if conf.get("conditions")
                            else {"type": "match", "match_type": "include", "match_content": ""},
                            **conf.get("multiline", {}),
                        },
                        "container": {
                            "workload_type": conf["container"].get("workload_type", ""),
                            "workload_name": conf["container"].get("workload_name", ""),
                            "container_name": conf["container"].get("container_name", ""),
                            "container_name_exclude": conf["container"].get("container_name_exclude", ""),
                        },
                        "label_selector": {
                            "match_labels": conf["label_selector"].get("match_labels", []),
                            "match_expressions": conf["label_selector"].get("match_expressions", []),
                        },
                        "annotation_selector": {
                            "match_annotations": conf["annotation_selector"].get("match_annotations", []),
                        },
                        "rule_id": rule_id,
                        "parent_container_config_id": path_collector.collector_config_id if path_collector else 0,
                        "collector_type": ContainerCollectorType.STDOUT,
                    }
                )
        return path_container_config, std_container_config

    def retry_container_collector(self, container_collector_config_id_list=None, **kwargs):
        """
        retry_container_collector
        @param container_collector_config_id_list:
        @return:
        """
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=self.data.collector_config_id)
        if container_collector_config_id_list:
            container_configs = container_configs.filter(id__in=container_collector_config_id_list)

        for container_config in container_configs:
            self.create_container_release(container_config)
        return [config.id for config in container_configs]

    # 接口调用
    def retry_bcs_config(self, rule_id):
        collectors = CollectorConfig.objects.filter(rule_id=rule_id)
        for collector in collectors:
            self.deal_self_call(
                collector_config_id=collector.collector_config_id,
                collector=collector,
                func=self.retry_container_collector,
            )
        return {"rule_id": rule_id}

    def compare_config(self, data, collector_config_id, **kwargs):
        container_configs = ContainerCollectorConfig.objects.filter(collector_config_id=collector_config_id)
        container_configs = list(container_configs)
        config_length = len(data["configs"])
        for x in range(config_length):
            is_all_container = not any(
                [
                    data["configs"][x]["container"]["workload_type"],
                    data["configs"][x]["container"]["workload_name"],
                    data["configs"][x]["container"]["container_name"],
                    data["configs"][x]["container"]["container_name_exclude"],
                    data["configs"][x]["label_selector"]["match_labels"],
                    data["configs"][x]["label_selector"]["match_expressions"],
                    data["configs"][x]["annotation_selector"]["match_annotations"],
                ]
            )
            if x < len(container_configs):
                container_configs[x].namespaces = data["configs"][x]["namespaces"]
                container_configs[x].namespaces_exclude = data["configs"][x]["namespaces_exclude"]
                container_configs[x].any_namespace = not any(
                    [data["configs"][x]["namespaces"], data["configs"][x]["namespaces_exclude"]]
                )
                container_configs[x].data_encoding = data["configs"][x]["data_encoding"]
                container_configs[x].params = (
                    {
                        "paths": data["configs"][x]["paths"],
                        "conditions": {"type": "match", "match_type": "include", "match_content": ""},
                    }
                    if not data["configs"][x]["params"]
                    else data["configs"][x]["params"]
                )
                container_configs[x].workload_type = data["configs"][x]["container"]["workload_type"]
                container_configs[x].workload_name = data["configs"][x]["container"]["workload_name"]
                container_configs[x].container_name = data["configs"][x]["container"]["container_name"]
                container_configs[x].container_name_exclude = data["configs"][x]["container"]["container_name_exclude"]
                container_configs[x].match_labels = data["configs"][x]["label_selector"]["match_labels"]
                container_configs[x].match_expressions = data["configs"][x]["label_selector"]["match_expressions"]
                container_configs[x].match_annotations = data["configs"][x]["annotation_selector"]["match_annotations"]
                container_configs[x].collector_type = data["configs"][x]["collector_type"]
                container_configs[x].all_container = is_all_container
                container_configs[x].raw_config = data["configs"][x].get("raw_config")
                container_configs[x].parent_container_config_id = data["configs"][x].get(
                    "parent_container_config_id", 0
                )
                container_configs[x].rule_id = data["configs"][x].get("rule_id", 0)
                container_configs[x].save()
                container_config = container_configs[x]
            else:
                container_config = ContainerCollectorConfig(
                    collector_config_id=collector_config_id,
                    namespaces=data["configs"][x]["namespaces"],
                    namespaces_exclude=data["configs"][x]["namespaces_exclude"],
                    any_namespace=not any([data["configs"][x]["namespaces"], data["configs"][x]["namespaces_exclude"]]),
                    data_encoding=data["configs"][x]["data_encoding"],
                    params={
                        "paths": data["configs"][x]["paths"],
                        "conditions": {"type": "match", "match_type": "include", "match_content": ""},
                    }
                    if not data["configs"][x]["params"]
                    else data["configs"][x]["params"],
                    workload_type=data["configs"][x]["container"]["workload_type"],
                    workload_name=data["configs"][x]["container"]["workload_name"],
                    container_name=data["configs"][x]["container"]["container_name"],
                    container_name_exclude=data["configs"][x]["container"]["container_name_exclude"],
                    match_labels=data["configs"][x]["label_selector"]["match_labels"],
                    match_expressions=data["configs"][x]["label_selector"]["match_expressions"],
                    match_annotations=data["configs"][x]["annotation_selector"]["match_annotations"],
                    collector_type=data["configs"][x]["collector_type"],
                    all_container=is_all_container,
                    raw_config=data["configs"][x].get("raw_config"),
                    parent_container_config_id=data["configs"][x].get("parent_container_config_id", 0),
                    rule_id=data["configs"][x].get("rule_id", 0),
                )
                container_config.save()
                container_configs.append(container_config)
            self.create_container_release(container_config=container_config)
        delete_container_configs = container_configs[config_length::]
        for config in delete_container_configs:
            # 增量比对后，需要真正删除配置
            self.delete_container_release(config, delete_config=True)

    def create_container_release(self, container_config: ContainerCollectorConfig, **kwargs):
        """
        创建容器采集配置
        :param container_config: 容器采集配置实例
        """
        from apps.log_databus.tasks.collector import create_container_release

        if self.data.yaml_config_enabled and container_config.raw_config:
            # 如果开启了yaml模式且有原始配置，则优先使用
            request_params = copy.deepcopy(container_config.raw_config)
            request_params["dataId"] = self.data.bk_data_id
        else:
            deal_collector_scenario_param(container_config.params)
            request_params = self.collector_container_config_to_raw_config(self.data, container_config)

        # 如果是边缘存查配置，还需要追加 output 配置
        data_link_id = CollectorConfig.objects.get(
            collector_config_id=container_config.collector_config_id
        ).data_link_id
        edge_transport_params = CollectorScenario.get_edge_transport_output_params(data_link_id)
        if edge_transport_params:
            ext_options = request_params.get("extOptions") or {}
            ext_options["output.kafka"] = edge_transport_params
            request_params["extOptions"] = ext_options

        name = self.generate_bklog_config_name(container_config.id)

        container_config.status = ContainerCollectStatus.PENDING.value
        container_config.status_detail = _("等待配置下发")
        container_config.save()

        create_container_release.delay(
            bcs_cluster_id=self.data.bcs_cluster_id,
            container_config_id=container_config.id,
            config_name=name,
            config_params=request_params,
        )

    def delete_container_release(self, container_config, delete_config=False):
        from apps.log_databus.tasks.collector import delete_container_release

        name = self.generate_bklog_config_name(container_config.id)
        container_config.status = ContainerCollectStatus.PENDING.value
        container_config.save()

        delete_container_release.delay(
            bcs_cluster_id=self.data.bcs_cluster_id,
            container_config_id=container_config.id,
            config_name=name,
            delete_config=delete_config,
        )

    # 内部和接口调用
    def validate_container_config_yaml(self, bk_biz_id, bcs_cluster_id, yaml_config: str):
        """
        解析容器日志yaml配置
        """

        class PatchedFullLoader(yaml.FullLoader):
            """
            yaml里面如果有 = 字符串会导致解析失败：https://github.com/yaml/pyyaml/issues/89
            例如:
              filters:
              - conditions:
                - index: "0"
                  key: Jul
                  op: =      # error!
            需要通过这个 loader 去 patch 掉
            """

            yaml_implicit_resolvers = yaml.FullLoader.yaml_implicit_resolvers.copy()
            yaml_implicit_resolvers.pop("=")

        try:
            # 验证是否为合法的 yaml 格式
            configs = [conf for conf in yaml.load_all(yaml_config, Loader=PatchedFullLoader)]
            # 兼容用户直接把整个yaml粘贴过来的情况，这个时候只取 spec 字段
            configs_to_check = [conf["spec"] if "spec" in conf else conf for conf in configs]
            slz = ContainerCollectorYamlSerializer(data=configs_to_check, many=True)
            slz.is_valid(raise_exception=True)

            if not slz.validated_data:
                raise ValueError(_("配置项不能为空"))
        except ValidationError as err:

            def error_msg(value, results):
                if isinstance(value, list):
                    for v in value:
                        error_msg(v, results)
                    return
                for k, v in list(value.items()):
                    if isinstance(v, dict):
                        error_msg(v, results)
                    elif isinstance(v, list) and isinstance(v[0], ErrorDetail):
                        results.append(f"{k}: {v[0][:-1]}")
                    else:
                        for v_msg in v:
                            error_msg(v_msg, results)

            parse_result = []

            def gen_err_topo_message(detail_item: list | dict | str, result_list: list, prefix: str = ""):
                if isinstance(detail_item, str):
                    result_list.append(f"{prefix}: {detail_item}")

                elif isinstance(detail_item, list) and isinstance(detail_item[0], ErrorDetail):
                    gen_err_topo_message(detail_item=detail_item[0], result_list=result_list, prefix=prefix)

                elif isinstance(detail_item, dict):
                    for k, v in detail_item.items():
                        temp_prefix = ".".join([prefix, str(k)]) if prefix else k
                        gen_err_topo_message(detail_item=v, result_list=result_list, prefix=temp_prefix)

            for item in err.detail:
                gen_err_topo_message(detail_item=item, result_list=parse_result)

            return {
                "origin_text": yaml_config,
                "parse_status": False,
                "parse_result": [
                    {"start_line_number": 0, "end_line_number": 0, "message": error} for error in parse_result
                ],
            }
        except Exception as e:  # pylint: disable=broad-except
            return {
                "origin_text": yaml_config,
                "parse_status": False,
                "parse_result": [
                    {"start_line_number": 0, "end_line_number": 0, "message": _("配置格式不合法: {err}").format(err=e)}
                ],
            }

        add_pod_label = False
        add_pod_annotation = False
        extra_labels = {}
        container_configs = []

        for idx, config in enumerate(slz.validated_data):
            log_config_type = config["logConfigType"]

            # 校验配置
            try:
                namespace_list = config.get("namespaceSelector", {}).get("matchNames", [])
                if namespace_list:
                    self.check_cluster_config(
                        bk_biz_id=bk_biz_id,
                        collector_type=log_config_type,
                        bcs_cluster_id=bcs_cluster_id,
                        namespace_list=namespace_list,
                    )
            except AllNamespaceNotAllowedException:
                return {
                    "origin_text": yaml_config,
                    "parse_status": False,
                    "parse_result": [
                        {
                            "start_line_number": 0,
                            "end_line_number": 0,
                            "message": _(
                                "配置校验失败: namespaceSelector 共享集群下 any 不允许为 true，"
                                "且 matchNames 不允许为空，请检查"
                            ),
                        }
                    ],
                }
            except Exception as e:  # noqa
                return {
                    "origin_text": yaml_config,
                    "parse_status": False,
                    "parse_result": [
                        {
                            "start_line_number": 0,
                            "end_line_number": 0,
                            "message": _("配置校验失败: {err}").format(err=e),
                        }
                    ],
                }

            add_pod_label = config["addPodLabel"]
            add_pod_annotation = config["addPodAnnotation"]
            extra_labels = config.get("extMeta", {})
            conditions = convert_filters_to_collector_condition(config.get("filters", []), config.get("delimiter", ""))

            match_expressions = config.get("labelSelector", {}).get("matchExpressions", [])
            for expr in match_expressions:
                # 转换为字符串
                expr["value"] = ",".join(expr.get("values") or [])

            match_annotations = config.get("annotationSelector", {}).get("matchExpressions", [])
            for expr in match_annotations:
                # 转换为字符串
                expr["value"] = ",".join(expr.get("values") or [])

            container_configs.append(
                {
                    "namespaces": config.get("namespaceSelector", {}).get("matchNames", []),
                    "namespaces_exclude": config.get("namespaceSelector", {}).get("excludeNames", []),
                    "container": {
                        "workload_type": config.get("workloadType", ""),
                        "workload_name": config.get("workloadName", ""),
                        "container_name": ",".join(config["containerNameMatch"])
                        if config.get("containerNameMatch")
                        else "",
                        "container_name_exclude": ",".join(config["containerNameExclude"])
                        if config.get("containerNameExclude")
                        else "",
                    },
                    "label_selector": {
                        "match_labels": [
                            {"key": key, "operator": "=", "value": value}
                            for key, value in config.get("labelSelector", {}).get("matchLabels", {}).items()
                        ],
                        "match_expressions": match_expressions,
                    },
                    "annotation_selector": {
                        "match_annotations": match_annotations,
                    },
                    "params": {
                        "paths": config.get("path", []),
                        "exclude_files": config.get("exclude_files", []),
                        "conditions": conditions,
                        "multiline_pattern": config.get("multiline", {}).get("pattern") or "",
                        "multiline_max_lines": config.get("multiline", {}).get("maxLines") or 10,
                        "multiline_timeout": (config.get("multiline", {}).get("timeout") or "10s").rstrip("s"),
                    },
                    "data_encoding": config["encoding"],
                    "collector_type": log_config_type,
                    "raw_config": slz.initial_data[idx],
                }
            )

        return {
            "origin_text": yaml_config,
            "parse_status": True,
            "parse_result": {
                "environment": Environment.CONTAINER,
                "extra_labels": [{"key": key, "value": value} for key, value in extra_labels.items()],
                "add_pod_label": add_pod_label,
                "add_pod_annotation": add_pod_annotation,
                "configs": container_configs,
            },
        }

    @classmethod
    def collector_container_config_to_raw_config(
        cls, collector_config: CollectorConfig, container_config: ContainerCollectorConfig
    ) -> dict:
        """
        根据采集配置和容器采集配置实例创建容器采集配置
        @param collector_config: 采集配置
        @param container_config: 容器采集配置实例
        @return:
        """
        raw_config = cls.container_config_to_raw_config(container_config)
        raw_config.update(
            {
                "dataId": collector_config.bk_data_id,
                "extMeta": {label["key"]: label["value"] for label in collector_config.extra_labels},
                "addPodLabel": collector_config.add_pod_label,
                "addPodAnnotation": collector_config.add_pod_annotation,
            }
        )
        return raw_config

    def list_workload_type(self):
        toggle = FeatureToggleObject.toggle(BCS_DEPLOYMENT_TYPE)
        return (
            toggle.feature_config
            if toggle
            else [WorkLoadType.DEPLOYMENT, WorkLoadType.JOB, WorkLoadType.DAEMON_SET, WorkLoadType.STATEFUL_SET]
        )

    def preview_containers(
        self,
        topo_type,
        bk_biz_id,
        bcs_cluster_id,
        namespaces=None,
        namespaces_exclude=None,
        label_selector=None,
        annotation_selector=None,
        container=None,
    ):
        """
        预览匹配到的 nodes 或 pods
        """
        container = container or {}
        namespaces = namespaces or []
        namespaces_exclude = namespaces_exclude or []
        label_selector = label_selector or {}
        annotation_selector = annotation_selector or {}

        # 将标签匹配条件转换为表达式
        match_expressions = label_selector.get("match_expressions", [])

        # match_labels 本质上是个字典，需要去重
        match_labels = {label["key"]: label["value"] for label in label_selector.get("match_labels", [])}
        match_labels_list = [f"{label[0]} = {label[1]}" for label in match_labels.items()]

        match_labels_list.extend(self.get_expr_list(match_expressions))
        label_expression = ", ".join(match_labels_list)

        # annotation selector expr解析
        match_annotations = annotation_selector.get("match_annotations", [])

        api_instance = Bcs(cluster_id=bcs_cluster_id).api_instance_core_v1
        previews = []

        # Node 预览
        if topo_type == TopoType.NODE.value:
            if label_expression:
                # 如果有多条表达式，需要拆分为多个去请求，以获取每个表达式实际匹配的数量
                nodes = api_instance.list_node(label_selector=label_expression)
            else:
                nodes = api_instance.list_node()
            previews.append(
                {"group": "node", "total": len(nodes.items), "items": [item.metadata.name for item in nodes.items]}
            )
            return previews

        # Pod 预览
        # 当存在标签表达式时，以标签表达式维度展示
        # 当不存在标签表达式时，以namespace维度展示
        if label_expression:
            if not namespaces or len(namespaces) > 1 or namespaces_exclude:
                pods = api_instance.list_pod_for_all_namespaces(label_selector=label_expression)
            else:
                pods = api_instance.list_namespaced_pod(label_selector=label_expression, namespace=namespaces[0])
        else:
            if not namespaces or len(namespaces) > 1 or namespaces_exclude:
                pods = api_instance.list_pod_for_all_namespaces()
            else:
                pods = api_instance.list_namespaced_pod(namespace=namespaces[0])

        if match_annotations:
            # 根据annotation过滤
            pods = self.filter_pods_by_annotations(pods, match_annotations)

        is_shared_cluster = False
        shared_cluster_namespace = list()
        cluster_info = self.get_cluster_info(bk_biz_id, bcs_cluster_id)
        if cluster_info.get("is_shared"):
            is_shared_cluster = True
            namespace_info = self._get_shared_cluster_namespace(bk_biz_id, bcs_cluster_id)
            shared_cluster_namespace = [info["name"] for info in namespace_info]

        pods = self.filter_pods(
            pods,
            namespaces=namespaces,
            namespaces_exclude=namespaces_exclude,
            is_shared_cluster=is_shared_cluster,
            shared_cluster_namespace=shared_cluster_namespace,
            **container,
        )

        # 按 namespace进行分组
        namespace_pods = defaultdict(list)
        for pod in pods:
            namespace = pod[0]
            namespace_pods[namespace].append(pod[1])

        for namespace, ns_pods in namespace_pods.items():
            previews.append({"group": f"namespace = {namespace}", "total": len(ns_pods), "items": ns_pods})

        return previews
