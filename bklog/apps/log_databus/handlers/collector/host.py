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
from typing import Any
from collections import defaultdict
from django.conf import settings
from django.utils.translation import gettext as _
from django.db import IntegrityError, transaction
from apps.api import CCApi, NodeApi, TransferApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.exceptions import ApiRequestError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import FEATURE_COLLECTOR_ITSM
from apps.log_databus.models import CollectorConfig
from apps.log_databus.serializers import (
    FastCollectorCreateSerializer,
    FastCollectorUpdateSerializer,
    CollectorCreateSerializer,
    CollectorUpdateSerializer,
)
from apps.log_databus.tasks.bkdata import async_create_bkdata_data_id
from apps.log_databus.constants import (
    CC_HOST_FIELDS,
    TargetNodeTypeEnum,
    LogPluginInfo,
    CollectStatus,
    BIZ_TOPO_INDEX,
    INTERNAL_TOPO_INDEX,
    SEARCH_BIZ_INST_TOPO_LEVEL,
    BK_SUPPLIER_ACCOUNT,
    RunStatus,
    ETLProcessorChoices,
    CmdbFieldType,
    CC_SCOPE_FIELDS,
    NOT_FOUND_CODE,
)
from apps.log_databus.exceptions import (
    CollectorCreateOrUpdateSubscriptionException,
    CollectorActiveException,
    CollectorConfigNameENDuplicateException,
    CollectorBkDataNameDuplicateException,
    CollectorResultTableIDDuplicateException,
    CollectorConfigNameDuplicateException,
    ModifyCollectorConfigException,
    PublicESClusterNotExistException,
    CollectorIllegalIPException,
)

from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_search.constants import CMDB_HOST_SEARCH_FIELDS
from apps.models import model_to_dict

from apps.log_databus.handlers.collector import CollectorHandler


from apps.log_search.handlers.biz import BizHandler
from apps.log_search.models import LogIndexSet, Space

from apps.utils.local import get_request_username
from apps.utils.log import logger


class HostCollectorHandler(CollectorHandler):
    FAST_CREATE_SERIALIZER = FastCollectorCreateSerializer
    FAST_UPDATE_SERIALIZER = FastCollectorUpdateSerializer
    CREATE_SERIALIZER = CollectorCreateSerializer
    UPDATE_SERIALIZER = CollectorUpdateSerializer

    def _pre_start(self):
        # 启动节点管理订阅功能
        if self.data.subscription_id:
            NodeApi.switch_subscription(
                {"subscription_id": self.data.subscription_id, "action": "enable", "bk_biz_id": self.data.bk_biz_id}
            )

    @transaction.atomic
    def start(self, **kwargs):
        super().start()
        if self.data.subscription_id:
            return self._run_subscription_task()
        return True

    def _pre_stop(self):
        if self.data.subscription_id:
            # 停止节点管理订阅功能
            NodeApi.switch_subscription(
                {"subscription_id": self.data.subscription_id, "action": "disable", "bk_biz_id": self.data.bk_biz_id}
            )

    @transaction.atomic
    def stop(self, **kwargs):
        super().stop()
        if self.data.subscription_id:
            return self._run_subscription_task("STOP")
        return True

    def _pre_destroy(self):
        """
        删除订阅事件
        :return: [dict]
        {
            "message": "",
            "code": "OK",
            "data": null,
            "result": true
        }
        """
        if not self.data.subscription_id:
            return
        subscription_params = {"subscription_id": self.data.subscription_id, "bk_biz_id": self.data.bk_biz_id}
        return NodeApi.delete_subscription(subscription_params)

    def run(self, action, scope):
        if self.data.subscription_id:
            return self._run_subscription_task(action=action, scope=scope)
        return True

    def diff_target_nodes(self, target_nodes: list) -> list:
        """
        比较订阅节点的变化
        :param target_nodes 目标节点
        :return
        [
            {
                'type': 'add',
                'bk_inst_id': 2,
                'bk_obj_id': 'biz'
            },
            {
                'type': 'add',
                'bk_inst_id': 3,
                'bk_obj_id': 'module'
            },
            {
                'type': 'delete',
                'bk_inst_id': 4,
                'bk_obj_id': 'set'
            },
            {
                'type': 'modify',
                'bk_inst_id': 5,
                'bk_obj_id': 'module'
            }
        ]
        """

        def genera_nodes_tuples(nodes):
            return [
                (node["bk_inst_id"], node["bk_obj_id"]) for node in nodes if "bk_inst_id" in node or "bk_obj_id" in node
            ]

        current_nodes_tuples = genera_nodes_tuples(self.data.target_nodes)
        target_nodes_tuples = genera_nodes_tuples(target_nodes)
        add_nodes = [
            {"type": "add", "bk_inst_id": node[0], "bk_obj_id": node[1]}
            for node in set(target_nodes_tuples) - set(current_nodes_tuples)
        ]
        delete_nodes = [
            {"type": "delete", "bk_inst_id": node[0], "bk_obj_id": node[1]}
            for node in set(current_nodes_tuples) - set(target_nodes_tuples)
        ]
        return add_nodes + delete_nodes

    def update_or_create(self, params: dict) -> dict:
        """
        创建采集配置
        :return:
        {
            "collector_config_id": 1,
            "collector_config_name": "采集项名称",
            "bk_data_id": 2001,
            "subscription_id": 1,
            "task_id_list": [1]
        }
        """
        if self.data and not self.data.is_active:
            raise CollectorActiveException()
        collector_config_name = params["collector_config_name"]
        collector_config_name_en = params["collector_config_name_en"]
        target_object_type = params["target_object_type"]
        target_node_type = params["target_node_type"]
        target_nodes = params["target_nodes"]
        data_encoding = params["data_encoding"]
        description = params.get("description") or collector_config_name
        bk_biz_id = params.get("bk_biz_id") or self.data.bk_biz_id
        is_display = params.get("is_display", True)
        params["params"]["encoding"] = data_encoding
        params["params"]["run_task"] = params.get("run_task", True)

        # cmdb元数据补充
        extra_labels = params["params"].get("extra_labels")
        if extra_labels:
            for item in extra_labels:
                if item["value"] == CmdbFieldType.HOST.value and item["key"] in CC_HOST_FIELDS:
                    item["value"] = "{{cmdb_instance." + item["value"] + "." + item["key"] + "}}"
                    item["key"] = "host.{}".format(item["key"])
                if item["value"] == CmdbFieldType.SCOPE.value and item["key"] in CC_SCOPE_FIELDS:
                    item["value"] = "{{cmdb_instance.host.relations[0]." + item["key"] + "}}"
                    item["key"] = "host.{}".format(item["key"])

        # 1. 创建CollectorConfig记录
        model_fields = {
            "collector_config_name": collector_config_name,
            "collector_config_name_en": collector_config_name_en,
            "target_object_type": target_object_type,
            "target_node_type": target_node_type,
            "target_nodes": target_nodes,
            "description": description,
            "data_encoding": data_encoding,
            "params": params["params"],
            "is_active": True,
            "is_display": is_display,
            "extra_labels": params["params"].get("extra_labels", []),
        }

        if "environment" in params:
            # 如果传了 environment 就设置，不传就不设置
            model_fields["environment"] = params["environment"]

        # 判断是否存在非法IP列表
        self._cat_illegal_ips(params)

        is_create = False

        # 判断是否已存在同英文名collector
        if self._pre_check_collector_config_en(model_fields=model_fields, bk_biz_id=bk_biz_id):
            logger.error(f"collector_config_name_en {collector_config_name_en} already exists")
            raise CollectorConfigNameENDuplicateException(
                CollectorConfigNameENDuplicateException.MESSAGE.format(
                    collector_config_name_en=collector_config_name_en
                )
            )
        # 判断是否已存在同bk_data_name, result_table_id
        bkdata_biz_id = params.get("bkdata_biz_id") or bk_biz_id
        bk_data_name = self.build_bk_data_name(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=collector_config_name_en
        )
        result_table_id = self.build_result_table_id(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=collector_config_name_en
        )
        if self._pre_check_bk_data_name(model_fields=model_fields, bk_data_name=bk_data_name):
            logger.error(f"bk_data_name {bk_data_name} already exists")
            raise CollectorBkDataNameDuplicateException(
                CollectorBkDataNameDuplicateException.MESSAGE.format(bk_data_name=bk_data_name)
            )
        if self._pre_check_result_table_id(model_fields=model_fields, result_table_id=result_table_id):
            logger.error(f"result_table_id {result_table_id} already exists")
            raise CollectorResultTableIDDuplicateException(
                CollectorResultTableIDDuplicateException.MESSAGE.format(result_table_id=result_table_id)
            )
        # 2. 创建/更新采集项，并同步到bk_data_id
        with transaction.atomic():
            try:
                # 2.1 创建/更新采集项
                if not self.data:
                    data_link_id = int(params.get("data_link_id") or 0)
                    # 创建后不允许修改的字段
                    model_fields.update(
                        {
                            "category_id": params["category_id"],
                            "collector_scenario_id": params["collector_scenario_id"],
                            "bk_biz_id": bk_biz_id,
                            "bkdata_biz_id": params.get("bkdata_biz_id"),
                            "data_link_id": self.get_data_link_id(bk_biz_id=bk_biz_id, data_link_id=data_link_id),
                            "bk_data_id": params.get("bk_data_id"),
                            "etl_processor": params.get("etl_processor", ETLProcessorChoices.TRANSFER.value),
                            "etl_config": params.get("etl_config"),
                            "collector_plugin_id": params.get("collector_plugin_id"),
                        }
                    )
                    model_fields["collector_scenario_id"] = params["collector_scenario_id"]
                    self.data = CollectorConfig.objects.create(**model_fields)
                    is_create = True
                else:
                    _collector_config_name = copy.deepcopy(self.data.collector_config_name)
                    if self.data.bk_data_id and self.data.bk_data_name != bk_data_name:
                        TransferApi.modify_data_id({"data_id": self.data.bk_data_id, "data_name": bk_data_name})
                        logger.info(
                            f"[modify_data_name] bk_data_id=>{self.data.bk_data_id}, data_name {self.data.bk_data_name}=>{bk_data_name}"
                        )
                        self.data.bk_data_name = bk_data_name

                    # 当更新itsm流程时 将diff更新前移
                    if not FeatureToggleObject.switch(name=FEATURE_COLLECTOR_ITSM):
                        self.data.target_subscription_diff = self.diff_target_nodes(target_nodes)

                    if "collector_scenario_id" in params:
                        model_fields["collector_scenario_id"] = params["collector_scenario_id"]

                    for key, value in model_fields.items():
                        setattr(self.data, key, value)
                    self.data.save()

                    # collector_config_name更改后更新索引集名称
                    if _collector_config_name != self.data.collector_config_name and self.data.index_set_id:
                        index_set_name = _("[采集项]") + self.data.collector_config_name
                        LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).update(
                            index_set_name=index_set_name
                        )

                # 2.2 meta-创建或更新数据源
                if params.get("is_allow_alone_data_id", True):
                    if self.data.etl_processor == ETLProcessorChoices.BKBASE.value:
                        # 兼容平台账号
                        if params.get("platform_username"):
                            setattr(self.data, "__platform_username", params["platform_username"])
                        # 创建
                        transfer_data_id = self.update_or_create_data_id(
                            self.data, etl_processor=ETLProcessorChoices.TRANSFER.value
                        )
                        self.data.bk_data_id = self.update_or_create_data_id(self.data, bk_data_id=transfer_data_id)
                    else:
                        self.data.bk_data_id = self.update_or_create_data_id(self.data)
                    self.data.save()

            except IntegrityError:
                logger.warning(f"collector config name duplicate => [{collector_config_name}]")
                raise CollectorConfigNameDuplicateException()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.CREATE if is_create else UserOperationActionEnum.UPDATE,
            "params": model_to_dict(self.data, exclude=["deleted_at", "created_at", "updated_at"]),
        }
        user_operation_record.delay(operation_record)

        if is_create:
            self._authorization_collector(self.data)
            self._send_create_notify(self.data)
        try:
            collector_scenario = CollectorScenario.get_instance(self.data.collector_scenario_id)
            self._update_or_create_subscription(
                collector_scenario=collector_scenario, params=params["params"], is_create=is_create
            )
        finally:
            if (
                params.get("is_allow_alone_data_id", True)
                and params.get("etl_processor") != ETLProcessorChoices.BKBASE.value
            ):
                # 创建数据平台data_id
                async_create_bkdata_data_id.delay(self.data.collector_config_id)

        return {
            "collector_config_id": self.data.collector_config_id,
            "collector_config_name": self.data.collector_config_name,
            "bk_data_id": self.data.bk_data_id,
            "subscription_id": self.data.subscription_id,
            "task_id_list": self.data.task_id_list,
        }

    @classmethod
    def _filter_illegal_ip_and_host_id(cls, bk_biz_id: int, ips: list = None, bk_host_ids: list = None):
        """
        过滤出非法ip列表
        @param bk_biz_id [Int] 业务id
        @param ips [List] ip列表
        """
        ips = ips or []
        bk_host_ids = bk_host_ids or []
        legal_host_list = CCApi.list_biz_hosts.bulk_request(
            {
                "bk_biz_id": bk_biz_id,
                "host_property_filter": {
                    "condition": "OR",
                    "rules": [
                        {"field": "bk_host_innerip", "operator": "in", "value": ips},
                        {"field": "bk_host_id", "operator": "in", "value": bk_host_ids},
                    ],
                },
                "fields": CMDB_HOST_SEARCH_FIELDS,
            }
        )

        legal_ip_set = {legal_host["bk_host_innerip"] for legal_host in legal_host_list}
        legal_host_id_set = {legal_host["bk_host_id"] for legal_host in legal_host_list}

        illegal_ips = [ip for ip in ips if ip not in legal_ip_set]
        illegal_bk_host_ids = [host_id for host_id in bk_host_ids if host_id not in legal_host_id_set]
        return illegal_ips, illegal_bk_host_ids

    def _cat_illegal_ips(self, params: dict):
        """
        当采集项对应节点为静态主机时判定是否有非法越权IP
        @param params {dict} 创建或者编辑采集项时的请求
        """
        # 这里是为了避免target_node_type, target_nodes参数为空的情况
        target_node_type = params.get("target_node_type")
        target_nodes = params.get("target_nodes", [])
        bk_biz_id = params["bk_biz_id"] if not self.data else self.data.bk_biz_id
        if target_node_type and target_node_type == TargetNodeTypeEnum.INSTANCE.value:
            illegal_ips, illegal_bk_host_ids = self._filter_illegal_ip_and_host_id(
                bk_biz_id=bk_biz_id,
                ips=[target_node["ip"] for target_node in target_nodes if "ip" in target_node],
                bk_host_ids=[target_node["bk_host_id"] for target_node in target_nodes if "bk_host_id" in target_node],
            )
            if illegal_ips or illegal_bk_host_ids:
                illegal_items = [str(item) for item in (illegal_ips + illegal_bk_host_ids)]
                logger.error(f"cat illegal ip or bk_host_id: {illegal_items}")
                raise CollectorIllegalIPException(
                    CollectorIllegalIPException.MESSAGE.format(bk_biz_id=bk_biz_id, illegal_ips=illegal_items)
                )

    @transaction.atomic
    def only_create_or_update_model(self, params):
        """
        only_create_or_update_model
        @param params:
        @return:
        """
        if self.data and not self.data.is_active:
            raise CollectorActiveException()
        model_fields = {
            "collector_config_name": params["collector_config_name"],
            "collector_config_name_en": params["collector_config_name_en"],
            "target_object_type": params["target_object_type"],
            "target_node_type": params["target_node_type"],
            "target_nodes": params["target_nodes"],
            "description": params.get("description") or params["collector_config_name"],
            "is_active": True,
            "data_encoding": params["data_encoding"],
            "params": params["params"],
            "environment": params["environment"],
            "extra_labels": params["params"].get("extra_labels", []),
        }

        bk_biz_id = params.get("bk_biz_id") or self.data.bk_biz_id
        collector_config_name_en = params["collector_config_name_en"]

        # 判断是否存在非法IP列表
        self._cat_illegal_ips(params)
        # 判断是否已存在同英文名collector
        if self._pre_check_collector_config_en(model_fields=model_fields, bk_biz_id=bk_biz_id):
            logger.error(f"collector_config_name_en {collector_config_name_en} already exists")
            raise CollectorConfigNameENDuplicateException(
                CollectorConfigNameENDuplicateException.MESSAGE.format(
                    collector_config_name_en=collector_config_name_en
                )
            )
        # 判断是否已存在同bk_data_name, result_table_id
        bk_data_name = self.build_bk_data_name(bk_biz_id=bk_biz_id, collector_config_name_en=collector_config_name_en)
        result_table_id = self.build_result_table_id(
            bk_biz_id=bk_biz_id, collector_config_name_en=collector_config_name_en
        )
        if self._pre_check_bk_data_name(model_fields=model_fields, bk_data_name=bk_data_name):
            logger.error(f"bk_data_name {bk_data_name} already exists")
            raise CollectorBkDataNameDuplicateException(
                CollectorBkDataNameDuplicateException.MESSAGE.format(bk_data_name=bk_data_name)
            )
        if self._pre_check_result_table_id(model_fields=model_fields, result_table_id=result_table_id):
            logger.error(f"result_table_id {result_table_id} already exists")
            raise CollectorResultTableIDDuplicateException(
                CollectorResultTableIDDuplicateException.MESSAGE.format(result_table_id=result_table_id)
            )
        is_create = False
        try:
            if not self.data:
                model_fields.update(
                    {
                        "category_id": params["category_id"],
                        "collector_scenario_id": params["collector_scenario_id"],
                        "bk_biz_id": bk_biz_id,
                        "bkdata_biz_id": params.get("bkdata_biz_id"),
                        "data_link_id": int(params["data_link_id"]) if params.get("data_link_id") else 0,
                        "bk_data_id": params.get("bk_data_id"),
                        "etl_processor": params.get("etl_processor", ETLProcessorChoices.TRANSFER.value),
                        "etl_config": params.get("etl_config"),
                        "collector_plugin_id": params.get("collector_plugin_id"),
                    }
                )
                self.data = CollectorConfig.objects.create(**model_fields)
                is_create = True
            else:
                _collector_config_name = self.data.collector_config_name
                if self.data.bk_data_id and self.data.bk_data_name != bk_data_name:
                    TransferApi.modify_data_id({"data_id": self.data.bk_data_id, "data_name": bk_data_name})
                    logger.info(
                        f"[modify_data_name] bk_data_id=>{self.data.bk_data_id}, data_name {self.data.bk_data_name}=>{bk_data_name}"
                    )
                    self.data.bk_data_name = bk_data_name

                # 当更新itsm流程时 将diff更新前移
                if not FeatureToggleObject.switch(name=FEATURE_COLLECTOR_ITSM):
                    self.data.target_subscription_diff = self.diff_target_nodes(params["target_nodes"])
                for key, value in model_fields.items():
                    setattr(self.data, key, value)
                self.data.save()

                # collector_config_name更改后更新索引集名称
                if _collector_config_name != self.data.collector_config_name and self.data.index_set_id:
                    index_set_name = _("[采集项]") + self.data.collector_config_name
                    LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).update(
                        index_set_name=index_set_name
                    )

            if params.get("is_allow_alone_data_id", True):
                if self.data.etl_processor == ETLProcessorChoices.BKBASE.value:
                    transfer_data_id = self.update_or_create_data_id(
                        self.data, etl_processor=ETLProcessorChoices.TRANSFER.value
                    )
                    self.data.bk_data_id = self.update_or_create_data_id(self.data, bk_data_id=transfer_data_id)
                else:
                    self.data.bk_data_id = self.update_or_create_data_id(self.data)
                self.data.save()

        except IntegrityError:
            logger.warning(f"collector config name duplicate => [{params['collector_config_name']}]")
            raise CollectorConfigNameDuplicateException()

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.CREATE if is_create else UserOperationActionEnum.UPDATE,
            "params": params,
        }
        user_operation_record.delay(operation_record)

        if is_create:
            self._authorization_collector(self.data)

        return model_to_dict(self.data)

    def get_subscription_task_detail(self, instance_id, task_id=None):
        """
        采集任务实例日志详情
        :param [string] instance_id: 实例ID
        :param [string] task_id: 任务ID
        :return: [dict]
        """
        # 详情接口查询，原始日志
        param = {
            "subscription_id": self.data.subscription_id,
            "instance_id": instance_id,
            "bk_biz_id": self.data.bk_biz_id,
        }
        if task_id:
            param["task_id"] = task_id
        detail_result = NodeApi.get_subscription_task_detail(param)

        # 日志详情，用于前端展示
        log = list()
        for step in detail_result.get("steps", []):
            log.append("{}{}{}\n".format("=" * 20, step["node_name"], "=" * 20))
            for sub_step in step["target_hosts"][0].get("sub_steps", []):
                log.extend(["{}{}{}".format("-" * 20, sub_step["node_name"], "-" * 20), sub_step["log"]])
                # 如果ex_data里面有值，则在日志里加上它
                if sub_step["ex_data"]:
                    log.append(sub_step["ex_data"])
                if sub_step["status"] != CollectStatus.SUCCESS:
                    return {"log_detail": "\n".join(log), "log_result": detail_result}
        return {"log_detail": "\n".join(log), "log_result": detail_result}

    def _retry_subscription(self, instance_id_list):
        params = {
            "subscription_id": self.data.subscription_id,
            "instance_id_list": instance_id_list,
            "bk_biz_id": self.data.bk_biz_id,
        }

        task_id = str(NodeApi.retry_subscription(params)["task_id"])
        self.data.task_id_list.append(task_id)
        self.data.save()
        return self.data.task_id_list

    def retry_target_nodes(self, instance_id_list):
        """
        重试部分实例或主机
        @param instance_id_list:
        @return:
        """
        res = self._retry_subscription(instance_id_list=instance_id_list)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.RETRY,
            "params": {"instance_id_list": instance_id_list},
        }
        user_operation_record.delay(operation_record)

        return res

    def retry_instances(self, instance_id_list):
        """
        重试部分实例或主机
        @param instance_id_list:
        @return:
        """
        res = self._retry_subscription(instance_id_list=instance_id_list)

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "biz_id": self.data.bk_biz_id,
            "record_type": UserOperationTypeEnum.COLLECTOR,
            "record_object_id": self.data.collector_config_id,
            "action": UserOperationActionEnum.RETRY,
            "params": {"instance_id_list": instance_id_list},
        }
        user_operation_record.delay(operation_record)

        return res

    @staticmethod
    def get_instance_log(instance_obj):
        """
        获取采集实例日志
        :param  [dict] instance_obj: 实例状态日志
        :return: [string]
        """
        for step_obj in instance_obj.get("steps", []):
            if step_obj == CollectStatus.SUCCESS:
                continue
            for sub_step_obj in step_obj["target_hosts"][0]["sub_steps"]:
                if sub_step_obj["status"] != CollectStatus.SUCCESS:
                    return "{}-{}".format(step_obj["node_name"], sub_step_obj["node_name"])
        return ""

    def format_task_instance_status(self, instance_data):
        """
        格式化任务状态数据
        :param  [list] instance_data: 任务状态data数据
        :return: [list]
        """
        instance_list = list()
        host_list = list()
        latest_id = self.data.task_id_list[-1]
        if self.data.target_node_type == TargetNodeTypeEnum.INSTANCE.value:
            for node in self.data.target_nodes:
                if "bk_host_id" in node:
                    host_list.append(node["bk_host_id"])
                else:
                    host_list.append((node["ip"], node["bk_cloud_id"]))

        for instance_obj in instance_data:
            bk_cloud_id = instance_obj["instance_info"]["host"]["bk_cloud_id"]
            if isinstance(bk_cloud_id, list):
                bk_cloud_id = bk_cloud_id[0]["bk_inst_id"]
            bk_host_innerip = instance_obj["instance_info"]["host"]["bk_host_innerip"]
            bk_host_id = instance_obj["instance_info"]["host"]["bk_host_id"]

            # 静态节点：排除订阅任务历史IP（不是最新订阅且不在当前节点范围的ip）
            if (
                self.data.target_node_type == TargetNodeTypeEnum.INSTANCE.value
                and str(instance_obj["task_id"]) != latest_id
                and ((bk_host_innerip, bk_cloud_id) not in host_list and bk_host_id not in host_list)
            ):
                continue
            instance_list.append(
                {
                    "host_id": bk_host_id,
                    "status": instance_obj["status"],
                    "ip": bk_host_innerip,
                    "ipv6": instance_obj["instance_info"]["host"].get("bk_host_innerip_v6", ""),
                    "host_name": instance_obj["instance_info"]["host"]["bk_host_name"],
                    "cloud_id": bk_cloud_id,
                    "log": self.get_instance_log(instance_obj),
                    "instance_id": instance_obj["instance_id"],
                    "instance_name": bk_host_innerip,
                    "task_id": instance_obj.get("task_id", ""),
                    "bk_supplier_id": instance_obj["instance_info"]["host"].get("bk_supplier_account"),
                    "create_time": instance_obj["create_time"],
                    "steps": {i["id"]: i["action"] for i in instance_obj.get("steps", []) if i["action"]},
                }
            )
        return instance_list

    def _get_collect_node(self):
        """
        获取target_nodes和target_subscription_diff集合之后组成的node_collect
        """
        node_collect = copy.deepcopy(self.data.target_nodes)
        for target_obj in self.data.target_subscription_diff:
            node_dic = {"bk_inst_id": target_obj["bk_inst_id"], "bk_obj_id": target_obj["bk_obj_id"]}
            if node_dic not in node_collect:
                node_collect.append(node_dic)
        return node_collect

    def get_biz_internal_module(self):
        internal_module = CCApi.get_biz_internal_module(
            {"bk_biz_id": self.data.bk_biz_id, "bk_supplier_account": BK_SUPPLIER_ACCOUNT}
        )
        internal_topo = {
            "host_count": 0,
            "default": 0,
            "bk_obj_name": _("集群"),
            "bk_obj_id": "set",
            "child": [
                {
                    "host_count": 0,
                    "default": _module.get("default", 0),
                    "bk_obj_name": _("模块"),
                    "bk_obj_id": "module",
                    "child": [],
                    "bk_inst_id": _module["bk_module_id"],
                    "bk_inst_name": _module["bk_module_name"],
                }
                for _module in internal_module.get("module", [])
            ],
            "bk_inst_id": internal_module["bk_set_id"],
            "bk_inst_name": internal_module["bk_set_name"],
        }
        return internal_topo

    def _get_biz_topo(self):
        """
        查询业务TOPO，按采集目标节点进行分类
        """
        biz_topo = CCApi.search_biz_inst_topo({"bk_biz_id": self.data.bk_biz_id, "level": SEARCH_BIZ_INST_TOPO_LEVEL})
        try:
            internal_topo = self.get_biz_internal_module()
            if internal_topo:
                biz_topo[BIZ_TOPO_INDEX]["child"].insert(INTERNAL_TOPO_INDEX, internal_topo)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"call CCApi.search_biz_inst_topo error: {e}")
            pass
        return biz_topo

    def get_node_mapping(self, topo_tree):
        """
        节点映射关系
        :param  [list] topo_tree: 拓扑树
        :return: [dict]
        """
        node_mapping = {}

        def mapping(node, node_link, node_mapping):
            node.update(node_link=node_link)
            node_mapping[node_link[-1]] = node

        BizHandler().foreach_topo_tree(topo_tree, mapping, node_mapping=node_mapping)
        return node_mapping

    def _get_template_mapping(self, node_collect):
        """
        获取模板dict
        @param node_collect {List} _get_collect_node处理后组成的node_collect
        """
        service_template_mapping = {}
        set_template_mapping = {}
        bk_boj_id_set = {node_obj["bk_obj_id"] for node_obj in node_collect}

        if TargetNodeTypeEnum.SERVICE_TEMPLATE.value in bk_boj_id_set:
            service_templates = CCApi.list_service_template.bulk_request({"bk_biz_id": self.data.bk_biz_id})
            service_template_mapping = {
                "{}|{}".format(TargetNodeTypeEnum.SERVICE_TEMPLATE.value, str(template.get("id", ""))): {
                    "name": template.get("name")
                }
                for template in service_templates
            }

        if TargetNodeTypeEnum.SET_TEMPLATE.value in bk_boj_id_set:
            set_templates = CCApi.list_set_template.bulk_request({"bk_biz_id": self.data.bk_biz_id})
            set_template_mapping = {
                "{}|{}".format(TargetNodeTypeEnum.SET_TEMPLATE.value, str(template.get("id", ""))): {
                    "name": template.get("name")
                }
                for template in set_templates
            }

        return {**service_template_mapping, **set_template_mapping}

    def _get_mapping(self, node_collect):
        """
        查询业务TOPO，按采集目标节点进行分类
        node_collect {List} _get_collect_node处理后组成的node_collect
        """
        biz_topo = self._get_biz_topo()
        node_mapping = self.get_node_mapping(biz_topo)
        template_mapping = self._get_template_mapping(node_collect=node_collect)

        return node_mapping, template_mapping

    def get_target_mapping(self) -> dict:
        """
        节点和标签映射关系
        :return: [dict] {"module|33": "modify", "set|6": "add", "set|7": "delete"}
        """
        target_mapping = dict()
        for target in self.data.target_subscription_diff:
            key = "{}|{}".format(target["bk_obj_id"], target["bk_inst_id"])
            target_mapping[key] = target["type"]
        return target_mapping

    def _get_host_result(self, node_collect):
        """
        根据业务、节点查询主机
        node_collect {List} _get_collect_node处理后组成的node_collect
        """
        conditions = [
            {"bk_obj_id": node_obj["bk_obj_id"], "bk_inst_id": node_obj["bk_inst_id"]} for node_obj in node_collect
        ]
        host_result = BizHandler(self.data.bk_biz_id).search_host(conditions)
        host_result_dict = defaultdict(list)
        for host in host_result:
            for inst_id in host["parent_inst_id"]:
                key = "{}|{}".format(str(host["bk_obj_id"]), str(inst_id))
                host_result_dict[key].append((host["bk_host_innerip"], host["bk_cloud_id"]))
                host_result_dict[key].append(host["bk_host_id"])
        return host_result_dict

    def _get_dynamic_group_hosts(self, node_collect) -> dict:
        """
        获取动态分组主机信息
        @param node_collect {List} _get_collect_node处理后组成的node_collect
        """
        host_result_dict = defaultdict(list)
        for node_obj in node_collect:
            key = "{}|{}".format(str(node_obj["bk_obj_id"]), str(node_obj["bk_inst_id"]))
            host_result = CCApi.execute_dynamic_group.bulk_request(
                params={
                    "bk_biz_id": self.data.bk_biz_id,
                    "id": node_obj["bk_inst_id"],
                    "fields": CMDB_HOST_SEARCH_FIELDS,
                }
            )
            for host in host_result:
                host_result_dict[key].append((host["bk_host_innerip"], host["bk_cloud_id"]))
                host_result_dict[key].append(host["bk_host_id"])
        return host_result_dict

    @staticmethod
    def _get_dynamic_group_info(bk_biz_id) -> dict:
        """
        查询业务下所有动态分组信息
        """
        dynamic_group_list = CCApi.search_dynamic_group.bulk_request(
            params={"bk_biz_id": bk_biz_id, "no_request": True}
        )
        return {group["id"]: group for group in dynamic_group_list}

    @classmethod
    def _get_node_obj(cls, node_obj, template_mapping, node_mapping, map_key):
        """
        获取node_path, bk_obj_name, bk_inst_name
        @param node_obj {dict} _get_collect_node处理后组成的node_collect对应元素
        @param template_mapping {dict} 模板集合
        @param node_mapping {dict} 拓扑节点集合
        @param map_key {str} 集合对应key
        """

        if node_obj["bk_obj_id"] in [
            TargetNodeTypeEnum.SET_TEMPLATE.value,
            TargetNodeTypeEnum.SERVICE_TEMPLATE.value,
        ]:
            node_path = template_mapping.get(map_key, {}).get("name", "")
            bk_obj_name = TargetNodeTypeEnum.get_choice_label(node_obj["bk_obj_id"])
            bk_inst_name = template_mapping.get(map_key, {}).get("name", "")
            return node_path, bk_obj_name, bk_inst_name

        node_path = "_".join(
            [node_mapping.get(node).get("bk_inst_name") for node in node_mapping.get(map_key, {}).get("node_link", [])]
        )
        bk_obj_name = node_mapping.get(map_key, {}).get("bk_obj_name", "")
        bk_inst_name = node_mapping.get(map_key, {}).get("bk_inst_name", "")

        return node_path, bk_obj_name, bk_inst_name

    def _get_status_content(self, instance_status: list, is_task=False) -> list:
        """
        获取采集任务/订阅状态内容
        @param instance_status {List} 实例列表
        """
        target_node_type = self.data.target_node_type

        # 如果采集目标是HOST-INSTANCE
        if target_node_type == TargetNodeTypeEnum.INSTANCE.value:
            content_data = [
                {
                    "is_label": False,
                    "label_name": "",
                    "bk_obj_name": _("主机"),
                    "node_path": _("主机"),
                    "bk_obj_id": "host",
                    "bk_inst_id": "",
                    "bk_inst_name": "",
                    "child": instance_status,
                }
            ]
            return content_data

        # 如果采集目标是HOST - TOPO 或 HOST - DYNAMIC_GROUP
        # 如果是查询采集任务状态，获取target_nodes获取采集目标及差异节点target_subscription_diff合集
        node_collect = self._get_collect_node() if is_task else self.data.target_nodes
        target_mapping = self.get_target_mapping() if is_task else {}

        if target_node_type == TargetNodeTypeEnum.DYNAMIC_GROUP.value:
            total_host_result = self._get_dynamic_group_hosts(node_collect)
            node_mapping, template_mapping = {}, {}
            dynamic_group_info = self._get_dynamic_group_info(self.data.bk_biz_id)
        else:
            total_host_result = self._get_host_result(node_collect)
            node_mapping, template_mapping = self._get_mapping(node_collect)
            dynamic_group_info = {}

        content_data = list()
        for node_obj in node_collect:
            map_key = "{}|{}".format(node_obj["bk_obj_id"], node_obj["bk_inst_id"])
            host_result = set(total_host_result.get(map_key, []))
            label_name = target_mapping.get(map_key, "") if is_task else ""

            content_obj = {
                "is_label": False if not label_name else True,
                "label_name": label_name,
                "bk_obj_id": node_obj["bk_obj_id"],
                "bk_inst_id": node_obj["bk_inst_id"],
                "child": [],
            }

            if target_node_type == TargetNodeTypeEnum.DYNAMIC_GROUP.value:
                dynamic_group_name = dynamic_group_info.get(content_obj["bk_inst_id"], {}).get("name", "")
                content_obj["bk_inst_name"] = dynamic_group_name
                content_obj["node_path"] = dynamic_group_name
                content_obj["bk_obj_name"] = _("主机")
            else:
                node_path, bk_obj_name, bk_inst_name = self._get_node_obj(
                    node_obj, template_mapping, node_mapping, map_key
                )
                content_obj["node_path"] = node_path
                content_obj["bk_obj_name"] = bk_obj_name
                content_obj["bk_inst_name"] = bk_inst_name

            for instance_obj in instance_status:
                # delete 标签如果任务状态action不为UNINSTALL
                if is_task and label_name == "delete" and instance_obj["steps"].get(LogPluginInfo.NAME) != "UNINSTALL":
                    continue
                # 因为instance_obj兼容新版IP选择器的字段名, 所以这里的bk_cloud_id->cloud_id, bk_host_id->host_id
                if (instance_obj["ip"], instance_obj["cloud_id"]) in host_result or instance_obj[
                    "host_id"
                ] in host_result:
                    content_obj["child"].append(instance_obj)
            content_data.append(content_obj)

        return content_data

    def get_task_status(self, id_list):
        """
        查询物理机采集任务状态
        :param  [list] id_list:
        :return: [dict]
        {
            "contents": [
                {
                "is_label": true,
                "label_name": "modify",
                "bk_obj_name": "模块",
                "node_path": "蓝鲸_test1_配置平台_adminserver",
                "bk_obj_id": "module",
                "bk_inst_id": 33,
                "bk_inst_name": "adminserver",
                "child": [
                    {
                        "bk_host_id": 1,
                        "status": "FAILED",
                        "ip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "log": "[unifytlogc] 下发插件配置-重载插件进程",
                        "instance_id": "host|instance|host|127.0.0.1-0-0",
                        "instance_name": "127.0.0.1",
                        "task_id": 24516,
                        "bk_supplier_id": "0",
                        "create_time": "2019-09-17 19:23:02",
                        "steps": {1 item}
                        }
                    ]
                }
            ]
        }
        """
        if self.data.is_custom_scenario:
            return {"task_ready": True, "contents": []}

        if not self.data.subscription_id:
            self._update_or_create_subscription(
                collector_scenario=CollectorScenario.get_instance(
                    collector_scenario_id=self.data.collector_scenario_id
                ),
                params=self.data.params,
            )

        status_result = NodeApi.get_subscription_task_status.bulk_request(
            params={
                "subscription_id": self.data.subscription_id,
                "need_detail": False,
                "need_aggregate_all_tasks": True,
                "need_out_of_scope_snapshots": False,
                "bk_biz_id": self.data.bk_biz_id,
            },
            get_data=lambda x: x["list"],
            get_count=lambda x: x["total"],
        )
        instance_status = self.format_task_instance_status(status_result)

        return {"task_ready": True, "contents": self._get_status_content(instance_status, is_task=True)}

    @staticmethod
    def format_subscription_instance_status(instance_data, plugin_data):
        """
        对订阅状态数据按照实例运行状态进行归类
        :param [dict] instance_data:
        :param [dict] plugin_data:
        :return: [dict]
        """
        plugin_status_mapping = {}
        for plugin_obj in plugin_data:
            for item in plugin_obj["plugin_status"]:
                if item["name"] == "bkunifylogbeat":
                    plugin_status_mapping[plugin_obj["bk_host_id"]] = item

        instance_list = list()
        for instance_obj in instance_data:
            # 日志采集暂时只支持本地采集
            bk_host_id = instance_obj["instance_info"]["host"]["bk_host_id"]
            plugin_statuses = plugin_status_mapping.get(bk_host_id, {})
            if instance_obj["status"] in [CollectStatus.PENDING, CollectStatus.RUNNING]:
                status = CollectStatus.RUNNING
                status_name = RunStatus.RUNNING
            elif instance_obj["status"] == CollectStatus.SUCCESS:
                status = CollectStatus.SUCCESS
                status_name = RunStatus.SUCCESS
            else:
                status = CollectStatus.FAILED
                status_name = RunStatus.FAILED

            bk_cloud_id = instance_obj["instance_info"]["host"]["bk_cloud_id"]
            if isinstance(bk_cloud_id, list):
                bk_cloud_id = bk_cloud_id[0]["bk_inst_id"]

            status_obj = {
                "status": status,
                "status_name": status_name,
                "host_id": bk_host_id,
                "ip": instance_obj["instance_info"]["host"]["bk_host_innerip"],
                "ipv6": instance_obj["instance_info"]["host"].get("bk_host_innerip_v6", ""),
                "cloud_id": bk_cloud_id,
                "host_name": instance_obj["instance_info"]["host"]["bk_host_name"],
                "instance_id": instance_obj["instance_id"],
                "instance_name": instance_obj["instance_info"]["host"]["bk_host_innerip"],
                "plugin_name": plugin_statuses.get("name"),
                "plugin_version": plugin_statuses.get("version"),
                "bk_supplier_id": instance_obj["instance_info"]["host"].get("bk_supplier_account"),
                "create_time": instance_obj["create_time"],
            }
            instance_list.append(status_obj)

        return instance_list

    def get_subscription_status(self):
        """
        查看订阅的插件运行状态
        :return:
        """
        if not self.data.subscription_id and not self.data.target_nodes:
            return {
                "contents": [
                    {
                        "is_label": False,
                        "label_name": "",
                        "bk_obj_name": _("主机"),
                        "node_path": _("主机"),
                        "bk_obj_id": "host",
                        "bk_inst_id": "",
                        "bk_inst_name": "",
                        "child": [],
                    }
                ]
            }
        instance_data = NodeApi.get_subscription_task_status.bulk_request(
            params={
                "subscription_id": self.data.subscription_id,
                "need_detail": False,
                "need_aggregate_all_tasks": True,
                "need_out_of_scope_snapshots": False,
                "bk_biz_id": self.data.bk_biz_id,
            },
            get_data=lambda x: x["list"],
            get_count=lambda x: x["total"],
        )

        bk_host_ids = []
        for item in instance_data:
            bk_host_ids.append(item["instance_info"]["host"]["bk_host_id"])

        plugin_data = NodeApi.plugin_search.batch_request(
            params={"conditions": [], "page": 1, "pagesize": settings.BULK_REQUEST_LIMIT},
            chunk_values=bk_host_ids,
            chunk_key="bk_host_id",
            bk_tenant_id=Space.get_tenant_id(bk_biz_id=self.data.bk_biz_id),
        )

        instance_status = self.format_subscription_instance_status(instance_data, plugin_data)
        return {"contents": self._get_status_content(instance_status, is_task=False)}

    @staticmethod
    def search_object_attribute():
        return_data = defaultdict(list)
        response = CCApi.search_object_attribute({"bk_obj_id": "host"})
        for data in response:
            if data["bk_obj_id"] == "host" and data["bk_property_id"] in CC_HOST_FIELDS:
                host_data = {
                    "field": data["bk_property_id"],
                    "name": data["bk_property_name"],
                    "group_name": data["bk_property_group_name"],
                }
                return_data["host"].append(host_data)
        return_data["host"].extend(
            [
                {"field": "bk_supplier_account", "name": "供应商", "group_name": "基础信息"},
                {"field": "bk_host_id", "name": "主机ID", "group_name": "基础信息"},
                {"field": "bk_biz_id", "name": "业务ID", "group_name": "基础信息"},
            ]
        )
        scope_data = [
            {"field": "bk_module_id", "name": "模块ID", "group_name": "基础信息"},
            {"field": "bk_set_id", "name": "集群ID", "group_name": "基础信息"},
            {"field": "bk_module_name", "name": "模块名称", "group_name": "基础信息"},
            {"field": "bk_set_name", "name": "集群名称", "group_name": "基础信息"},
        ]
        return_data["scope"] = scope_data
        return return_data

    def _update_or_create_subscription(self, collector_scenario, params: dict, is_create=False):
        try:
            self.data.subscription_id = collector_scenario.update_or_create_subscription(self.data, params)
            self.data.save()
            if params.get("run_task", True):
                self._run_subscription_task()
            # start nodeman subscription
            NodeApi.switch_subscription(
                {"subscription_id": self.data.subscription_id, "action": "enable", "bk_biz_id": self.data.bk_biz_id}
            )
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(f"create or update collector config failed => [{error}]")
            if not is_create:
                raise CollectorCreateOrUpdateSubscriptionException(
                    CollectorCreateOrUpdateSubscriptionException.MESSAGE.format(err=error)
                )

    def fast_create(self, params: dict) -> dict:
        params["params"]["encoding"] = params["data_encoding"]
        # 如果没传入集群ID, 则随机给一个公共集群
        if not params.get("storage_cluster_id"):
            storage_cluster_id = self.get_random_public_cluster_id(bk_biz_id=params["bk_biz_id"])
            if not storage_cluster_id:
                raise PublicESClusterNotExistException()
            params["storage_cluster_id"] = storage_cluster_id
        # 如果没传入数据链路ID, 则按照优先级选取一个集群ID
        data_link_id = int(params.get("data_link_id") or 0)
        params["data_link_id"] = self.get_data_link_id(bk_biz_id=params["bk_biz_id"], data_link_id=data_link_id)
        self.only_create_or_update_model(params)
        self.create_or_update_subscription(params)

        params["table_id"] = params["collector_config_name_en"]
        index_set_id = self.create_or_update_clean_config(False, params).get("index_set_id", 0)
        self._send_create_notify(self.data)
        return {
            "collector_config_id": self.data.collector_config_id,
            "bk_data_id": self.data.bk_data_id,
            "subscription_id": self.data.subscription_id,
            "task_id_list": self.data.task_id_list,
            "index_set_id": index_set_id,
        }

    def fast_update(self, params: dict) -> dict:
        if self.data and not self.data.is_active:
            raise CollectorActiveException()
        bkdata_biz_id = self.data.bkdata_biz_id if self.data.bkdata_biz_id else self.data.bk_biz_id
        bk_data_name = self.build_bk_data_name(
            bk_biz_id=bkdata_biz_id, collector_config_name_en=self.data.collector_config_name_en
        )
        self._cat_illegal_ips(params)

        collector_config_fields = [
            "collector_config_name",
            "description",
            "target_object_type",
            "target_node_type",
            "target_nodes",
            "params",
            "extra_labels",
        ]
        model_fields = {i: params[i] for i in collector_config_fields if params.get(i)}

        with transaction.atomic():
            try:
                _collector_config_name = self.data.collector_config_name
                if self.data.bk_data_id and self.data.bk_data_name != bk_data_name:
                    TransferApi.modify_data_id({"data_id": self.data.bk_data_id, "data_name": bk_data_name})
                    logger.info(
                        f"[modify_data_name] bk_data_id=>{self.data.bk_data_id}, data_name {self.data.bk_data_name}=>{bk_data_name}"
                    )
                    self.data.bk_data_name = bk_data_name

                for key, value in model_fields.items():
                    setattr(self.data, key, value)
                self.data.save()

                # collector_config_name更改后更新索引集名称
                if _collector_config_name != self.data.collector_config_name and self.data.index_set_id:
                    index_set_name = _("[采集项]") + self.data.collector_config_name
                    LogIndexSet.objects.filter(index_set_id=self.data.index_set_id).update(
                        index_set_name=index_set_name
                    )

                # 更新数据源
                if params.get("is_allow_alone_data_id", True):
                    if self.data.etl_processor == ETLProcessorChoices.BKBASE.value:
                        transfer_data_id = self.update_or_create_data_id(
                            self.data, etl_processor=ETLProcessorChoices.TRANSFER.value
                        )
                        self.data.bk_data_id = self.update_or_create_data_id(self.data, bk_data_id=transfer_data_id)
                    else:
                        self.data.bk_data_id = self.update_or_create_data_id(self.data)
                    self.data.save()

            except Exception as e:
                logger.warning(f"modify collector config name failed, err: {e}")
                raise ModifyCollectorConfigException(ModifyCollectorConfigException.MESSAGE.format(e))

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

        try:
            if params.get("params"):
                params["params"]["encoding"] = params["data_encoding"]
                collector_scenario = CollectorScenario.get_instance(self.data.collector_scenario_id)
                self._update_or_create_subscription(
                    collector_scenario=collector_scenario, params=params["params"], is_create=False
                )
        finally:
            if (
                params.get("is_allow_alone_data_id", True)
                and params.get("etl_processor") != ETLProcessorChoices.BKBASE.value
            ):
                # 创建数据平台data_id
                async_create_bkdata_data_id.delay(self.data.collector_config_id)

        params["table_id"] = self.data.collector_config_name_en
        self.create_or_update_clean_config(True, params)

        return {"collector_config_id": self.data.collector_config_id}

    def _run_subscription_task(self, action=None, scope: dict[str, Any] = None):
        """
        触发订阅事件
        :param: action 动作 [START, STOP, INSTALL, UNINSTALL]
        :param: nodes 需要重试的实例
        :return: task_id 任务ID
        """
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=self.data.collector_scenario_id)
        params = {"subscription_id": self.data.subscription_id, "bk_biz_id": self.data.bk_biz_id}
        if action:
            params.update({"actions": {collector_scenario.PLUGIN_NAME: action}})

        # 无scope.nodes时，节点管理默认对全部已配置的scope.nodes进行操作
        # 有scope.nodes时，对指定scope.nodes进行操作
        if scope:
            params["scope"] = scope
            params["scope"]["bk_biz_id"] = self.data.bk_biz_id

        task_id = NodeApi.run_subscription_task(params).get("task_id")
        if scope is None and task_id:
            self.data.task_id_list = [str(task_id)]
        self.data.save()
        return self.data.task_id_list

    def create_or_update_subscription(self, params):
        """STEP2: 创建|修改订阅"""
        is_create = True if self.data else False
        try:
            collector_scenario = CollectorScenario.get_instance(self.data.collector_scenario_id)
            self._update_or_create_subscription(
                collector_scenario=collector_scenario, params=params["params"], is_create=is_create
            )
        finally:
            if (
                params.get("is_allow_alone_data_id", True)
                and params.get("etl_processor") != ETLProcessorChoices.BKBASE.value
            ):
                # 创建数据平台data_id
                async_create_bkdata_data_id.delay(self.data.collector_config_id)

    @classmethod
    def get_subscription_dispose(cls, collector_obj, return_data, subscription_collector_map, subscription_id_list):
        # 若订阅ID未写入
        if not collector_obj.subscription_id:
            return_data.append(
                {
                    "collector_id": collector_obj.collector_config_id,
                    "subscription_id": None,
                    "status": CollectStatus.PREPARE if collector_obj.target_nodes else CollectStatus.SUCCESS,
                    "status_name": RunStatus.PREPARE if collector_obj.target_nodes else RunStatus.SUCCESS,
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "pending": 0,
                }
            )
            return return_data, subscription_id_list, subscription_collector_map

        # 订阅ID和采集配置ID的映射关系 & 需要查询订阅ID列表
        subscription_collector_map[collector_obj.subscription_id] = collector_obj.collector_config_id
        subscription_id_list.append(collector_obj.subscription_id)
        return return_data, subscription_id_list, subscription_collector_map

    def list_collectors_by_host(self, params):
        bk_biz_id = params.get("bk_biz_id")
        node_result = []
        try:
            node_result = NodeApi.query_host_subscriptions({**params, "source_type": "subscription"})
        except ApiRequestError as error:
            if NOT_FOUND_CODE in error.message:
                node_result = []

        subscription_ids = [ip_subscription["source_id"] for ip_subscription in node_result]
        collectors = CollectorConfig.objects.filter(
            subscription_id__in=subscription_ids,
            bk_biz_id=bk_biz_id,
            is_active=True,
            table_id__isnull=False,
            index_set_id__isnull=False,
        )

        collectors = [model_to_dict(c) for c in collectors]
        collectors = self.add_cluster_info(collectors)

        index_sets = {
            index_set.index_set_id: index_set
            for index_set in LogIndexSet.objects.filter(
                index_set_id__in=[collector["index_set_id"] for collector in collectors]
            )
        }

        collect_status = {
            status["collector_id"]: status
            for status in self.get_subscription_status_by_list(
                [collector["collector_config_id"] for collector in collectors]
            )
        }

        return [
            {
                "collector_config_id": collector["collector_config_id"],
                "collector_config_name": collector["collector_config_name"],
                "collector_scenario_id": collector["collector_scenario_id"],
                "index_set_id": collector["index_set_id"],
                "index_set_name": index_sets[collector["index_set_id"]].index_set_name,
                "index_set_scenario_id": index_sets[collector["index_set_id"]].scenario_id,
                "retention": collector["retention"],
                "status": collect_status.get(collector["collector_config_id"], {}).get("status", CollectStatus.UNKNOWN),
                "status_name": collect_status.get(collector["collector_config_id"], {}).get(
                    "status_name", RunStatus.UNKNOWN
                ),
                "description": collector["description"],
            }
            for collector in collectors
            if collector["index_set_id"] in index_sets
        ]
