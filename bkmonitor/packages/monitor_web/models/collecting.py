# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json

from django.conf import settings
from django.db import models, transaction
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from bkmonitor.utils.common_utils import logger
from bkmonitor.utils.db.fields import JsonField, SymmetricJsonField
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api, resource
from monitor_web.collecting.constant import (
    OperationResult,
    OperationType,
    Status,
    TaskStatus,
)
from monitor_web.commons.data_access import EventDataAccessor, PluginDataAccessor
from monitor_web.models.base import OperateRecordModelBase
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import ParamMode, PluginType
from monitor_web.plugin.manager import PluginManagerFactory


class CollectConfigMeta(OperateRecordModelBase):
    """
    采集配置基本信息
    """

    STATUS_CHOICES = (
        (Status.STARTING, _lazy("启用中")),
        (Status.STARTED, _lazy("已启用")),
        (Status.STOPPING, _lazy("停用中")),
        (Status.STOPPED, _lazy("已停用")),
        (Status.DEPLOYING, _lazy("执行中")),
    )

    OPERATION_TYPE_CHOICES = (
        (OperationType.UPGRADE, _lazy("升级")),
        (OperationType.ROLLBACK, _lazy("回滚")),
        (OperationType.START, _lazy("启用")),
        (OperationType.STOP, _lazy("停用")),
        (OperationType.CREATE, _lazy("新增")),
        (OperationType.EDIT, _lazy("编辑")),
        (OperationType.ADD_DEL, _lazy("增删目标")),
    )

    OPERATION_RESULT_CHOICES = (
        (OperationResult.SUCCESS, _lazy("全部成功")),
        (OperationResult.WARNING, _lazy("部分成功")),
        (OperationResult.FAILED, _lazy("全部失败")),
        (OperationResult.DEPLOYING, _lazy("下发中")),
        (OperationResult.PREPARING, _lazy("准备中")),
    )

    class CollectType(CollectorPluginMeta.PluginType):
        LOG = "Log"
        SNMP_TRAP = "SNMP_Trap"

    COLLECT_TYPE_CHOICES = CollectorPluginMeta.PLUGIN_TYPE_CHOICES

    TARGET_OBJECT_TYPE_CHOICES = (
        (TargetObjectType.SERVICE, _lazy("服务")),
        (TargetObjectType.HOST, _lazy("主机")),
    )

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    name = models.CharField("配置名称", max_length=128)

    # 采集插件相关配置
    collect_type = models.CharField("采集方式", max_length=32, choices=COLLECT_TYPE_CHOICES, db_index=True)
    plugin = models.ForeignKey(
        CollectorPluginMeta, verbose_name="关联插件", related_name="collect_configs", on_delete=models.CASCADE
    )

    # 采集目标相关配置
    # 取值范围
    # target_object_type     target_node_type     说明
    # SERVICE                TOPO                 服务拓扑
    # HOST                   TOPO                 业务拓扑
    # HOST                   INSTANCE             主机实例
    target_object_type = models.CharField("采集对象类型", max_length=32, choices=TARGET_OBJECT_TYPE_CHOICES)

    deployment_config = models.ForeignKey("DeploymentConfigVersion", verbose_name="当前的部署配置", on_delete=models.CASCADE)
    cache_data = JsonField("缓存数据", default=None)
    last_operation = models.CharField("最近一次操作", max_length=32, choices=OPERATION_TYPE_CHOICES)
    operation_result = models.CharField("最近一次任务结果", max_length=32, choices=OPERATION_RESULT_CHOICES)

    label = models.CharField("二级标签", max_length=64, default="")

    def check_task_is_ready(self, deploying_mapping):
        """
        检查任务是否准备完毕并返回状态
        :param deploying_mapping: 部署状态列表映射
        :return: 任务状态
        """
        if resource.collecting.is_task_ready(bk_biz_id=self.bk_biz_id, collect_config_id=self.id):
            self.operation_result = OperationResult.DEPLOYING
            self.save(not_update_user=True)
            status = deploying_mapping.get(self.last_operation, Status.DEPLOYING)
        else:
            status = Status.PREPARING
        return status

    @property
    def config_status(self):
        """
        采集配置状态
        STARTING,  启用中
        STARTED,   已启用
        STOPPING,  停用中
        STOPPED,   已停用
        DEPLOYING, 执行中
        PREPARING, 准备中
        """
        deploying_mapping = {OperationType.STOP: Status.STOPPING, OperationType.START: Status.STARTING}
        if self.operation_result == OperationResult.PREPARING:
            config_status = self.check_task_is_ready(deploying_mapping)
        elif self.operation_result == OperationResult.DEPLOYING:
            config_status = deploying_mapping.get(self.last_operation, Status.DEPLOYING)
        else:
            config_status = Status.STOPPED if self.last_operation == OperationType.STOP else Status.STARTED

        return config_status

    @property
    def task_status(self):
        """
        获取任务状态
        FAILED: 上次任务调用失败/任务执行下发全部失败
        WARNING：任务执行下发部分失败
        SUCCESS：上次任务执行下发全部成功
        STOPPED：已停用
        PREPARING: 准备中
        DEPLOYING：执行中
        AUTO_DEPLOYING: 自动执行中
        STOPPING: 停用中
        STARTING: 启用中
        """
        deploying_mapping = {OperationType.STOP: TaskStatus.STOPPING, OperationType.START: TaskStatus.STARTING}
        if self.operation_result == OperationResult.PREPARING:
            task_status = self.check_task_is_ready(deploying_mapping)
        elif self.operation_result == OperationResult.DEPLOYING:
            task_status = deploying_mapping.get(self.last_operation, TaskStatus.DEPLOYING)
        else:
            # 任务状态不应该以最后一次任务结果为依据，否则会出现"异常"任务单击进入详情后主机状态却全部正常的情况

            # 如果不是在部署中，则优先提取缓存信息中的数量信息进行任务状态判断
            cache_data = self.cache_data
            if (
                cache_data
                and cache_data.get("error_instance_count") is not None
                and cache_data.get("total_instance_count") is not None
            ):
                error_count = cache_data["error_instance_count"]
                total_count = cache_data["total_instance_count"]
                if error_count == 0 and total_count >= 0:
                    task_status = TaskStatus.SUCCESS
                elif error_count == total_count:
                    task_status = TaskStatus.FAILED
                else:
                    task_status = TaskStatus.WARNING
            else:
                # 如果没有缓存，则只能以最后一次任务结果为依据
                task_status = self.operation_result

            # 已停止的采集配置单独控制
            if self.last_operation == OperationType.STOP:
                task_status = TaskStatus.STOPPED

        return task_status

    @property
    def allow_rollback(self):
        """
        操作是否可以回滚
        1. 增删目标、升级操作可以回滚, 启用、停用不可以回滚
        2. 回滚按钮只能点一次，上一次操作为回滚则不能再回滚
        """
        return self.last_operation in [OperationType.EDIT, OperationType.ADD_DEL, OperationType.UPGRADE]

    def get_cache_data(self, key, default_value):
        """
        获取缓存数据
        """
        if self.cache_data:
            return self.cache_data.get(key, default_value)

        return default_value

    @property
    def need_upgrade(self):
        """
        是否需要升级
        """
        # 如果采集配置处于已停用，或者主机/实例总数为0，则不需要升级
        if self.task_status == TaskStatus.STOPPED or self.get_cache_data("total_instance_count", 0) == 0:
            return False
        else:
            return (
                self.deployment_config.plugin_version.config_version
                < self.plugin.packaged_release_version.config_version
            )

    @property
    def label_info(self):
        if self.label == "other_rt":
            return _("其他")
        result = resource.commons.get_label_msg(self.label)
        return "{}-{}".format(result["first_label_name"], result["second_label_name"])

    def switch_config_version(self, target_deployment_config):
        """
        切换到对应配置版本
        """

        def switch_success(target_deployment_config, subscription_id):
            # 创建一个新的版本
            new_deployment_config = self.create_deployment_config(
                plugin_version=target_deployment_config.plugin_version,
                params=target_deployment_config.params,
                target_nodes=target_deployment_config.target_nodes,
                remote_collecting_host=target_deployment_config.remote_collecting_host,
                target_node_type=target_deployment_config.target_node_type,
            )
            new_deployment_config.subscription_id = subscription_id
            new_deployment_config.save()
            # 将目标版本置为当前版本
            self.deployment_config = new_deployment_config
            self.save()
            # 如果全局配置巡检开启，则启动订阅巡检
            if settings.IS_SUBSCRIPTION_ENABLED:
                api.node_man.switch_subscription(subscription_id=subscription_id, action="enable")

        diff_result = self.deployment_config.show_diff(target_deployment_config)

        task_id = None
        # 重新创建订阅的条件:1、插件版本发生升级 2、远程采集配置变更 3、克隆出的新任务，subscription_id为0
        operate_type = self.operate_type(diff_result)
        if operate_type == "rebuild":
            with transaction.atomic():
                prev_sub_id = self.deployment_config.subscription_id
                result = self.create_subscription(target_deployment_config)
                # 将目标版本置为当前版本
                task_id = result["task_id"]
                if prev_sub_id != 0:
                    self.delete_subscription(prev_sub_id)
                switch_success(target_deployment_config, result["subscription_id"])
        # 若改动仅为插件配置参数(params)或目标节点(nodes)，或者参数没有改动但是目标节点不为空，则编辑节点管理订阅配置
        elif operate_type == "update":
            with transaction.atomic():
                task_id = self.update_subscription(target_deployment_config)
                switch_success(target_deployment_config, self.deployment_config.subscription_id)

        return {"diff_result": diff_result, "task_id": task_id}

    def operate_type(self, diff_result):
        if self.collect_type == self.CollectType.LOG or self.collect_type == self.CollectType.SNMP_TRAP:
            return "update"
        if (
            diff_result["plugin_version"]["is_modified"]
            or diff_result["remote_collecting_host"]["is_modified"]
            or (not self.deployment_config.subscription_id)
        ):
            return "rebuild"
        elif (
            diff_result["params"]["is_modified"]
            or diff_result["nodes"]["is_modified"]
            or self.deployment_config.target_nodes
        ):
            return "update"

    def create_deployment_config(self, **kwargs):
        """
        创建一条部署配置记录
        """
        deployment_config = DeploymentConfigVersion.objects.create(
            parent_id=self.deployment_config.pk, config_meta_id=self.pk, **kwargs
        )
        return deployment_config

    def rollback(self):
        """
        回滚操作
        """
        last_deployment_config = self.deployment_config.last_version
        return self.switch_config_version(last_deployment_config)

    @property
    def data_id(self):
        if self.collect_type == self.CollectType.PROCESS:
            # 进程采集对应dataid 有两个，通过ProcessPluginManager.perf_data_id 和 port_data_id获取
            return None
        if self.collect_type == self.CollectType.LOG or self.collect_type == self.CollectType.SNMP_TRAP:
            data_accessor = EventDataAccessor(self.plugin.release_version, self.update_user)
        else:
            data_accessor = PluginDataAccessor(self.plugin.release_version, self.update_user)
        return data_accessor.get_data_id()

    def create_plugin_collecting_steps(self, target_deployment_config, data_id):
        plugin_manager = PluginManagerFactory.get_manager(plugin=self.plugin)
        config_params = copy.deepcopy(target_deployment_config.params)

        # 获取维度注入参数
        config_json = target_deployment_config.plugin_version.config.config_json
        dms_insert_params = {}
        for param in config_json:
            if param["mode"] == ParamMode.DMS_INSERT:
                param_value = config_params["plugin"].get(param['name'])
                for dms_key, dms_value in list(param_value.items()):
                    if param["type"] == "host":
                        dms_insert_params[dms_key] = "{{ " + f"cmdb_instance.host.{dms_value} or '-'" + " }}"
                    else:
                        dms_insert_params[dms_key] = (
                            "{{ " + f"cmdb_instance.service.labels['{dms_value}'] or '-'" + " }}"
                        )

        if self.plugin.plugin_type == PluginType.PROCESS:
            # processbeat 配置
            # processbeat 采集不需要dataid
            config_params["collector"].update(
                {
                    "taskid": str(self.id),
                    "namespace": self.plugin_id,
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
                            "bk_collect_config_id": self.id,
                            "bk_biz_id": str(self.bk_biz_id),
                        },
                    },
                    "tags": config_params["collector"].get("tag", {}),
                }
            )
        else:
            # bkmonitorbeat通用配置参数
            config_params["collector"].update(
                {
                    "task_id": str(self.id),
                    "bk_biz_id": str(self.bk_biz_id),
                    "config_name": self.plugin_id,
                    "config_version": "1.0",
                    "namespace": self.plugin_id,
                    "period": str(config_params["collector"]["period"]),
                    # 采集超时时间
                    "timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "max_timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "dataid": str(data_id or self.data_id),
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
                            "bk_collect_config_id": self.id,
                            # 维度注入模板变量
                            **dms_insert_params,
                        },
                    },
                }
            )
        config_params["subscription_id"] = self.deployment_config.subscription_id
        return plugin_manager.get_deploy_steps_params(
            target_deployment_config.plugin_version, config_params, target_deployment_config.target_nodes
        )

    def get_deploy_params(self, target_deployment_config=None, data_id=None):
        # 切换配置时若需要创建新的订阅则需要传入新的部署配置
        if not target_deployment_config:
            target_deployment_config = self.deployment_config

        if not data_id:
            data_id = self.data_id

        subscription_params = {
            "scope": {
                "bk_biz_id": self.bk_biz_id,
                "object_type": self.target_object_type,
                "node_type": target_deployment_config.target_node_type,
                "nodes": [target_deployment_config.remote_collecting_host]
                if self.plugin.plugin_type == PluginType.SNMP
                else target_deployment_config.target_nodes,
            },
            "steps": [],
            "run_immediately": True,
        }

        deploy_steps = self.create_plugin_collecting_steps(target_deployment_config, data_id)
        for step in deploy_steps:
            subscription_params["steps"].append(step)

        # 在组装节点管理创建订阅时，target_hosts被定义为远程下发采集配置文件与执行采集任务的主机
        if target_deployment_config.remote_collecting_host:
            if self.plugin.plugin_type == PluginType.SNMP:
                return subscription_params
            subscription_params["target_hosts"] = [target_deployment_config.remote_collecting_host]

        return subscription_params

    def create_subscription(self, target_deployment_config=None):
        """
        创建订阅事件
        """
        create_subscription_params = self.get_deploy_params(target_deployment_config)
        logger.info("create subscriptino param is {}".format(json.dumps(create_subscription_params)))
        result = api.node_man.create_subscription(create_subscription_params)
        return {"subscription_id": result["subscription_id"], "task_id": result["task_id"]}

    def trigger_subscription(self, subscription_id=None, scope=None, steps=None, action=None):
        """
        主动触发订阅事件
        """
        params = {"subscription_id": subscription_id or self.deployment_config.subscription_id}
        if not params["subscription_id"]:
            return ""

        if scope:
            params["scope"] = scope

        if steps:
            params["actions"] = steps
        elif action:
            subscription_param = self.get_deploy_params()
            params["actions"] = {step["id"]: action for step in subscription_param.get("steps", [])}

        logger.info("trigger subscription param is {}".format(json.dumps(params)))
        result = api.node_man.run_subscription(**params)
        logger.info("trigger subscription task id is: {}".format(result["task_id"]))
        return result["task_id"]

    def retry_subscription(self, subscription_id=None, instance_id_list=None):
        """
        重试整个订阅或某个实例和主机
        """
        params = {"subscription_id": subscription_id or self.deployment_config.subscription_id}
        if not params["subscription_id"]:
            return ""

        if instance_id_list:
            params["instance_id_list"] = instance_id_list

        logger.info("retry subscription param is {}".format(json.dumps(params)))
        result = api.node_man.retry_subscription(**params)
        logger.info("retry subscription task id is: {}".format(result["task_id"]))
        return result["task_id"]

    def update_subscription(self, target_deployment_config):
        if not self.deployment_config.subscription_id:
            return ""
        deploy_params = self.get_deploy_params(target_deployment_config)
        update_params = {
            "subscription_id": self.deployment_config.subscription_id,
            "scope": {
                "bk_biz_id": self.bk_biz_id,
                "node_type": deploy_params["scope"]["node_type"],
                "nodes": deploy_params["scope"]["nodes"],
            },
            "steps": deploy_params.get("steps", []),
            "run_immediately": True,
        }

        logger.info("update subsription param is {}".format(json.dumps(update_params)))
        result = api.node_man.update_subscription(**update_params)

        return result["task_id"]

    def delete_subscription(self, subscription_id=None):
        # 删除订阅前需要先主动触发卸载操作
        self.trigger_subscription(subscription_id=subscription_id, action="UNINSTALL")
        if subscription_id is None:
            subscription_id = self.deployment_config.subscription_id
        if subscription_id != 0:
            api.node_man.delete_subscription(subscription_id=subscription_id)
        self.delete_event_plugin()

    def delete_event_plugin(self):
        version = self.deployment_config.plugin_version
        plugin_type = version.plugin.plugin_type
        if plugin_type in version.plugin.VIRTUAL_PLUGIN_TYPE:
            plugin_manager = PluginManagerFactory.get_manager(version.plugin, plugin_type)
            plugin_manager.delete_result_table(version)

    def switch_subscription(self, action):
        """
        启停订阅的自动执行
        """
        if self.deployment_config.subscription_id:
            api.node_man.switch_subscription(subscription_id=self.deployment_config.subscription_id, action=action)


class DeploymentConfigVersion(OperateRecordModelBase):
    """
    部署版本历史
    """

    TARGET_NODE_TYPE_CHOICES = (
        (TargetNodeType.TOPO, _lazy("拓扑")),
        (TargetNodeType.INSTANCE, _lazy("实例")),
        (TargetNodeType.SERVICE_TEMPLATE, _lazy("服务模板")),
        (TargetNodeType.SET_TEMPLATE, _lazy("集群模板")),
    )

    plugin_version = models.ForeignKey(
        PluginVersionHistory, verbose_name="关联插件版本", related_name="deployment_versions", on_delete=models.CASCADE
    )

    parent_id = models.IntegerField("父配置ID", default=None, null=True)
    config_meta_id = models.IntegerField("所属采集配置ID")
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)

    target_node_type = models.CharField("采集目标类型", max_length=32, choices=TARGET_NODE_TYPE_CHOICES)

    # 采集参数配置 example
    # {
    #     'collector': {
    #         'period': 60,  # 采集周期
    #         'host': '${target_host.inner_ip}',  # TODO: 如何支持CMDB变量
    #         'port': '9107',
    #     },
    #     'plugin': {
    #         '--web.listen-address': '${host}:${port}',
    #     }
    # }
    params = SymmetricJsonField("采集参数配置", default=None)

    # 采集目标节点列表，数据结构为以下其中一种
    # 服务拓扑
    # [
    #     {
    #         'bk_inst_id': 33,   # 节点实例ID
    #         'bk_obj_id': 'module',  # 节点对象ID
    #     }
    # ]
    # 业务拓扑
    # [
    #     {
    #         'bk_inst_id': 33,   # 节点实例ID
    #         'bk_obj_id': 'module',  # 节点对象ID
    #     }
    # ]
    # 主机实例
    # [
    #     {
    #         'ip': '127.0.0.1',
    #         'bk_cloud_id': 0,
    #         'bk_supplier_id': 0,
    #     }
    # ]
    target_nodes = JsonField("采集目标节点", default=[])

    # 远程采集，若为空则代表不使用远程采集模式
    # {
    #     'ip': '127.0.0.1',
    #     'bk_cloud_id': 0,
    #     'bk_supplier_id': 0,
    #     'is_collecting_only': True  # 是否为采集专用机器
    # }
    remote_collecting_host = JsonField("远程采集机器", default=None)
    task_ids = JsonField("任务id列表", default=None)

    def __str__(self):
        return f"{self.target_node_type}-{self.plugin_version}"

    @property
    def last_version(self):
        """
        上一次部署历史
        """
        return DeploymentConfigVersion.objects.filter(pk=self.parent_id).first()

    @property
    def metrics(self):
        """
        获取表结构
        """
        if self.plugin_version.plugin.plugin_id == "bkprocessbeat":
            return PluginManagerFactory.get_manager(plugin="bkprocessbeat").gen_metric_info()
        last_version = self.plugin_version.plugin.get_release_ver_by_config_ver(self.plugin_version.config_version)
        return last_version.info.metric_json

    def show_diff(self, target_config):
        """
        比对两个版本的配置，并返回差异点
        """
        diff_result = {
            "plugin_version": {
                "is_modified": self.plugin_version != target_config.plugin_version,  # 插件版本是否改变
                "before": self.plugin_version.version,
                "after": target_config.plugin_version.version,
            },
            "params": {
                "is_modified": self.params != target_config.params,  # 采集参数是否改变
                "before": self.params,
                "after": target_config.params,
            },
            "remote_collecting_host": {
                "is_modified": self.remote_collecting_host != target_config.remote_collecting_host,
                "before": self.remote_collecting_host,
                "after": target_config.remote_collecting_host,
            },
            "nodes": {
                "is_modified": False,
                "added": [],  # 新增节点
                "updated": [],  # 被更新的节点
                "removed": [],  # 被删除的节点
                "unchanged": [],  # 不变的节点
            },
        }
        if diff_result["plugin_version"]["is_modified"]:
            diff_result["nodes"]["updated"] = self.target_nodes
            diff_result["nodes"]["is_modified"] = True
            return diff_result

        old_config_nodes = self.target_nodes[:]

        if (
            target_config.target_node_type != self.target_node_type
            or target_config.remote_collecting_host != target_config.remote_collecting_host
        ):
            diff_result["nodes"]["added"] = target_config.target_nodes
            diff_result["nodes"]["removed"] = self.target_nodes
        else:
            for new_node in target_config.target_nodes:
                for old_node in self.target_nodes:
                    if new_node == old_node:
                        # 新配置中能找到老配置的节点
                        if diff_result["params"]["is_modified"] or diff_result["remote_collecting_host"]["is_modified"]:
                            # 如果参数已被修改，则需要更新配置
                            diff_result["nodes"]["updated"].append(new_node)
                        else:
                            # 如果参数没有修改，则不需要做任何事情
                            diff_result["nodes"]["unchanged"].append(new_node)
                        old_config_nodes.remove(old_node)
                        break
                else:
                    # 新配置中没找到老配置的节点，则为新增
                    diff_result["nodes"]["added"].append(new_node)

        # 没被匹配过的剩余的老节点，则为需要删除的节点
        diff_result["nodes"]["removed"] = old_config_nodes
        diff_result["nodes"]["is_modified"] = any(
            [diff_result["nodes"]["added"], diff_result["nodes"]["updated"], diff_result["nodes"]["removed"]]
        )

        return diff_result
