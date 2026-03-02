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

import abc
import copy
import base64
import datetime
import re
from collections import defaultdict

import arrow
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _
from django.utils.module_loading import import_string

from apps.api import BkDataAccessApi, NodeApi, TransferApi
from apps.api.modules.bk_node import BKNodeApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.exceptions import ApiError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import (
    FEATURE_COLLECTOR_ITSM,
)
from apps.iam import Permission, ResourceEnum
from apps.log_databus.constants import (
    ADMIN_REQUEST_USER,
    BKDATA_DATA_REGION,
    BKDATA_DATA_SCENARIO,
    BKDATA_DATA_SCENARIO_ID,
    BKDATA_DATA_SENSITIVITY,
    BKDATA_DATA_SOURCE,
    BKDATA_DATA_SOURCE_TAGS,
    BKDATA_PERMISSION,
    BKDATA_TAGS,
    BULK_CLUSTER_INFOS_LIMIT,
    CACHE_KEY_CLUSTER_INFO,
    META_DATA_ENCODING,
    ArchiveInstanceType,
    CollectStatus,
    EtlConfig,
    ETLProcessorChoices,
    LogPluginInfo,
    RunStatus,
    RETRIEVE_CHAIN,
    Environment,
)
from apps.log_databus.exceptions import (
    CollectNotSuccess,
    CollectNotSuccessNotCanStart,
    CollectorBkDataNameDuplicateException,
    CollectorConfigDataIdNotExistException,
    CollectorConfigNameDuplicateException,
    CollectorConfigNameENDuplicateException,
    CollectorConfigNotExistException,
    CollectorResultTableIDDuplicateException,
    RegexInvalidException,
    RegexMatchException,
    ResultTableNotExistException,
    SubscriptionInfoNotFoundException,
    CollectorIdNotExistException,
    SubscriptionStatisticException,
)
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.models import (
    ArchiveConfig,
    CleanStash,
    CollectorConfig,
    CollectorPlugin,
    ContainerCollectorConfig,
    DataLinkConfig,
)
from apps.log_databus.tasks.bkdata import async_create_bkdata_data_id
from apps.log_esquery.utils.es_route import EsRoute
from apps.log_measure.events import NOTIFY_EVENT
from apps.log_search.constants import (
    CollectorScenarioEnum,
    CustomTypeEnum,
    GlobalCategoriesEnum,
    InnerTag,
)
from apps.log_search.handlers.biz import BizHandler
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import (
    IndexSetTag,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    Space,
)
from apps.models import model_to_dict
from apps.utils.cache import caches_ten_minute
from apps.utils.custom_report import BK_CUSTOM_REPORT, CONFIG_OTLP_FIELD
from apps.utils.db import array_chunk
from apps.utils.function import map_if
from apps.utils.local import get_local_param, get_request_username, get_request_tenant_id
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import format_user_time_zone

COLLECTOR_RE = re.compile(r".*\d{6,8}$")


class CollectorHandler:
    data: CollectorConfig

    def __init__(self, collector_config_id=None, data=None):
        self.collector_config_id = collector_config_id
        self.data = data if data else None

        if collector_config_id and not data:
            try:
                self.data = CollectorConfig.objects.get(collector_config_id=self.collector_config_id)
            except CollectorConfig.DoesNotExist:
                raise CollectorConfigNotExistException()

    @classmethod
    def get_instance(cls, collector_config_id=None, env=None):
        if env and not collector_config_id:
            if env == Environment.CONTAINER:
                collector_handler = import_string("apps.log_databus.handlers.collector.K8sCollectorHandler")
                return collector_handler()
            else:
                collector_handler = import_string("apps.log_databus.handlers.collector.HostCollectorHandler")
                return collector_handler()

        if collector_config_id:
            try:
                data = CollectorConfig.objects.get(collector_config_id=collector_config_id)
            except CollectorConfig.DoesNotExist:
                raise CollectorConfigNotExistException()

            if data.is_container_environment:
                collector_handler = import_string("apps.log_databus.handlers.collector.K8sCollectorHandler")
                return collector_handler(collector_config_id, data)
            else:
                collector_handler = import_string("apps.log_databus.handlers.collector.HostCollectorHandler")
                return collector_handler(collector_config_id, data)
        else:
            raise CollectorIdNotExistException()

    def _multi_info_get(self, use_request=True):
        """
        并发查询所需的配置
        @param use_request:
        @return:
        """
        multi_execute_func = MultiExecuteFunc()
        if self.data.bk_data_id:
            multi_execute_func.append(
                "data_id_config",
                TransferApi.get_data_id,
                params={"bk_data_id": self.data.bk_data_id},
                use_request=use_request,
            )
        if self.data.table_id:
            multi_execute_func.append(
                "result_table_config",
                TransferApi.get_result_table,
                params={"table_id": self.data.table_id},
                use_request=use_request,
            )
            multi_execute_func.append(
                "result_table_storage",
                TransferApi.get_result_table_storage,
                params={"result_table_list": self.data.table_id, "storage_type": "elasticsearch"},
                use_request=use_request,
            )
        if self.data.subscription_id:
            multi_execute_func.append(
                "subscription_config",
                BKNodeApi.get_subscription_info,
                params={"subscription_id_list": [self.data.subscription_id], "bk_biz_id": self.data.bk_biz_id},
                use_request=use_request,
            )
        return multi_execute_func.run()

    def set_itsm_info(self, collector_config, context):  # noqa
        """
        set_itsm_info
        @param collector_config:
        @param context:
        @return:
        """
        from apps.log_databus.handlers.itsm import ItsmHandler

        itsm_info = ItsmHandler().collect_itsm_status(collect_config_id=collector_config["collector_config_id"])
        collector_config.update(
            {
                "iframe_ticket_url": itsm_info["iframe_ticket_url"],
                "ticket_url": itsm_info["ticket_url"],
                "itsm_ticket_status": itsm_info["collect_itsm_status"],
                "itsm_ticket_status_display": itsm_info["collect_itsm_status_display"],
            }
        )
        return collector_config

    def set_default_field(self, collector_config, context):  # noqa
        """
        set_default_field
        @param collector_config:
        @param context:
        @return:
        """
        collector_config.update(
            {
                "collector_scenario_name": self.data.get_collector_scenario_id_display(),
                "bk_data_name": self.data.bk_data_name,
                "storage_cluster_id": None,
                "retention": None,
                "etl_params": {},
                "fields": [],
            }
        )
        return collector_config

    def set_split_rule(self, collector_config, context):  # noqa
        """
        set_split_rule
        @param collector_config:
        @param context:
        @return:
        """
        collector_config["index_split_rule"] = "--"
        if self.data.table_id and collector_config["storage_shards_size"]:
            slice_size = collector_config["storage_shards_nums"] * collector_config["storage_shards_size"]
            collector_config["index_split_rule"] = _("ES索引主分片大小达到{}G后分裂").format(slice_size)
        return collector_config

    def set_target(self, collector_config: dict, context):  # noqa
        """
        set_target
        @param collector_config:
        @param context:
        @return:
        """
        if collector_config["target_node_type"] == "INSTANCE":
            collector_config["target"] = collector_config.get("target_nodes", [])
            return collector_config
        nodes = collector_config.get("target_nodes", [])
        bk_module_inst_ids = self._get_ids("module", nodes)
        bk_set_inst_ids = self._get_ids("set", nodes)
        collector_config["target"] = []
        biz_handler = BizHandler(bk_biz_id=collector_config["bk_biz_id"])
        result_module = biz_handler.get_modules_info(bk_module_inst_ids)
        result_set = biz_handler.get_sets_info(bk_set_inst_ids)
        collector_config["target"].extend(result_module)
        collector_config["target"].extend(result_set)
        return collector_config

    def set_categorie_name(self, collector_config, context):
        """
        set_target
        @param collector_config:
        @param context:
        @return:
        """
        collector_config["category_name"] = GlobalCategoriesEnum.get_display(collector_config["category_id"])
        collector_config["custom_name"] = CustomTypeEnum.get_choice_label(collector_config["custom_type"])
        return collector_config

    def complement_metadata_info(self, collector_config, context):
        """
        补全保存在metadata 结果表中的配置
        @param collector_config:
        @param context:
        @return:
        """
        result = context
        if not self.data.table_id:
            collector_config.update(
                {"table_id_prefix": self._build_bk_table_id(self.data.bk_biz_id, ""), "table_id": ""}
            )
            return collector_config
        table_id_prefix, table_id = self.data.table_id.split(".")
        collector_config.update({"table_id_prefix": table_id_prefix + "_", "table_id": table_id})

        if "result_table_config" in result and "result_table_storage" in result:
            if self.data.table_id in result["result_table_storage"]:
                self.data.etl_config = EtlStorage.get_etl_config(
                    result["result_table_config"], default=self.data.etl_config
                )
                etl_storage = EtlStorage.get_instance(etl_config=self.data.etl_config)
                collector_config.update(
                    etl_storage.parse_result_table_config(
                        result_table_config=result["result_table_config"],
                        result_table_storage=result["result_table_storage"][self.data.table_id],
                        fields_dict=self.get_fields_dict(self.data.collector_config_id),
                    )
                )
                # 补充es集群端口号 、es集群域名
                storage_cluster_id = collector_config.get("storage_cluster_id", "")
                cluster_config = IndexSetHandler.get_cluster_map().get(storage_cluster_id, {})
                collector_config.update(
                    {
                        "storage_cluster_port": cluster_config.get("cluster_port", ""),
                        "storage_cluster_domain_name": cluster_config.get("cluster_domain_name", ""),
                    }
                )
            return collector_config
        return collector_config

    def complement_nodeman_info(self, collector_config, context):
        """
        补全保存在节点管理的订阅配置
        @param collector_config:
        @param context:
        @return:
        """
        result = context
        if self.data.subscription_id and "subscription_config" in result:
            if not result["subscription_config"]:
                raise SubscriptionInfoNotFoundException()
            subscription_config = result["subscription_config"][0]
            collector_scenario = CollectorScenario.get_instance(collector_scenario_id=self.data.collector_scenario_id)
            params = collector_scenario.parse_steps(subscription_config["steps"])
            collector_config.update({"params": params})
            data_encoding = params.get("encoding")
            if data_encoding:
                # 将对应data_encoding 转换成大写供前端
                collector_config.update({"data_encoding": data_encoding.upper()})
        return collector_config

    def fields_is_empty(self, collector_config, context):  # noqa
        """
        如果数据未入库，则fields为空，直接使用默认标准字段返回
        @param collector_config:
        @param context:
        @return:
        """
        if not collector_config["fields"]:
            etl_storage = EtlStorage.get_instance(EtlConfig.BK_LOG_TEXT)
            collector_scenario = CollectorScenario.get_instance(collector_scenario_id=self.data.collector_scenario_id)
            built_in_config = collector_scenario.get_built_in_config()
            result_table_config = etl_storage.get_result_table_config(
                fields=None, etl_params=None, built_in_config=built_in_config
            )
            etl_config = etl_storage.parse_result_table_config(result_table_config)
            collector_config["fields"] = etl_config.get("fields", [])
        return collector_config

    def deal_time(self, collector_config, context):  # noqa
        """
        对 collector_config进行时区转换
        @param collector_config:
        @param context:
        @return:
        """
        time_zone = get_local_param("time_zone", settings.TIME_ZONE)
        collector_config["updated_at"] = format_user_time_zone(collector_config["updated_at"], time_zone=time_zone)
        collector_config["created_at"] = format_user_time_zone(collector_config["created_at"], time_zone=time_zone)
        return collector_config

    def add_container_configs(self, collector_config, context):
        """
        add_container_configs
        @param collector_config:
        @param context:
        @return:
        """
        if not self.data.is_container_environment:
            return collector_config

        container_configs = []
        for config in ContainerCollectorConfig.objects.filter(collector_config_id=self.collector_config_id):
            container_configs.append(model_to_dict(config))

        collector_config["configs"] = container_configs
        return collector_config

    def encode_yaml_config(self, collector_config, context):
        """
        encode_yaml_config
        @param collector_config:
        @param context:
        @return:
        """
        if not collector_config["yaml_config"]:
            return collector_config
        collector_config["yaml_config"] = base64.b64encode(collector_config["yaml_config"].encode("utf-8"))
        return collector_config

    @abc.abstractmethod
    def _pre_start(self):
        raise NotImplementedError

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

        self._pre_start()

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
        return True

    @abc.abstractmethod
    def _pre_stop(self):
        raise NotImplementedError

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

        self._pre_stop()

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
        return True

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

        # 添加索引集相关信息
        log_index_set_obj = LogIndexSet.objects.filter(collector_config_id=self.collector_config_id).first()
        if log_index_set_obj:
            collector_config.update(
                {"sort_fields": log_index_set_obj.sort_fields, "target_fields": log_index_set_obj.target_fields}
            )
            parent_index_set_ids = log_index_set_obj.get_parent_index_set_ids()
            collector_config.update({"parent_index_set_ids": parent_index_set_ids})
        return collector_config

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
        parent_index_set_ids=None,
    ):
        collector_config_update = {
            "collector_config_name": collector_config_name,
            "category_id": category_id,
            "description": description or collector_config_name,
            "is_display": is_display,
        }

        _collector_config_name = self.data.collector_config_name
        bk_data_name = self.build_bk_data_name(
            bk_biz_id=self.data.get_bk_biz_id(), collector_config_name_en=self.data.collector_config_name_en
        )
        if self.data.bk_data_id and self.data.bk_data_name != bk_data_name:
            TransferApi.modify_data_id({"data_id": self.data.bk_data_id, "data_name": bk_data_name})
            self.data.bk_data_name = bk_data_name
            logger.info(
                f"[modify_data_name] bk_data_id=>{self.data.bk_data_id}, data_name {self.data.bk_data_name}=>{bk_data_name}"
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

        # 更新归属索引集
        IndexSetHandler(self.data.index_set_id).update_parent_index_sets(parent_index_set_ids)

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
            # 优先使用collector_config的table_id，如果存在则提取表名部分
            if self.data.table_id:
                # table_id格式为: prefix.table_name，需要提取表名部分
                table_id_name = self.data.table_id.split(".")[-1]
            else:
                # 如果table_id不存在，则使用collector_config_name_en作为后备
                table_id_name = self.data.collector_config_name_en
            etl_params = {
                "table_id": table_id_name,
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

    @abc.abstractmethod
    def _pre_destroy(self):
        raise NotImplementedError

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

        # 3. 区分物理机和容器
        self._pre_destroy()

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

    @abc.abstractmethod
    def get_task_status(self, id_list):
        raise NotImplementedError

    @abc.abstractmethod
    def retry_instances(self, instance_id_list):
        raise NotImplementedError

    @abc.abstractmethod
    def get_subscription_status(self):
        raise NotImplementedError

    @staticmethod
    def get_fields_dict(collector_config_id: int):
        """
        获取字段的自定义分词和是否大小写信息
        """
        fields_dict = {}
        clean_stash = CleanStash.objects.filter(collector_config_id=collector_config_id).first()
        if not clean_stash:
            return fields_dict
        etl_params = clean_stash.etl_params or {}
        fields_dict = {
            "log": {
                "is_case_sensitive": etl_params.get("original_text_is_case_sensitive", False),
                "tokenize_on_chars": etl_params.get("original_text_tokenize_on_chars", ""),
            }
        }
        etl_fields = clean_stash.etl_fields or []
        for etl_field in etl_fields:
            fields_dict.update(
                {
                    etl_field["field_name"]: {
                        "is_case_sensitive": etl_field.get("is_case_sensitive", False),
                        "tokenize_on_chars": etl_field.get("tokenize_on_chars", ""),
                    }
                }
            )
        return fields_dict

    def get_report_token(self):
        """
        获取上报Token
        """
        data = {"bk_data_token": ""}
        if self.data.custom_type == CustomTypeEnum.OTLP_LOG.value and self.data.log_group_id:
            log_group = TransferApi.get_log_group({"log_group_id": self.data.log_group_id})
            data["bk_data_token"] = log_group.get("bk_data_token", "")
        return data

    @staticmethod
    def get_report_host():
        """
        获取上报Host
        """

        data = {}
        bk_custom_report = FeatureToggleObject.toggle(BK_CUSTOM_REPORT)
        if bk_custom_report:
            data = bk_custom_report.feature_config.get(CONFIG_OTLP_FIELD, {})
        return data

    @staticmethod
    def _get_ids(node_type: str, nodes: list):
        return [node["bk_inst_id"] for node in nodes if node["bk_obj_id"] == node_type]

    @staticmethod
    @caches_ten_minute(key=CACHE_KEY_CLUSTER_INFO, need_deconstruction_name="result_table_list", need_md5=True)
    def bulk_cluster_infos(result_table_list: list):
        """
        批量获取集群信息，单个失败不影响其他，将单个失败的 result_table 进行重试
        如果分片请求失败，则拆解为单个 result_table 重试
        @param result_table_list:
        @return:
        """

        def get_cluster_info(result_table_str: str):
            """
            获取集群信息（支持批量查询）
            """
            try:
                return TransferApi.get_result_table_storage(
                    params={"result_table_list": result_table_str, "storage_type": "elasticsearch"}
                )
            except Exception as e:
                logger.warning(f"获取集群信息失败(result_tables={result_table_str}): {e}", exc_info=True)
                return {}

        cluster_infos = {}

        if not result_table_list:
            return cluster_infos

        unique_tables = list(dict.fromkeys(result_table_list))

        # 按分片批量获取
        chunk_multi_execute_func = MultiExecuteFunc()
        unique_table_chunks: list[list[str]] = array_chunk(unique_tables, BULK_CLUSTER_INFOS_LIMIT)

        # 记录每个 chunk_str 对应的 table_chunk
        table_chunk_dict: dict[str, list[str]] = {}

        for table_chunk in unique_table_chunks:
            chunk_str = ",".join(table_chunk)
            table_chunk_dict[chunk_str] = table_chunk
            chunk_multi_execute_func.append(chunk_str, get_cluster_info, chunk_str)

        chunk_response = chunk_multi_execute_func.run()

        # 记录需要重试的 table_id
        retry_tables = []

        # 处理分片结果
        for chunk_str, response in chunk_response.items():
            table_chunk = table_chunk_dict.get(chunk_str, [])

            if response and isinstance(response, dict):
                cluster_infos.update(response)

                # 检查分片结果是否包含该分片中所有表的集群信息
                for table_id in table_chunk:
                    if table_id not in response:
                        # 如果分片结果中缺少某个表的集群信息, 则该表获取失败, 进行重试
                        retry_tables.append(table_id)
            else:
                # 分片获取失败, 记录该分片中的所有 table_id 进行重试
                retry_tables.extend(table_chunk)

        # 对获取集群信息失败的 table_id 进行重试
        if retry_tables:
            logger.warning(
                f"The chunk query result is incomplete, "
                f"querying {len(retry_tables)} result tables individually: {retry_tables}"
            )

            single_multi_execute_func = MultiExecuteFunc()

            for table_id in retry_tables:
                single_multi_execute_func.append(table_id, get_cluster_info, table_id)

            single_response = single_multi_execute_func.run()

            # 处理单独查询结果
            for table_id, response in single_response.items():
                if response and isinstance(response, dict) and response.get(table_id):
                    # 单个重试成功
                    cluster_infos[table_id] = response[table_id]

        # 确保所有 result_table 都有集群信息, 否则设置为默认值
        for table_id in result_table_list:
            cluster_infos.setdefault(
                table_id, {"cluster_config": {"cluster_id": -1, "cluster_name": ""}, "storage_config": {"retention": 0}}
            )

        return cluster_infos

    @classmethod
    def add_cluster_info(cls, data):
        """
        补充集群信息
        @param data:
        @return:
        """
        result_table_list = [_data["table_id"] for _data in data if _data.get("table_id")]

        try:
            cluster_infos = cls.bulk_cluster_infos(result_table_list=result_table_list)
        except ApiError as error:
            logger.exception(f"request cluster info error => [{error}]")
            cluster_infos = {}

        time_zone = get_local_param("time_zone")
        index_set_id_set = set(
            LogIndexSetData.objects.exclude(apply_status="normal").values_list("index_set_id", flat=True)
        )
        for _data in data:
            cluster_info = cluster_infos.get(
                _data["table_id"],
                {"cluster_config": {"cluster_id": -1, "cluster_name": ""}, "storage_config": {"retention": 0}},
            )
            _data["storage_cluster_id"] = cluster_info["cluster_config"]["cluster_id"]
            _data["storage_cluster_name"] = cluster_info["cluster_config"].get("cluster_name", "")
            _data["storage_display_name"] = cluster_info["cluster_config"].get("display_name", "")
            _data["retention"] = cluster_info["storage_config"]["retention"]
            # table_id
            if _data.get("table_id"):
                table_id_prefix, table_id = _data["table_id"].split(".")
                _data["table_id_prefix"] = table_id_prefix + "_"
                _data["table_id"] = table_id
            # 分类名
            _data["category_name"] = GlobalCategoriesEnum.get_display(_data["category_id"])
            _data["custom_name"] = CustomTypeEnum.get_choice_label(_data["custom_type"])

            # 时间处理
            _data["created_at"] = (
                arrow.get(_data["created_at"])
                .replace(tzinfo=settings.TIME_ZONE)
                .to(time_zone)
                .strftime(settings.BKDATA_DATETIME_FORMAT)
            )
            _data["updated_at"] = (
                arrow.get(_data["updated_at"])
                .replace(tzinfo=settings.TIME_ZONE)
                .to(time_zone)
                .strftime(settings.BKDATA_DATETIME_FORMAT)
            )

            # 是否可以检索
            if _data["is_active"] and _data["index_set_id"]:
                _data["is_search"] = _data["index_set_id"] not in index_set_id_set
            else:
                _data["is_search"] = False

        return data

    @classmethod
    def add_tags_info(cls, data):
        """添加标签信息"""
        index_set_ids = [data_info.get("index_set_id") for data_info in data if data_info.get("index_set_id")]
        index_set_objs = LogIndexSet.origin_objects.filter(index_set_id__in=index_set_ids)

        tag_ids_mapping = dict()
        tag_ids_all = list()

        for obj in index_set_objs:
            tag_ids_mapping[obj.index_set_id] = obj.tag_ids
            tag_ids_all.extend(obj.tag_ids)

        # 查询出所有的tag信息
        index_set_tag_objs = IndexSetTag.objects.filter(tag_id__in=tag_ids_all)
        index_set_tag_mapping = {
            obj.tag_id: {
                "name": InnerTag.get_choice_label(obj.name),
                "color": obj.color,
                "tag_id": obj.tag_id,
            }
            for obj in index_set_tag_objs
        }

        for data_info in data:
            index_set_id = data_info.get("index_set_id", None)
            if not index_set_id:
                data_info["tags"] = list()
                continue
            tag_ids = tag_ids_mapping.get(int(index_set_id), [])
            if not tag_ids:
                data_info["tags"] = list()
                continue
            data_info["tags"] = [
                index_set_tag_mapping.get(int(tag_id)) for tag_id in tag_ids if index_set_tag_mapping.get(int(tag_id))
            ]

        return data

    @classmethod
    def update_or_create_data_id(
        cls, instance: CollectorConfig | CollectorPlugin, etl_processor: str = None, bk_data_id: int = None
    ) -> int:
        """
        创建或更新数据源
        @param instance:
        @param etl_processor:
        @param bk_data_id:
        @return:
        """

        if etl_processor is None:
            etl_processor = instance.etl_processor

        # 创建 Transfer
        if etl_processor == ETLProcessorChoices.TRANSFER.value:
            collector_scenario = CollectorScenario.get_instance(instance.collector_scenario_id)
            bk_data_id = collector_scenario.update_or_create_data_id(
                bk_data_id=instance.bk_data_id,
                data_link_id=instance.data_link_id,
                data_name=cls.build_bk_data_name(instance.get_bk_biz_id(), instance.get_en_name()),
                description=instance.description,
                encoding=META_DATA_ENCODING,
                bk_biz_id=instance.get_bk_biz_id(),
            )
            return bk_data_id

        # 兼容平台账户
        bk_username = getattr(instance, "__platform_username", None) or instance.get_updated_by()

        # 创建 BKBase
        maintainers = {bk_username} if bk_username else {instance.updated_by, instance.created_by}

        if ADMIN_REQUEST_USER in maintainers and len(maintainers) > 1:
            maintainers.discard(ADMIN_REQUEST_USER)

        bkdata_params = {
            "operator": bk_username,
            "bk_username": bk_username,
            "data_scenario": BKDATA_DATA_SCENARIO,
            "data_scenario_id": BKDATA_DATA_SCENARIO_ID,
            "permission": BKDATA_PERMISSION,
            "bk_biz_id": instance.get_bk_biz_id(),
            "description": instance.description,
            "access_raw_data": {
                "tags": BKDATA_TAGS,
                "raw_data_name": instance.get_en_name(),
                "maintainer": ",".join(maintainers),
                "raw_data_alias": instance.get_en_name(),
                "data_source_tags": BKDATA_DATA_SOURCE_TAGS,
                "data_region": BKDATA_DATA_REGION,
                "data_source": BKDATA_DATA_SOURCE,
                "data_encoding": (instance.data_encoding if instance.data_encoding else META_DATA_ENCODING),
                "sensitivity": BKDATA_DATA_SENSITIVITY,
                "description": instance.description,
            },
        }

        if bk_data_id and not instance.bk_data_id:
            bkdata_params["access_raw_data"]["preassigned_data_id"] = bk_data_id

        # 更新
        if instance.bk_data_id:
            bkdata_params["access_raw_data"].update({"preassigned_data_id": instance.bk_data_id})
            bkdata_params.update({"raw_data_id": instance.bk_data_id})
            BkDataAccessApi.deploy_plan_put(bkdata_params)
            return instance.bk_data_id

        # 创建
        result = BkDataAccessApi.deploy_plan_post(bkdata_params)
        return result["raw_data_id"]

    def _pre_check_collector_config_en(self, model_fields: dict, bk_biz_id: int):
        qs = CollectorConfig.objects.filter(
            collector_config_name_en=model_fields["collector_config_name_en"], bk_biz_id=bk_biz_id
        )
        if self.collector_config_id:
            qs = qs.exclude(collector_config_id=self.collector_config_id)
        return qs.exists()

    @staticmethod
    def _authorization_collector(collector_config: CollectorConfig):
        try:
            # 如果是创建，需要做新建授权
            Permission().grant_creator_action(
                resource=ResourceEnum.COLLECTION.create_simple_instance(
                    collector_config.collector_config_id, attribute={"name": collector_config.collector_config_name}
                ),
                creator=collector_config.created_by,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                f"collector_config->({collector_config.collector_config_id}) grant creator action failed, reason: {e}"
            )

    def _itsm_start_judge(self):
        if self.data.is_custom_scenario:
            return
        if self.data.itsm_has_appling() and FeatureToggleObject.switch(name=FEATURE_COLLECTOR_ITSM):
            raise CollectNotSuccessNotCanStart

    @classmethod
    def _get_kafka_broker(cls, broker_url):
        """
        判断是否为内网域名
        """
        if "consul" in broker_url and settings.DEFAULT_KAFKA_HOST:
            return settings.DEFAULT_KAFKA_HOST
        return broker_url

    def tail(self):
        if not self.data.bk_data_id:
            raise CollectorConfigDataIdNotExistException()
        data_result = TransferApi.list_kafka_tail(params={"bk_data_id": self.data.bk_data_id, "namespace": "bklog"})
        return_data = []
        for _message in data_result:
            # 数据预览
            etl_message = copy.deepcopy(_message)
            data_items = etl_message.get("items")
            if data_items:
                etl_message.update(
                    {
                        "data": data_items[0].get("data", ""),
                        "log": data_items[0].get("data", ""),
                        "iterationindex": data_items[0].get("iterationindex", ""),
                        "batch": [_item.get("data", "") for _item in data_items],
                    }
                )
            else:
                etl_message.update({"data": "", "iterationindex": "", "bathc": []})

            return_data.append({"etl": etl_message, "origin": _message})

        return return_data

    @staticmethod
    def _pre_get_subscription_status_by_list(
        collector_obj, container_collector_mapping, return_data, subscription_collector_map, subscription_id_list
    ):
        if collector_obj.is_container_environment:
            collector_handler = import_string("apps.log_databus.handlers.collector.K8sCollectorHandler")
            return_data = collector_handler.get_container_return_data(
                collector_obj, container_collector_mapping, return_data
            )
            return return_data, subscription_id_list, subscription_collector_map

        collector_handler = import_string("apps.log_databus.handlers.collector.HostCollectorHandler")
        return_data, subscription_id_list, subscription_collector_map = collector_handler.get_subscription_dispose(
            collector_obj, return_data, subscription_collector_map, subscription_id_list
        )
        return return_data, subscription_id_list, subscription_collector_map

    def get_subscription_status_by_list(self, collector_id_list: list) -> list:
        """
        批量获取采集项订阅状态
        :param  [list] collector_id_list: 采集项ID列表
        :return: [dict]
        """
        return_data = list()
        subscription_id_list = list()
        subscription_collector_map = dict()

        collector_list = CollectorConfig.objects.filter(collector_config_id__in=collector_id_list)

        # 获取主采集项到容器子采集项的映射关系
        container_collector_mapping = defaultdict(list)
        for config in ContainerCollectorConfig.objects.filter(collector_config_id__in=collector_id_list):
            container_collector_mapping[config.collector_config_id].append(config)

        for collector_obj in collector_list:
            return_data, subscription_id_list, subscription_collector_map = self._pre_get_subscription_status_by_list(
                collector_obj,
                container_collector_mapping,
                return_data,
                subscription_collector_map,
                subscription_id_list,
            )
        status_result = []
        multi_execute_func = MultiExecuteFunc(max_workers=10)
        for subscription_id in subscription_id_list:
            multi_execute_func.append(
                result_key=subscription_id,
                func=NodeApi.subscription_statistic,
                params={"subscription_id_list": [subscription_id], "plugin_name": LogPluginInfo.NAME},
            )

        multi_result = multi_execute_func.run(return_exception=True)
        for key, ret in multi_result.items():
            if isinstance(ret, Exception):
                # 子查询异常
                logger.exception("subscription id(%s),subscription statistic failed：%s", key, ret)
                raise SubscriptionStatisticException(
                    SubscriptionStatisticException.MESSAGE.format(
                        reason=f"subscription id({key}),subscription statistic failed：{ret}"
                    )
                )
            status_result.extend(ret)

        # 如果没有订阅ID，则直接返回
        if not subscription_id_list:
            return self._clean_terminated(return_data)

        # 接口查询到的数据进行处理
        subscription_status_data, subscription_id_list = self.format_subscription_status(
            status_result, subscription_id_list, subscription_collector_map
        )
        return_data += subscription_status_data

        # 节点管理接口未查到相应订阅ID数据
        for subscription_id in subscription_id_list:
            collector_key = subscription_collector_map[subscription_id]
            return_data.append(
                {
                    "collector_id": collector_key,
                    "subscription_id": subscription_id,
                    "status": CollectStatus.FAILED,
                    "status_name": RunStatus.FAILED,
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "pending": 0,
                }
            )

        # 若采集项已停用，则采集状态修改为“已停用”
        return self._clean_terminated(return_data)

    @staticmethod
    def _clean_terminated(data: list):
        for _data in data:
            # RUNNING状态
            if _data["status"] == CollectStatus.RUNNING:
                continue

            _collector_config = CollectorConfig.objects.get(collector_config_id=_data["collector_id"])
            if not _collector_config.is_active:
                _data["status"] = CollectStatus.TERMINATED
                _data["status_name"] = RunStatus.TERMINATED
        return data

    @staticmethod
    def format_subscription_status(status_result, subscription_id_list, subscription_collector_map):
        return_data = list()

        for status_obj in status_result:
            total_count = int(status_obj["instances"])
            status_group = {
                status["status"]: int(status["count"]) for status in status_obj["status"] if status["count"]
            }

            # 订阅状态
            group_status_keys = status_group.keys()
            if not status_group:
                status = CollectStatus.UNKNOWN
                status_name = RunStatus.UNKNOWN
            elif CollectStatus.PENDING in group_status_keys or CollectStatus.RUNNING in group_status_keys:
                status = CollectStatus.RUNNING
                status_name = RunStatus.RUNNING
            elif CollectStatus.FAILED in group_status_keys and CollectStatus.SUCCESS in group_status_keys:
                status = CollectStatus.FAILED
                status_name = RunStatus.PARTFAILED
            elif CollectStatus.FAILED in group_status_keys and CollectStatus.SUCCESS not in group_status_keys:
                status = CollectStatus.FAILED
                status_name = RunStatus.FAILED
            elif CollectStatus.TERMINATED in group_status_keys and CollectStatus.SUCCESS not in group_status_keys:
                status = CollectStatus.TERMINATED
                status_name = RunStatus.TERMINATED
            else:
                status = CollectStatus.SUCCESS
                status_name = RunStatus.SUCCESS

            # 各订阅状态实例数量
            pending_count = status_group.get(CollectStatus.PENDING, 0) + status_group.get(CollectStatus.RUNNING, 0)
            failed_count = status_group.get(CollectStatus.FAILED, 0)
            success_count = status_group.get(CollectStatus.SUCCESS, 0)

            subscription_id_list.remove(status_obj["subscription_id"])
            return_data.append(
                {
                    "collector_id": subscription_collector_map[status_obj["subscription_id"]],
                    "subscription_id": status_obj["subscription_id"],
                    "status": status,
                    "status_name": status_name,
                    "total": total_count,
                    "success": success_count,
                    "failed": failed_count,
                    "pending": pending_count,
                }
            )
        return return_data, subscription_id_list

    @staticmethod
    def regex_debug(data):
        """
        行首正则调试，返回匹配行数
        """
        lines = data["log_sample"].split("\n")
        match_lines = 0
        for line in lines:
            try:
                if re.search(data["multiline_pattern"], line):
                    match_lines += 1
            except re.error as e:
                raise RegexInvalidException(RegexInvalidException.MESSAGE.format(error=e))
        if not match_lines:
            raise RegexMatchException
        data.update({"match_lines": match_lines})
        return data

    def indices_info(self):
        result_table_id = self.data.table_id
        if not result_table_id:
            raise CollectNotSuccess
        result = EsRoute(scenario_id=Scenario.LOG, indices=result_table_id).cat_indices()
        return StorageHandler.sort_indices(result)

    def get_clean_stash(self):
        clean_stash = CleanStash.objects.filter(collector_config_id=self.collector_config_id).first()
        if not clean_stash:
            return None
        config = model_to_dict(clean_stash)
        # 给未配置自定义分词符和大小写敏感的清洗配置添加默认值
        etl_params = config.get("etl_params", {})
        etl_params.setdefault("original_text_is_case_sensitive", False)
        etl_params.setdefault("original_text_tokenize_on_chars", "")
        config["etl_params"] = etl_params

        etl_fields = config.get("etl_fields", [])
        for etl_field in etl_fields:
            etl_field.setdefault("is_case_sensitive", False)
            etl_field.setdefault("tokenize_on_chars", "")
        config["etl_fields"] = etl_fields
        return config

    def create_clean_stash(self, params: dict):
        model_fields = {
            "clean_type": params["clean_type"],
            "etl_params": params["etl_params"],
            "etl_fields": params["etl_fields"],
            "collector_config_id": int(self.collector_config_id),
            "bk_biz_id": params["bk_biz_id"],
        }
        CleanStash.objects.filter(collector_config_id=self.collector_config_id).delete()
        logger.info(f"delete clean stash {self.collector_config_id}")
        return model_to_dict(CleanStash.objects.create(**model_fields))

    @staticmethod
    def list_collector(bk_biz_id):
        return [
            {
                "collector_config_id": collector.collector_config_id,
                "collector_config_name": collector.collector_config_name,
            }
            for collector in CollectorConfig.objects.filter(bk_biz_id=bk_biz_id)
        ]

    @classmethod
    def create_custom_log_group(cls, collector: CollectorConfig):
        resp = TransferApi.create_log_group(
            {
                "bk_data_id": collector.bk_data_id,
                "bk_biz_id": collector.get_bk_biz_id(),
                "log_group_name": collector.collector_config_name_en,
                "label": collector.category_id,
                "operator": collector.created_by,
            }
        )
        collector.log_group_id = resp["log_group_id"]
        collector.save(update_fields=["log_group_id"])

        return resp

    def custom_create(
        self,
        bk_biz_id=None,
        collector_config_name=None,
        collector_config_name_en=None,
        data_link_id=None,
        custom_type=None,
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
        bk_app_code=settings.APP_CODE,
        bkdata_biz_id=None,
        is_display=True,
        sort_fields=None,
        target_fields=None,
        collector_scenario_id=CollectorScenarioEnum.CUSTOM.value,
        parent_index_set_ids=None,
    ):
        collector_config_params = {
            "bk_biz_id": bk_biz_id,
            "collector_config_name": collector_config_name,
            "collector_config_name_en": collector_config_name_en,
            "collector_scenario_id": collector_scenario_id,
            "custom_type": custom_type,
            "category_id": category_id,
            "description": description or collector_config_name,
            "data_link_id": int(data_link_id) if data_link_id else 0,
            "bk_app_code": bk_app_code,
            "bkdata_biz_id": bkdata_biz_id,
            "is_display": is_display,
        }
        bkdata_biz_id = bkdata_biz_id or bk_biz_id
        # 判断是否已存在同英文名collector
        if self._pre_check_collector_config_en(model_fields=collector_config_params, bk_biz_id=bkdata_biz_id):
            logger.error(f"collector_config_name_en {collector_config_name_en} already exists")
            raise CollectorConfigNameENDuplicateException(
                CollectorConfigNameENDuplicateException.MESSAGE.format(
                    collector_config_name_en=collector_config_name_en
                )
            )
        # 判断是否已存在同bk_data_name, result_table_id
        bk_data_name = self.build_bk_data_name(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=collector_config_name_en
        )
        result_table_id = self.build_result_table_id(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=collector_config_name_en
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
                logger.warning(f"collector config name duplicate => [{collector_config_name}]")
                raise CollectorConfigNameDuplicateException()

            collector_scenario = CollectorScenario.get_instance(CollectorScenarioEnum.CUSTOM.value)
            self.data.bk_data_id = collector_scenario.update_or_create_data_id(
                bk_data_id=self.data.bk_data_id,
                data_link_id=self.data.data_link_id,
                data_name=self.build_bk_data_name(bkdata_biz_id, collector_config_name_en),
                description=collector_config_params["description"],
                encoding=META_DATA_ENCODING,
                bk_biz_id=bkdata_biz_id,
            )
            self.data.save()

            # 创建索引集，并添加到归属索引集中
            index_set = self.data.create_index_set()
            if parent_index_set_ids:
                IndexSetHandler(index_set.index_set_id).add_to_parent_index_sets(parent_index_set_ids)

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
        async_create_bkdata_data_id.delay(self.data.collector_config_id)

        custom_config = get_custom(custom_type)

        # 仅在有集群ID时创建清洗
        if storage_cluster_id:
            from apps.log_databus.handlers.etl import EtlHandler

            etl_handler = EtlHandler.get_instance(self.data.collector_config_id)
            params = {
                "table_id": collector_config_name_en,
                "storage_cluster_id": storage_cluster_id,
                "retention": retention,
                "allocation_min_days": allocation_min_days,
                "storage_replies": storage_replies,
                "es_shards": es_shards,
                "etl_params": custom_config.etl_params,
                "etl_config": custom_config.etl_config,
                "fields": custom_config.fields,
                "sort_fields": sort_fields,
                "target_fields": target_fields,
            }
            if etl_params and fields:
                # 如果传递了清洗参数，则优先使用
                params.update({"etl_params": etl_params, "etl_config": etl_config, "fields": fields})
            self.data.index_set_id = etl_handler.update_or_create(**params)["index_set_id"]
            self.data.save(update_fields=["index_set_id"])

        custom_config.after_hook(self.data)

        ret = {
            "collector_config_id": self.data.collector_config_id,
            "index_set_id": self.data.index_set_id,
            "bk_data_id": self.data.bk_data_id,
        }

        # create custom Log Group
        if custom_type == CustomTypeEnum.OTLP_LOG.value:
            log_group_info = self.create_custom_log_group(self.data)
            ret.update({"bk_data_token": log_group_info.get("bk_data_token")})
        self._send_create_notify(self.data)

        return ret

    def pre_check(self, params: dict):
        data = {"allowed": False, "message": _("该数据名已重复")}
        bk_biz_id = params.get("bk_biz_id")
        collector_config_name_en = params.get("collector_config_name_en")

        if self._pre_check_collector_config_en(params, bk_biz_id):
            return data

        bk_data_name = params.get("bk_data_name") or self.build_bk_data_name(
            bk_biz_id=bk_biz_id, collector_config_name_en=collector_config_name_en
        )
        bk_data = CollectorConfig(bk_data_name=bk_data_name).get_bk_data_by_name()
        if bk_data:
            return data

        result_table_id = params.get("result_table_id") or self.build_result_table_id(
            bk_biz_id=bk_biz_id, collector_config_name_en=collector_config_name_en
        )
        result_table = CollectorConfig(table_id=result_table_id).get_result_table_by_id()
        if result_table:
            return data

        # 如果采集名不以6-8数字结尾, data.allowed返回True, 反之返回False
        if COLLECTOR_RE.match(collector_config_name_en):
            data.update({"allowed": False, "message": _("采集名不能以6-8位数字结尾")})
        else:
            data.update({"allowed": True, "message": ""})
        return data

    def _pre_check_bk_data_name(self, model_fields: dict, bk_data_name: str):
        if not self.collector_config_id:
            return CollectorConfig(bk_data_name=bk_data_name).get_bk_data_by_name()

        if model_fields["collector_config_name_en"] != self.data.collector_config_name_en:
            return CollectorConfig(bk_data_name=bk_data_name).get_bk_data_by_name()

        return None

    def _pre_check_result_table_id(self, model_fields: dict, result_table_id: str):
        if not self.collector_config_id:
            return CollectorConfig(table_id=result_table_id).get_result_table_by_id()

        if model_fields["collector_config_name_en"] != self.data.collector_config_name_en:
            return CollectorConfig(table_id=result_table_id).get_result_table_by_id()

        return None

    @classmethod
    def _generate_label(cls, obj_dict):
        if not obj_dict or not obj_dict["items"]:
            return []
        obj_item, *_ = obj_dict["items"]
        if not obj_item["metadata"]["labels"]:
            return []
        return [
            {"key": label_key, "value": label_valus}
            for label_key, label_valus in obj_item["metadata"]["labels"].items()
        ]

    def create_or_update_clean_config(self, is_update, params):
        if is_update:
            table_id = self.data.table_id
            # 更新场景，需要把之前的存储设置拿出来，和更新的配置合并一下
            result_table_info = TransferApi.get_result_table_storage(
                {"result_table_list": table_id, "storage_type": "elasticsearch"}
            )
            result_table = result_table_info.get(table_id, {})
            if not result_table:
                raise ResultTableNotExistException(ResultTableNotExistException.MESSAGE.format(table_id))

            default_etl_params = {
                "es_shards": result_table["storage_config"]["index_settings"]["number_of_shards"],
                "storage_replies": result_table["storage_config"]["index_settings"]["number_of_replicas"],
                "storage_cluster_id": result_table["cluster_config"]["cluster_id"],
                "retention": result_table["storage_config"]["retention"],
                "allocation_min_days": params.get("allocation_min_days", 0),
                "etl_config": self.data.etl_config,
            }
            default_etl_params.update(params)
            params = default_etl_params

        from apps.log_databus.handlers.etl import EtlHandler

        etl_handler = EtlHandler.get_instance(self.data.collector_config_id)
        return etl_handler.update_or_create(**params)

    @classmethod
    def _send_create_notify(cls, collector_config: CollectorConfig):
        try:
            space = Space.objects.get(bk_biz_id=collector_config.bk_biz_id)
            space_uid = space.space_uid
            space_name = space.space_name
        except Space.DoesNotExist:
            space_uid = collector_config.bk_biz_id
            space_name = collector_config.bk_biz_id
        content = _(
            "有新采集项创建，请关注！采集项ID: {}, 采集项名称: {}, 空间ID: {}, 空间名称: {}, 创建者: {}, 来源: {}"
        ).format(
            collector_config.collector_config_id,
            collector_config.collector_config_name,
            space_uid,
            space_name,
            collector_config.created_by,
            collector_config.bk_app_code,
        )

        NOTIFY_EVENT(
            content=content,
            dimensions={
                "space_uid": space_uid,
                "collector_name": collector_config.collector_config_name,
                "collector_id": collector_config.collector_config_id,
                "enable_v4": collector_config.enable_v4,
                "msg_type": "create_collector_config",
            },
        )

    @staticmethod
    def get_data_link_id(bk_biz_id: int, data_link_id: int = 0) -> int:
        """
        获取随机的链路ID
        优先级如下:
        1. 传入的data_link_id
        2. 业务可见的私有链路ID
        3. 公共链路ID
        4. 透传0到监控使用监控的默认链路
        """
        if data_link_id:
            return data_link_id
        # 业务可见的私有链路ID
        data_link_obj = (
            DataLinkConfig.objects.filter(bk_biz_id=bk_biz_id, bk_tenant_id=get_request_tenant_id())
            .order_by("data_link_id")
            .first()
        )
        if data_link_obj:
            return data_link_obj.data_link_id
        # 公共链路ID
        data_link_obj = (
            DataLinkConfig.objects.filter(bk_biz_id=0, bk_tenant_id=get_request_tenant_id())
            .order_by("data_link_id")
            .first()
        )
        if data_link_obj:
            return data_link_obj.data_link_id

        return data_link_id

    @staticmethod
    def _build_bk_table_id(bk_biz_id: int, collector_config_name_en: str) -> str:
        """
        根据bk_biz_id和collector_config_name_en构建table_id
        """
        bk_biz_id = int(bk_biz_id)
        if bk_biz_id >= 0:
            bk_table_id = f"{bk_biz_id}_{settings.TABLE_ID_PREFIX}_{collector_config_name_en}"
        else:
            bk_table_id = (
                f"{settings.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{settings.TABLE_ID_PREFIX}_{collector_config_name_en}"
            )
        return bk_table_id

    @staticmethod
    def get_random_public_cluster_id(bk_biz_id: int) -> int:
        from apps.log_databus.handlers.storage import StorageHandler

        # 拥有使用权限的集群列表
        clusters = StorageHandler().get_cluster_groups_filter(bk_biz_id=bk_biz_id)
        for cluster in clusters:
            if cluster.get("storage_cluster_id"):
                return cluster["storage_cluster_id"]

        return 0

    @classmethod
    def build_bk_data_name(cls, bk_biz_id: int, collector_config_name_en: str) -> str:
        """
        根据bk_biz_id和collector_config_name_en构建bk_data_name
        @param bk_biz_id:
        @param collector_config_name_en:
        @return:
        """
        bk_biz_id = int(bk_biz_id)
        if bk_biz_id >= 0:
            bk_data_name = f"{bk_biz_id}_{settings.TABLE_ID_PREFIX}_{collector_config_name_en}"
        else:
            bk_data_name = (
                f"{settings.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{settings.TABLE_ID_PREFIX}_{collector_config_name_en}"
            )
        return bk_data_name

    @classmethod
    def build_result_table_id(cls, bk_biz_id: int, collector_config_name_en: str, is_pattern_rt: bool = False) -> str:
        """
        根据bk_biz_id和collector_config_name_en构建result_table_id
        @param bk_biz_id:
        @param collector_config_name_en:
        @param is_pattern_rt: 是否为聚类结果表
        @return:
        """
        bk_biz_id = int(bk_biz_id)
        if bk_biz_id >= 0:
            result_table_id = f"{bk_biz_id}_{settings.TABLE_ID_PREFIX}.{collector_config_name_en}"
        else:
            result_table_id = (
                f"{settings.TABLE_SPACE_PREFIX}_{-bk_biz_id}_{settings.TABLE_ID_PREFIX}.{collector_config_name_en}"
            )
        if is_pattern_rt:
            return f"{result_table_id}__pattern"
        return result_table_id
