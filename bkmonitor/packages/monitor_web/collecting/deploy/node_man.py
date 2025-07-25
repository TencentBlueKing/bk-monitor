"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import itertools
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _

from api.cmdb.define import TopoNode, TopoTree
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api, resource
from core.errors.api import BKAPIError
from core.errors.collecting import (
    CollectConfigNeedUpgrade,
    CollectConfigRollbackError,
    DeleteCollectConfigError,
    SubscriptionStatusError,
)
from monitor_web.collecting.constant import (
    CollectStatus,
    OperationResult,
    OperationType,
    TaskStatus,
)
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.plugin.constant import ParamMode, PluginType
from monitor_web.plugin.manager import PluginManagerFactory

from .base import BaseInstaller


class NodeManInstaller(BaseInstaller):
    """
    节点管理安装器
    """

    running_status = {OperationType.START: TaskStatus.STARTING, OperationType.STOP: TaskStatus.STOPPING}

    def __init__(self, collect_config: CollectConfigMeta, topo_tree: TopoTree = None):
        super().__init__(collect_config)
        self._topo_tree = topo_tree
        self._topo_links = None

    def _get_topo_links(self) -> dict[str, list[TopoNode]]:
        """
        获取拓扑链路
        """
        if self._topo_links:
            return self._topo_links

        if not self._topo_tree:
            self._topo_tree = api.cmdb.get_topo_tree(bk_biz_id=self.collect_config.bk_biz_id)

        topo_links = self._topo_tree.convert_to_topo_link()

        # 补充节点信息
        self._topo_links = {}
        for link in topo_links.values():
            for index, node in enumerate(link[:-1]):
                node_id = f"{node.bk_obj_id}|{node.bk_inst_id}"
                if node_id not in self._topo_links:
                    self._topo_links[node_id] = link[index:]

        return self._topo_links

    def _create_plugin_collecting_steps(self, target_version: DeploymentConfigVersion, data_id: str):
        """
        创建插件采集步骤配置
        """
        plugin_manager = PluginManagerFactory.get_manager(plugin=self.plugin)
        config_params = copy.deepcopy(target_version.params)

        # 获取维度注入参数
        config_json = target_version.plugin_version.config.config_json
        dms_insert_params = {}
        for param in config_json:
            if param["mode"] == ParamMode.DMS_INSERT:
                param_value = config_params["plugin"].get(param["name"])
                for dms_key, dms_value in list(param_value.items()):
                    if param["type"] == "host":
                        dms_insert_params[dms_key] = "{{ " + f"cmdb_instance.host.{dms_value} or '-'" + " }}"
                    elif param["type"] == "service":
                        dms_insert_params[dms_key] = (
                            "{{ " + f"cmdb_instance.service.labels['{dms_value}'] or '-'" + " }}"
                        )
                    elif param["type"] == "custom":
                        # 自定义维度k， v 注入
                        dms_insert_params[dms_key] = dms_value

        if self.plugin.plugin_type == PluginType.PROCESS:
            # processbeat 配置
            # processbeat 采集不需要dataid
            config_params["collector"].update(
                {
                    "taskid": str(self.collect_config.id),
                    "namespace": self.plugin.plugin_id,
                    # 采集周期带上单位 `s`
                    "period": f"{config_params['collector']['period']}s",
                    # 采集超时时间
                    "timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "max_timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "dataid": str(plugin_manager.perf_data_id),
                    "port_dataid": str(plugin_manager.port_data_id),
                    "match_pattern": config_params["process"]["match_pattern"],
                    "process_name": config_params["process"].get("process_name", ""),
                    "exclude_pattern": config_params["process"]["exclude_pattern"],
                    "port_detect": config_params["process"]["port_detect"],
                    # 维度注入能力
                    "extract_pattern": config_params["process"].get("extract_pattern", ""),
                    "pid_path": config_params["process"]["pid_path"],
                    "labels": {
                        "$for": "cmdb_instance.scope",
                        "$item": "scope",
                        "$body": {
                            "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                            "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                            "bk_target_cloud_id": (
                                "{{ cmdb_instance.host.bk_cloud_id[0].id "
                                "if cmdb_instance.host.bk_cloud_id is iterable and "
                                "cmdb_instance.host.bk_cloud_id is not string "
                                "else cmdb_instance.host.bk_cloud_id }}"
                            ),
                            "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                            "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                            "bk_target_service_category_id": (
                                "{{ cmdb_instance.service.service_category_id | default('', true) }}"
                            ),
                            "bk_collect_config_id": self.collect_config.id,
                            "bk_biz_id": str(self.collect_config.bk_biz_id),
                        },
                    },
                    "tags": config_params["collector"].get("tag", {}),
                }
            )
        else:
            # bkmonitorbeat通用配置参数
            config_params["collector"].update(
                {
                    "task_id": str(self.collect_config.id),
                    "bk_biz_id": str(self.collect_config.bk_biz_id),
                    "config_name": self.plugin.plugin_id,
                    "config_version": "1.0",
                    "namespace": self.plugin.plugin_id,
                    "period": str(config_params["collector"]["period"]),
                    # 采集超时时间
                    "timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "max_timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "dataid": str(data_id),
                    "labels": {
                        "$for": "cmdb_instance.scope",
                        "$item": "scope",
                        "$body": {
                            "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                            "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                            "bk_target_cloud_id": (
                                "{{ cmdb_instance.host.bk_cloud_id[0].id "
                                "if cmdb_instance.host.bk_cloud_id is iterable and "
                                "cmdb_instance.host.bk_cloud_id is not string "
                                "else cmdb_instance.host.bk_cloud_id }}"
                            ),
                            "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                            "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                            "bk_target_service_category_id": (
                                "{{ cmdb_instance.service.service_category_id | default('', true) }}"
                            ),
                            "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                            "bk_collect_config_id": self.collect_config.id,
                            # 维度注入模板变量
                            **dms_insert_params,
                        },
                    },
                }
            )
        config_params["subscription_id"] = target_version.subscription_id
        return plugin_manager.get_deploy_steps_params(
            target_version.plugin_version, config_params, target_version.target_nodes
        )

    def _get_deploy_params(self, target_version: DeploymentConfigVersion):
        """
        获取订阅任务参数
        """
        data_id = self.collect_config.data_id

        subscription_params = {
            "scope": {
                "bk_biz_id": self.collect_config.bk_biz_id,
                "object_type": self.collect_config.target_object_type,
                "node_type": target_version.target_node_type,
                "nodes": [target_version.remote_collecting_host]
                if self.plugin.plugin_type == PluginType.SNMP
                else target_version.target_nodes,
            },
            "steps": self._create_plugin_collecting_steps(target_version, data_id),
            "run_immediately": True,
        }

        # 在组装节点管理创建订阅时，target_hosts被定义为远程下发采集配置文件与执行采集任务的主机
        if target_version.remote_collecting_host:
            if self.plugin.plugin_type == PluginType.SNMP:
                return subscription_params
            subscription_params["target_hosts"] = [target_version.remote_collecting_host]

        return subscription_params

    def _deploy(self, target_version: DeploymentConfigVersion) -> dict:
        """
        部署插件采集
        """
        if self.collect_config.deployment_config_id and self.collect_config.deployment_config_id != target_version.pk:
            last_version: DeploymentConfigVersion = self.collect_config.deployment_config
        else:
            last_version = None

        # 判断是否需要重建订阅任务
        if last_version and last_version.subscription_id:
            diff_result = last_version.show_diff(target_version)
            operate_type = self.collect_config.operate_type(diff_result)
        else:
            operate_type = "create"
            diff_result = {
                "nodes": {
                    "is_modified": True,
                    "added": target_version.target_nodes,
                    "removed": [],
                    "unchanged": [],
                    "updated": [],
                }
            }

        subscription_params = self._get_deploy_params(target_version)
        if not operate_type:
            subscription_id = last_version.subscription_id
            task_id = None
        elif operate_type == "create":
            # 新建订阅任务
            result = api.node_man.create_subscription(**subscription_params)
            subscription_id = result["subscription_id"]
            task_id = result["task_id"]
        elif operate_type == "update":
            # 更新上一次订阅任务
            update_params = {
                "subscription_id": last_version.subscription_id,
                "scope": {
                    "bk_biz_id": self.collect_config.bk_biz_id,
                    "node_type": subscription_params["scope"]["node_type"],
                    "nodes": subscription_params["scope"]["nodes"],
                },
                "steps": subscription_params.get("steps", []),
                "run_immediately": True,
            }
            result = api.node_man.update_subscription(**update_params)
            subscription_id = last_version.subscription_id
            task_id = result.get("task_id", None)
        else:
            # 新建订阅任务
            result = api.node_man.create_subscription(**subscription_params)
            subscription_id = result["subscription_id"]
            task_id = result["task_id"]

            # 卸载上一次订阅任务
            api.node_man.switch_subscription(subscription_id=last_version.subscription_id, action="disable")
            api.node_man.run_subscription(
                subscription_id=last_version.subscription_id,
                actions={step["id"]: "UNINSTALL" for step in subscription_params["steps"]},
            )
            api.node_man.delete_subscription(subscription_id=last_version.subscription_id)

        # 启动自动巡检
        if settings.IS_SUBSCRIPTION_ENABLED:
            api.node_man.switch_subscription(subscription_id=subscription_id, action="enable")
        else:
            api.node_man.switch_subscription(subscription_id=subscription_id, action="disable")

        # 更新部署记录及采集配置
        target_version.subscription_id = subscription_id
        if task_id:
            target_version.task_ids = [task_id]
        target_version.save()

        return diff_result["nodes"]

    def _release_package(self, release_version):
        """
        发布插件包
        """
        if release_version.is_packaged:
            return

        plugin_manager = PluginManagerFactory.get_manager(plugin=self.plugin)
        with transaction.atomic():
            register_info = {
                "plugin_id": self.plugin.plugin_id,
                "config_version": release_version.config_version,
                "info_version": release_version.info_version,
            }
            ret = resource.plugin.plugin_register(**register_info)
            plugin_manager.release(
                config_version=release_version.config_version,
                info_version=release_version.info_version,
                token=ret["token"],
                debug=False,
            )

    def install(self, install_config: dict, operation: str | None) -> dict:
        """
        首次安装插件采集
        install_config: {
            "target_node_type": "INSTANCE",
            "target_nodes": [],
            "params": {
                "collector": {"period": 60, "timeout": 60, "metric_relabel_configs": []},
                "plugin": {},
                "target_node_type": "INSTANCE",
                "target_object_type": "HOST"
            },
            "remote_collecting_host": {},
            "name": "",
            "label": ""
        }
        """
        # 判断该采集是否需要升级，如果需要升级则抛出异常
        if self.collect_config.pk and self.collect_config.need_upgrade:
            raise CollectConfigNeedUpgrade({"msg": self.collect_config.name})

        release_version = self.plugin.packaged_release_version
        self._release_package(release_version)

        # 创建新的部署记录
        deployment_config_params = {
            "plugin_version": release_version,
            "target_node_type": install_config["target_node_type"],
            "target_nodes": install_config["target_nodes"],
            "params": install_config["params"],
            "remote_collecting_host": install_config.get("remote_collecting_host"),
            "config_meta_id": self.collect_config.pk or 0,
            "parent_id": self.collect_config.deployment_config_id or 0,
            "task_ids": [],
        }
        new_version = DeploymentConfigVersion.objects.create(**deployment_config_params)

        # 如果是新建的采集配置，需要先保存以生成采集配置ID
        if not self.collect_config.pk:
            self.collect_config.deployment_config = new_version
            self.collect_config.save()

        # 部署插件采集
        diff_node = self._deploy(new_version)

        # 更新采集配置
        self.collect_config.operation_result = OperationResult.PREPARING

        # 如果有指定操作类型，则更新为指定操作类型
        if operation:
            self.collect_config.last_operation = operation
        else:
            self.collect_config.last_operation = OperationType.EDIT if self.collect_config.pk else OperationType.CREATE
        self.collect_config.deployment_config = new_version
        self.collect_config.save()

        # 如果是首次创建，更新部署配置关联的采集配置ID
        if not new_version.config_meta_id:
            new_version.config_meta_id = self.collect_config.pk
            new_version.save()

        return {
            "diff_node": diff_node,
            "can_rollback": self.collect_config.last_operation != OperationType.CREATE,
            "id": self.collect_config.pk,
            "deployment_id": new_version.pk,
        }

    def upgrade(self, params: dict) -> dict:
        """
        升级插件采集
        """
        # 判断是否需要升级
        if not self.collect_config.need_upgrade:
            raise CollectConfigNeedUpgrade({"msg": _("采集配置无需升级")})

        current_version = self.collect_config.deployment_config

        # 创建新的部署记录
        params["collector"]["period"] = current_version.params["collector"]["period"]
        params["collector"]["timeout"] = current_version.params["collector"].get("timeout", 60)

        release_version = self.plugin.packaged_release_version
        self._release_package(release_version)

        deployment_config_params = {
            "plugin_version": release_version,
            "target_node_type": current_version.target_node_type,
            "target_nodes": current_version.target_nodes,
            "params": params,
            "remote_collecting_host": current_version.remote_collecting_host,
            "config_meta_id": self.collect_config.pk,
            "parent_id": current_version.pk,
        }
        new_version = DeploymentConfigVersion.objects.create(**deployment_config_params)

        # 部署插件采集
        self._deploy(new_version)

        # 更新采集配置
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.UPGRADE
        self.collect_config.deployment_config = new_version
        self.collect_config.save()

        return {
            "id": self.collect_config.pk,
            "deployment_id": new_version.pk,
        }

    def uninstall(self):
        """
        卸载插件采集
        1. 判断是否已经停用
        2. 删除节点管理订阅任务
        """
        # 判断是否已经停用
        if self.collect_config.last_operation != OperationType.STOP:
            raise DeleteCollectConfigError({"msg": _("采集配置未停用")})

        subscription_id = self.collect_config.deployment_config.subscription_id

        # 卸载并删除节点管理订阅任务
        if subscription_id:
            api.node_man.switch_subscription(subscription_id=subscription_id, action="disable")
            subscription_params = self._get_deploy_params(self.collect_config.deployment_config)
            api.node_man.run_subscription(
                subscription_id=subscription_id,
                actions={step["id"]: "UNINSTALL" for step in subscription_params["steps"]},
            )
            api.node_man.delete_subscription(subscription_id=subscription_id)

        # 删除部署记录及采集配置
        DeploymentConfigVersion.objects.filter(config_meta_id=self.collect_config.id).delete()
        self.collect_config.delete()

    def rollback(self, target_version: int | DeploymentConfigVersion | None = None):
        """
        回滚插件采集
        """
        # 获取目标版本
        if not target_version:
            target_version = self.collect_config.deployment_config.last_version
        elif isinstance(target_version, int):
            target_version = DeploymentConfigVersion.objects.filter(pk=target_version).first()

        # 判断目标版本是否存在
        if not target_version:
            raise CollectConfigRollbackError({"msg": _("目标版本不存在")})

        # 回滚部署
        diff_node = self._deploy(target_version)

        # 更新采集配置
        self.collect_config.deployment_config = target_version
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.ROLLBACK
        self.collect_config.save()

        return {
            "diff_node": diff_node,
            "id": self.collect_config.pk,
            "deployment_id": target_version.pk,
        }

    def stop(self):
        """
        停止插件采集
        1. 关闭订阅任务巡检
        2. 执行停止操作
        """
        subscription_id = self.collect_config.deployment_config.subscription_id

        # 如果没有订阅任务ID，则直接返回
        if not subscription_id:
            self.collect_config.operation_result = OperationResult.SUCCESS
            self.collect_config.last_operation = OperationType.STOP
            self.collect_config.save()
            return

        # 关闭订阅任务巡检
        api.node_man.switch_subscription(subscription_id=subscription_id, action="disable")

        # 停用采集配置
        subscription_params = self._get_deploy_params(self.collect_config.deployment_config)
        result = api.node_man.run_subscription(
            subscription_id=subscription_id,
            actions={step["id"]: "STOP" for step in subscription_params["steps"]},
        )

        # 更新采集配置及部署记录
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.STOP
        self.collect_config.save()

        self.collect_config.deployment_config.task_ids = (
            [result["task_id"]] if result.get("task_id", None) is not None else []
        )
        self.collect_config.deployment_config.save()

    def start(self):
        """
        启动插件采集
        1. 启动订阅任务巡检
        2. 执行启动操作
        """
        subscription_id = self.collect_config.deployment_config.subscription_id

        # 如果没有订阅任务ID，则直接返回
        if not subscription_id:
            self.collect_config.operation_result = OperationResult.SUCCESS
            self.collect_config.last_operation = OperationType.START
            self.collect_config.save()
            return

        # 启用订阅任务巡检
        if settings.IS_SUBSCRIPTION_ENABLED:
            api.node_man.switch_subscription(subscription_id=subscription_id, action="enable")

        # 启动采集配置
        subscription_params = self._get_deploy_params(self.collect_config.deployment_config)
        result = api.node_man.run_subscription(
            subscription_id=subscription_id,
            actions={step["id"]: "START" for step in subscription_params["steps"]},
        )

        # 更新采集配置及部署记录
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.START
        self.collect_config.save()

        self.collect_config.deployment_config.task_ids = (
            [result["task_id"]] if result.get("task_id", None) is not None else []
        )
        self.collect_config.deployment_config.save()

    def run(self, action: str = None, scope: dict[str, Any] = None):
        """
        执行插件采集
        :param ACTION: 操作类型 INSTALL/UNINSTALL/START/STOP
        """
        subscription_id = self.collect_config.deployment_config.subscription_id

        # 如果没有订阅任务ID，则直接返回
        if not subscription_id:
            return

        # 如果没有指定操作类型，则默认为安装
        if not action:
            action = "INSTALL"
        else:
            action = action.upper()

        # 执行采集配置
        subscription_params = self._get_deploy_params(self.collect_config.deployment_config)
        params = {
            "subscription_id": subscription_id,
            "actions": {step["id"]: action for step in subscription_params["steps"]},
        }

        # 如果有指定范围，则只执行指定范围
        if scope:
            params["scope"] = scope.copy()
            params["scope"]["bk_biz_id"] = self.collect_config.bk_biz_id

        api.node_man.run_subscription(**params)

    def retry(self, instance_ids: list[int] = None):
        """
        重试插件采集，如果没有指定实例，则啊重试失败的实例
        """
        current_version = self.collect_config.deployment_config

        if not current_version.subscription_id:
            return

        params = {"subscription_id": current_version.subscription_id}
        if instance_ids is not None:
            # 如果指定了实例ID，则只重试指定的实例
            params["instance_id_list"] = instance_ids
        elif current_version.task_ids:
            # 如果没有指定实例ID，则重试所有失败实例
            result = api.node_man.batch_task_result(
                subscription_id=current_version.subscription_id,
                task_id_list=current_version.task_ids,
            )

            # 所有失败的实例
            failed_instances_ids = {
                item["instance_id"]
                for item in result
                if item["status"] in [CollectStatus.FAILED, CollectStatus.PENDING]
            }
            if not failed_instances_ids:
                # 如果没有失败的实例，则直接返回
                return
            elif len(failed_instances_ids) != len(result):
                # 如果不是所有实例都失败，则只重试失败的实例
                params["instance_id_list"] = failed_instances_ids

        # 重试订阅任务
        result = api.node_man.retry_subscription(**params)

        # 更新采集配置及部署记录
        self.collect_config.deployment_config.task_ids.append(result["task_id"])
        self.collect_config.deployment_config.save()
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.save()

    def revoke(self, instance_ids: list[int] = None):
        """
        终止采集任务
        """
        subscription_id = self.collect_config.deployment_config.subscription_id

        # 如果没有指定实例ID，则终止所有实例
        params = {"subscription_id": subscription_id}
        if instance_ids is not None:
            params["instance_id_list"] = instance_ids

        # 终止订阅任务
        api.node_man.revoke_subscription(**params)

    @staticmethod
    def _get_instance_step_log(instance_result: dict[str, Any]):
        """
        获取实例下发阶段性日志
        """
        for step in instance_result.get("steps", []):
            if step["status"] != CollectStatus.SUCCESS:
                for sub_step in step["target_hosts"][0]["sub_steps"]:
                    if sub_step["status"] != CollectStatus.SUCCESS:
                        return "{}-{}".format(step["node_name"], sub_step["node_name"])
        return ""

    def _process_nodeman_task_result(self, task_result: list[dict[str, Any]]):
        """
        处理节点管理任务结果
        {
          "task_id":1,
          "record_id":1,
          "instance_id":"service|instance|service|1",
          "create_time":"2024-09-06 12:07:33",
          "pipeline_id":"xxxxxxxxxxxx",
          "instance_info":{
            "host":{
              "bk_biz_id":2,
              "bk_host_id":1,
              "bk_biz_name":"蓝鲸",
              "bk_cloud_id":0,
              "bk_host_name":"VM_0_0_centos",
              "bk_cloud_name":"云区域",
              "bk_host_innerip":"127.0.0.1",
              "bk_supplier_account":"0"
            },
            "service":{
              "id":4324,
              "name":"127.0.0.1_mysql_3306",
              "bk_host_id":1,
              "bk_module_id":1
            }
          },
          "start_time":"2024-09-06 12:07:35",
          "finish_time":"2024-09-06 12:07:54",
          "status":"SUCCESS"
        }

        {
          "task_id":1,
          "record_id":1,
          "instance_id":"host|instance|host|1",
          "create_time":"2024-09-06 12:40:17",
          "pipeline_id":"xxxxxxxxxxxx",
          "instance_info":{
            "host":{
              "bk_biz_id":2,
              "bk_host_id":1,
              "bk_biz_name":"蓝鲸",
              "bk_cloud_id":0,
              "bk_host_name":"VM_0_0_centos",
              "bk_cloud_name":"云区域",
              "bk_host_innerip":"127.0.0.1",
              "bk_host_innerip_v6":"",
              "bk_supplier_account":"0"
            },
            "service":{}
          },
          "start_time":"2024-09-06 12:40:19",
          "finish_time":"2024-09-06 12:40:27",
          "status":"SUCCESS"
        }
        """
        instances = []
        for instance_result in task_result:
            host = instance_result["instance_info"]["host"]
            service_info = instance_result["instance_info"].get("service") or {}
            instance = {
                "instance_id": instance_result["instance_id"],
                "ip": host["bk_host_innerip"],
                "bk_cloud_id": host["bk_cloud_id"],
                "bk_host_id": host["bk_host_id"],
                "bk_host_name": host["bk_host_name"],
                "bk_supplier_id": host.get("bk_supplier_account", "0"),
                "task_id": instance_result["task_id"],
                "status": instance_result["status"],
                "plugin_version": self.collect_config.deployment_config.plugin_version.version,
                "log": self._get_instance_step_log(instance_result),
                "action": "",
                "steps": {step["id"]: step["action"] for step in instance_result.get("steps", []) if step["action"]},
                "scope_ids": [],
            }

            # 状态转换
            if instance["status"] in [TaskStatus.DEPLOYING, TaskStatus.RUNNING]:
                instance["status"] = self.running_status.get(self.collect_config.last_operation, TaskStatus.RUNNING)

            # 处理scope
            for scope in instance_result["instance_info"].get("scope", []):
                if "bk_obj_id" in scope and "bk_inst_id" in scope:
                    instance["scope_ids"].append(f"{scope['bk_obj_id']}|{scope['bk_inst_id']}")
                elif "ip" in scope:
                    instance["scope_ids"].append(host["bk_host_id"])

            # 处理服务实例与主机差异字段
            if instance["instance_id"].startswith("service|instance"):
                instance.update(
                    {
                        "instance_name": service_info.get("name") or service_info["id"],
                        "service_instance_id": service_info["id"],
                        "bk_module_id": service_info["bk_module_id"],
                    }
                )
            else:
                instance["instance_name"] = host.get("bk_host_innerip") or host.get("bk_host_innerip_v6") or ""
                instance["bk_module_ids"] = host.get("module", [])
                if not instance["bk_module_ids"]:
                    instance["bk_module_ids"] = [
                        r.get("bk_module_id") for r in host.get("relations", []) if r.get("bk_module_id")
                    ]

            # 根据步骤获取操作类型
            action = "install"
            for step in instance_result.get("steps", []):
                if step.get("action") in ["UNINSTALL", "REMOVE_CONFIG"]:
                    action = "uninstall"
                elif step.get("action") in ["INSTALL"]:
                    action = "install"
                elif step.get("action") in ["PUSH_CONFIG"]:
                    action = "update"

            instance["action"] = action
            instances.append(instance)

        return instances

    def status(self, diff=False) -> list[dict[str, Any]]:
        """
        状态查询
        :param diff: 是否显示差异
        """
        # 获取订阅任务状态，并将结果转换为需要的数据结构
        subscription_id = self.collect_config.deployment_config.subscription_id
        if not subscription_id:
            return []
        result = api.node_man.batch_task_result(subscription_id=subscription_id, need_detail=True)
        instance_statuses = self._process_nodeman_task_result(result)

        # 差异比对/不比对数据结构
        current_version: DeploymentConfigVersion = self.collect_config.deployment_config
        last_version: DeploymentConfigVersion | None = current_version.last_version

        # 将模板转换为节点
        template_to_nodes = defaultdict(list)
        current_node_type = current_version.target_node_type
        if (
            current_node_type in [TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE]
            and current_version.target_nodes
        ):
            opt_mapping = {
                TargetNodeType.SERVICE_TEMPLATE: {"field": "service_template_id", "api": api.cmdb.get_module},
                TargetNodeType.SET_TEMPLATE: {"field": "set_template_id", "api": api.cmdb.get_set},
            }

            template_ids = [node["bk_inst_id"] for node in current_version.target_nodes]
            topo_nodes = opt_mapping[current_node_type]["api"](
                bk_biz_id=self.collect_config.bk_biz_id, **{f"{opt_mapping[current_node_type]['field']}s": template_ids}
            )
            for node in topo_nodes:
                template_id = getattr(node, opt_mapping[current_node_type]["field"])
                template_to_nodes[f"{current_node_type}|{template_id}"].append(
                    {"bk_obj_id": node.bk_obj_id, "bk_inst_id": node.bk_inst_id}
                )

        # 老主机配置兼容，将ip/bk_cloud_id转换为bk_host_id，方便后续数据处理
        if (
            current_node_type == TargetNodeType.INSTANCE
            and self.collect_config.target_object_type == TargetObjectType.HOST
        ):
            # 统计旧版主机配置
            ips = []
            for host in current_version.target_nodes:
                if "bk_host_id" in host:
                    continue
                ips.append({"ip": host["ip"], "bk_cloud_id": host.get("bk_cloud_id", 0)})

            # 查询主机信息
            hosts = api.cmdb.get_host_by_ip(bk_biz_id=self.collect_config.bk_biz_id, ips=ips)
            ip_to_host_ids = {f"{host.bk_host_innerip}|{host.bk_cloud_id}": host.bk_host_id for host in hosts}

            # 标记主机ID
            for host in itertools.chain(
                current_version.target_nodes, last_version.target_nodes if last_version else []
            ):
                if "bk_host_id" in host:
                    continue

                ip = host.get("ip", host.get("bk_target_ip"))
                bk_cloud_id = host.get("bk_cloud_id", host.get("bk_target_cloud_id", 0))
                if f"{ip}|{bk_cloud_id}" in ip_to_host_ids:
                    host["bk_host_id"] = ip_to_host_ids[f"{ip}|{bk_cloud_id}"]

            # 过滤主机ID为空的节点
            current_version.target_nodes = [
                {"bk_host_id": host["bk_host_id"]} for host in current_version.target_nodes if "bk_host_id" in host
            ]
            if last_version:
                last_version.target_nodes = [
                    {"bk_host_id": host["bk_host_id"]} for host in last_version.target_nodes if "bk_host_id" in host
                ]

        # 差异比对
        if diff:
            # 如果存在上一个版本，且需要显示差异
            # {
            #     "is_modified": true,
            #     "added": [],
            #     "updated": [],
            #     "removed": [{"bk_host_id": 51985}],
            #     "unchanged": [{"bk_host_id": 96886},{"bk_host_id": 96887}]
            # }
            if last_version:
                node_diff = last_version.show_diff(current_version)["nodes"]
            else:
                node_diff = {"added": current_version.target_nodes}

            # removed目前不会显示出来，如果后续需要显示，还需要处理父节点的数据，通知节点管理也需要查询目标范围外的任务结果
            node_diff.pop("removed", None)
            node_diff.pop("is_modified", None)

            node_diff = {
                new_diff_type: node_diff.get(diff_type, [])
                for diff_type, new_diff_type in [
                    ("added", "ADD"),
                    ("removed", "REMOVE"),
                    ("updated", "UPDATE"),
                    ("unchanged", "RETRY"),
                ]
            }
        else:
            node_diff = {"": current_version.target_nodes}

        nodes = {}
        dynamic_group_ids = []
        for diff_type, diff_nodes in node_diff.items():
            for diff_node in diff_nodes:
                # 动态分组
                if current_node_type == TargetNodeType.DYNAMIC_GROUP:
                    nodes[f"{diff_node['bk_inst_id']}"] = {"diff_type": diff_type, "child": []}
                    dynamic_group_ids.append(diff_node["bk_inst_id"])
                    continue

                # 主机节点
                if "bk_host_id" in diff_node:
                    nodes[diff_node["bk_host_id"]] = {"diff_type": diff_type, "child": []}
                    continue

                # 将服务/集群模板转换为拓扑节点
                if f"{diff_node['bk_obj_id']}|{diff_node['bk_inst_id']}" in template_to_nodes:
                    template_nodes = template_to_nodes[f"{diff_node['bk_obj_id']}|{diff_node['bk_inst_id']}"]
                else:
                    template_nodes = [diff_node]

                for node in template_nodes:
                    nodes[f"{node['bk_obj_id']}|{node['bk_inst_id']}"] = {"diff_type": diff_type, "child": []}

        # 查询动态分组及其组内的主机实例
        dynamic_groups = []
        if current_node_type == TargetNodeType.DYNAMIC_GROUP:
            dynamic_groups = api.cmdb.search_dynamic_group(
                bk_biz_id=self.collect_config.bk_biz_id,
                bk_obj_id="host",
                dynamic_group_ids=dynamic_group_ids,
                with_instance_id=True,
            )

        # 将任务状态与差异比对数据结构合并返回
        for instance in instance_statuses:
            # 给动态分组内的主机实例加上状态信息
            if current_node_type == TargetNodeType.DYNAMIC_GROUP:
                for dynamic_group in dynamic_groups:
                    nodes[dynamic_group["id"]]["dynamic_group_name"] = dynamic_group["name"]
                    nodes[dynamic_group["id"]]["dynamic_group_id"] = dynamic_group["id"]
                    if instance["bk_host_id"] in dynamic_group["instance_ids"]:
                        nodes[dynamic_group["id"]]["child"].append(instance)
                # 清理scope_ids
                instance.pop("scope_ids", None)
                continue

            for scope_id in instance["scope_ids"]:
                scope_ids = set()
                if str(scope_id).startswith("module|"):
                    topo_links = self._get_topo_links()
                    for link in topo_links.get(scope_id, []):
                        scope_ids.add(f"{link.bk_obj_id}|{link.bk_inst_id}")
                else:
                    scope_ids = {scope_id}

                for sid in scope_ids:
                    if sid in nodes:
                        nodes[sid]["child"].append(instance)

            # 清理scope_ids
            instance.pop("scope_ids", None)

        # 补充拓扑节点信息
        if (current_node_type, self.collect_config.target_object_type) == (
            TargetNodeType.INSTANCE,
            TargetObjectType.HOST,
        ):
            # 主机全部归属在主机节点下
            diff_mapping = defaultdict(lambda: {"child": [], "node_path": _("主机")})
            for node_id, node_info in nodes.items():
                diff_mapping[node_info["diff_type"]]["child"].extend(node_info["child"])
            for diff_type, diff_info in diff_mapping.items():
                diff_info.update({"label_name": diff_type, "is_label": bool(diff_type)})
        elif (current_node_type, self.collect_config.target_object_type) == (
            TargetNodeType.DYNAMIC_GROUP,
            TargetObjectType.HOST,
        ):
            diff_mapping = {}
            for node_id, node_info in nodes.items():
                diff_mapping[node_id] = {
                    "child": node_info["child"],
                    "node_path": _("动态分组"),
                    "label_name": node_info["diff_type"],
                    "is_label": bool(node_info["diff_type"]),
                    "dynamic_group_name": node_info.get("dynamic_group_name"),
                    "dynamic_group_id": node_info.get("dynamic_group_id"),
                }
        else:
            # 服务/集群模板归属在对应的服务/集群模板下
            topo_links = self._get_topo_links()
            diff_mapping = {}
            for node_id, node_info in nodes.items():
                node_path = "/".join(link.bk_inst_name for link in reversed(topo_links.get(node_id, [])))
                if not node_path:
                    node_path = f"{_('未知节点')}({node_id})"
                diff_mapping[node_id] = {
                    "child": node_info["child"],
                    "node_path": node_path,
                    "label_name": node_info["diff_type"],
                    "is_label": bool(node_info["diff_type"]),
                }

        return list(diff_mapping.values())

    def instance_status(self, instance_id: str) -> dict[str, Any]:
        """
        获取实例状态详情
        """
        current_version = self.collect_config.deployment_config

        if not current_version.subscription_id or not current_version.task_ids:
            return {"log_detail": _("未找到日志")}

        params = {
            "subscription_id": self.collect_config.deployment_config.subscription_id,
            "instance_id": instance_id,
            "task_id": self.collect_config.deployment_config.task_ids[0],
        }
        result = api.node_man.task_result_detail(**params)
        if result:
            log = []
            for step in result.get("steps", []):
                log.append("{}{}{}\n".format("=" * 20, step["node_name"], "=" * 20))
                for sub_step in step["target_hosts"][0].get("sub_steps", []):
                    log.extend(["{}{}{}".format("-" * 20, sub_step["node_name"], "-" * 20), sub_step["log"]])
                    # 如果ex_data里面有值，则在日志里加上它
                    if sub_step["ex_data"]:
                        log.append(sub_step["ex_data"])
                    if sub_step["status"] != CollectStatus.SUCCESS:
                        return {"log_detail": "\n".join(log)}
            return {"log_detail": "\n".join(log)}
        else:
            return {"log_detail": _("未找到日志")}

    def update_status(self):
        """
        更新采集配置状态
        """
        current_version = self.collect_config.deployment_config

        try:
            status_result = api.node_man.batch_task_result(subscription_id=current_version.subscription_id)
        except BKAPIError as e:
            message = _("采集配置 CollectConfigMeta: {} 查询订阅{}结果出错: {}").format(
                self.collect_config.id, current_version.subscription_id, e
            )
            raise SubscriptionStatusError({"msg": message})
        except IndexError:
            message = _("采集配置 CollectConfigMeta: {} 对应订阅{}不存在").format(
                self.collect_config.id, current_version.subscription_id
            )
            raise SubscriptionStatusError({"msg": message})

        error_count = 0
        total_count = len(status_result)
        instances_status = ""
        for item in status_result:
            instances_status += "{}({});".format(item["instance_id"], item["status"])
            if item["status"] in [CollectStatus.RUNNING, CollectStatus.PENDING]:
                break
            if item["status"] == CollectStatus.FAILED:
                error_count += 1
        else:
            if error_count == 0:
                self.collect_config.operation_result = OperationResult.SUCCESS
            elif error_count == total_count:
                self.collect_config.operation_result = OperationResult.FAILED
            else:
                self.collect_config.operation_result = OperationResult.WARNING
            self.collect_config.save(not_update_user=True)
