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

import datetime


from collections import defaultdict
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _


from apps.api import CCApi, NodeApi, TransferApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record

from apps.log_databus.constants import (
    CC_HOST_FIELDS,
    ArchiveInstanceType,
    TargetNodeTypeEnum,
    RETRIEVE_CHAIN,
)


from apps.log_databus.exceptions import (
    CollectorConfigNameDuplicateException,
)
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.custom_define import get_custom

from apps.log_databus.handlers.etl_storage import EtlStorage

from apps.log_databus.handlers.collector_handler.base_collector import (
    BaseCollectorHandler,
    build_bk_data_name,
)

from apps.log_databus.models import (
    ArchiveConfig,
)

from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import (
    LogIndexSet,
)
from apps.models import model_to_dict

from apps.utils.function import map_if
from apps.utils.local import get_request_username
from apps.utils.log import logger


class HostCollectorHandler(BaseCollectorHandler):
    # 统一调用
    def add_container_configs(self, collector_config, context):
        """
        add_container_configs
        @param collector_config:
        @param context:
        @return:
        """
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

    # 接口调用 自定义上报-更新自定义采集配置--里面有self.retrieve()必须要放这里
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
        return self.retry_target_nodes(instance_id_list)

    def get_task_status(self, id_list):
        return self.get_subscription_task_status(task_id_list=id_list)

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
        )

        instance_status = self.format_subscription_instance_status(instance_data, plugin_data)

        # 如果采集目标是HOST-INSTANCE
        if self.data.target_node_type == TargetNodeTypeEnum.INSTANCE.value:
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
            return {"contents": content_data}

        # 如果采集目标是HOST-TOPO
        # 从数据库target_nodes获取采集目标，查询业务TOPO，按采集目标节点进行分类
        target_nodes = self.data.target_nodes
        biz_topo = self._get_biz_topo()

        node_mapping = self.get_node_mapping(biz_topo)
        template_mapping = self._get_template_mapping(target_nodes)
        total_host_result = self._get_host_result(node_collect=target_nodes)

        content_data = list()
        for node_obj in target_nodes:
            map_key = "{}|{}".format(str(node_obj["bk_obj_id"]), str(node_obj["bk_inst_id"]))
            host_result = total_host_result.get(map_key, [])
            node_path, bk_obj_name, bk_inst_name = self._get_node_obj(
                node_obj=node_obj, template_mapping=template_mapping, node_mapping=node_mapping, map_key=map_key
            )
            content_obj = {
                "is_label": False,
                "label_name": "",
                "bk_obj_name": bk_obj_name,
                "node_path": node_path,
                "bk_obj_id": node_obj["bk_obj_id"],
                "bk_inst_id": node_obj["bk_inst_id"],
                "bk_inst_name": bk_inst_name,
                "child": [],
            }

            for instance_obj in instance_status:
                # 因为instance_obj兼容新版IP选择器的字段名, 所以这里的bk_cloud_id->cloud_id, bk_host_id->host_id
                if (instance_obj["ip"], instance_obj["cloud_id"]) in host_result or instance_obj[
                    "host_id"
                ] in host_result:
                    content_obj["child"].append(instance_obj)
            content_data.append(content_obj)
        return {"contents": content_data}

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
            # {"field": "bk_module_name", "name": "模块名称", "group_name": "基础信息"},
            # {"field": "bk_set_name", "name": "集群名称", "group_name": "基础信息"},
        ]
        return_data["scope"] = scope_data
        return return_data
