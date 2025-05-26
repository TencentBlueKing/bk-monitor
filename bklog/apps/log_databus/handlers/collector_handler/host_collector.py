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

from django.db import transaction
from apps.api import CCApi, NodeApi
from apps.constants import UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.exceptions import ApiRequestError, ApiResultError
from apps.log_databus.tasks.bkdata import async_create_bkdata_data_id
from apps.log_databus.constants import (
    CC_HOST_FIELDS,
    TargetNodeTypeEnum,
    LogPluginInfo,
    CHECK_TASK_READY_NOTE_FOUND_EXCEPTION_CODE,
    CollectStatus,
    BIZ_TOPO_INDEX,
    INTERNAL_TOPO_INDEX,
    SEARCH_BIZ_INST_TOPO_LEVEL,
    BK_SUPPLIER_ACCOUNT,
    RunStatus,
    ETLProcessorChoices,
)
from apps.log_databus.exceptions import SubscriptionInfoNotFoundException, CollectorCreateOrUpdateSubscriptionException

from apps.log_databus.handlers.collector_scenario import CollectorScenario


from apps.log_databus.handlers.collector_handler.base import (
    CollectorHandler,
)

from apps.log_search.handlers.biz import BizHandler


from apps.utils.local import get_request_username
from apps.utils.log import logger


class HostCollectorHandler(CollectorHandler):
    def _pre_start(self):
        # 启动节点管理订阅功能
        if self.data.subscription_id:
            NodeApi.switch_subscription({"subscription_id": self.data.subscription_id, "action": "enable"})

    @transaction.atomic
    def start(self, **kwargs):
        super().start()
        if self.data.subscription_id:
            return self._run_subscription_task()
        return True

    def _pre_stop(self):
        if self.data.subscription_id:
            # 停止节点管理订阅功能
            NodeApi.switch_subscription({"subscription_id": self.data.subscription_id, "action": "disable"})

    @transaction.atomic
    def stop(self, **kwargs):
        super().stop()
        if self.data.subscription_id:
            return self._run_subscription_task("STOP")
        return True

    def _pre_destroy(self):
        if not self.data.subscription_id:
            return
        subscription_params = {"subscription_id": self.data.subscription_id}
        return NodeApi.delete_subscription(subscription_params)

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

    def run(self, action, scope):
        if self.data.subscription_id:
            return self._run_subscription_task(action=action, scope=scope)
        return True

    def get_subscription_task_detail(self, instance_id, task_id=None):
        """
        采集任务实例日志详情
        :param [string] instance_id: 实例ID
        :param [string] task_id: 任务ID
        :return: [dict]
        """
        # 详情接口查询，原始日志
        param = {"subscription_id": self.data.subscription_id, "instance_id": instance_id}
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
        params = {"subscription_id": self.data.subscription_id, "instance_id_list": instance_id_list}

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
        return self.retry_target_nodes(instance_id_list)

    @classmethod
    def _check_task_ready_exception(cls, error: BaseException):
        """
        处理task_ready_exception 返回error
        @param error {BaseException} 返回错误
        """
        task_ready = True
        if isinstance(error, ApiRequestError):
            return task_ready
        if isinstance(error, ApiResultError) and str(error.code) == CHECK_TASK_READY_NOTE_FOUND_EXCEPTION_CODE:
            return task_ready
        logger.error(f"Call NodeApi check_task_ready error: {error}")
        raise error

    def _check_task_ready(self, param: dict):
        """
        查询任务是否下发: 兼容节点管理未发布的情况
        @param param {Dict} NodeApi.check_subscription_task_ready 请求
        """
        try:
            task_ready = NodeApi.check_subscription_task_ready(param)
        # 如果节点管理路由不存在或服务异常等request异常情况
        except BaseException as e:  # pylint: disable=broad-except
            task_ready = self._check_task_ready_exception(e)
        return task_ready

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

    def get_subscription_task_status(self, task_id_list):
        """
        查询物理机采集任务状态
        :param  [list] task_id_list:
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
        # 查询采集任务状态
        param = {
            "subscription_id": self.data.subscription_id,
        }
        if self.data.task_id_list:
            param["task_id_list"] = self.data.task_id_list

        task_ready = self._check_task_ready(param=param)

        # 如果任务未启动，则直接返回结果
        if not task_ready:
            return {"task_ready": task_ready, "contents": []}

        status_result = NodeApi.get_subscription_task_status.bulk_request(
            params={
                "subscription_id": self.data.subscription_id,
                "need_detail": False,
                "need_aggregate_all_tasks": True,
                "need_out_of_scope_snapshots": False,
            },
            get_data=lambda x: x["list"],
            get_count=lambda x: x["total"],
        )
        instance_status = self.format_task_instance_status(status_result)

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
            return {"task_ready": task_ready, "contents": content_data}

        # 如果采集目标是HOST-TOPO
        # 获取target_nodes获取采集目标及差异节点target_subscription_diff合集
        node_collect = self._get_collect_node()
        node_mapping, template_mapping = self._get_mapping(node_collect=node_collect)
        content_data = list()
        target_mapping = self.get_target_mapping()
        total_host_result = self._get_host_result(node_collect)
        for node_obj in node_collect:
            map_key = "{}|{}".format(str(node_obj["bk_obj_id"]), str(node_obj["bk_inst_id"]))
            host_result = total_host_result.get(map_key, [])
            label_name = target_mapping.get(map_key, "")
            node_path, bk_obj_name, bk_inst_name = self._get_node_obj(
                node_obj=node_obj, template_mapping=template_mapping, node_mapping=node_mapping, map_key=map_key
            )

            content_obj = {
                "is_label": False if not label_name else True,
                "label_name": label_name,
                "bk_obj_name": bk_obj_name,
                "node_path": node_path,
                "bk_obj_id": node_obj["bk_obj_id"],
                "bk_inst_id": node_obj["bk_inst_id"],
                "bk_inst_name": bk_inst_name,
                "child": [],
            }

            for instance_obj in instance_status:
                # delete 标签如果订阅任务状态action不为UNINSTALL
                if label_name == "delete" and instance_obj["steps"].get(LogPluginInfo.NAME) != "UNINSTALL":
                    continue
                # 因为instance_obj兼容新版IP选择器的字段名, 所以这里的bk_cloud_id->cloud_id, bk_host_id->host_id
                if (instance_obj["ip"], instance_obj["cloud_id"]) in host_result or instance_obj[
                    "host_id"
                ] in host_result:
                    content_obj["child"].append(instance_obj)
            content_data.append(content_obj)
        return {"task_ready": task_ready, "contents": content_data}

    def get_task_status(self, id_list):
        return self.get_subscription_task_status(task_id_list=id_list)

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

    def _update_or_create_subscription(self, collector_scenario, params: dict, is_create=False):
        try:
            self.data.subscription_id = collector_scenario.update_or_create_subscription(self.data, params)
            self.data.save()
            if params.get("run_task", True):
                self._run_subscription_task()
            # start nodeman subscription
            NodeApi.switch_subscription({"subscription_id": self.data.subscription_id, "action": "enable"})
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(f"create or update collector config failed => [{error}]")
            if not is_create:
                raise CollectorCreateOrUpdateSubscriptionException(
                    CollectorCreateOrUpdateSubscriptionException.MESSAGE.format(err=error)
                )

    def _run_subscription_task(self, action=None, scope: dict[str, Any] = None):
        """
        触发订阅事件
        :param: action 动作 [START, STOP, INSTALL, UNINSTALL]
        :param: nodes 需要重试的实例
        :return: task_id 任务ID
        """
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=self.data.collector_scenario_id)
        params = {"subscription_id": self.data.subscription_id}
        if action:
            params.update({"actions": {collector_scenario.PLUGIN_NAME: action}})

        # 无scope.nodes时，节点管理默认对全部已配置的scope.nodes进行操作
        # 有scope.nodes时，对指定scope.nodes进行操作
        if scope:
            params["scope"] = scope
            params["scope"]["bk_biz_id"] = self.data.bk_biz_id

        task_id = str(NodeApi.run_subscription_task(params)["task_id"])
        if scope is None:
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
