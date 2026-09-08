import collections
import logging
from typing import Any, Literal, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import CollectStatus, TargetNodeType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import NodemanPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.built_in import BuiltInPluginManager
from bk_monitor_base.domains.metric_plugin.manager.tools import get_nodeman_deploy_plugin_manager
from bk_monitor_base.domains.metric_plugin.models import MetricPluginDeploymentModel, MetricPluginDeploymentVersionModel
from bk_monitor_base.infras.third_party_api.cmdb import api as cmdb_api
from bk_monitor_base.infras.third_party_api.cmdb.api import FindTopoNodePathNode
from bk_monitor_base.infras.third_party_api.nodeman.api import (
    CreateSubscriptionParams,
    CreateSubscriptionResult,
    ScopeParams,
    SubscriptionTaskResult,
    UpdateSubscriptionParams,
    batch_get_subscription_task_result,
    check_subscription_task_ready,
    create_subscription,
    get_subscription_task_result_detail,
    retry_subscription,
    revoke_subscription,
    run_subscription,
    switch_subscription,
    update_subscription,
)

from ..define import (
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
)
from ..errors import MetricPluginDeploymentOperationError
from .base import BaseInstaller

logger = logging.getLogger(__name__)


@final
class NodemanInstaller(BaseInstaller):
    """
    Nodeman 安装器

    Note:
        1. 该安装器通过节点管理的订阅功能进行插件的安装、卸载、启动、停止、调试、状态查询等操作。
        2. 在MetricPluginDeployment的related_params中需要记录节点管理的订阅ID。
        3. 在MetricPlugin或MetricPluginVersion的related_params中需要记录下发时使用的数据ID,
           数据ID存储在哪里取决于插件的类型或配置。
        4. 在MetricPluginDeployment的related_params中记录订阅任务ID
    """

    def __init__(self, deployment: MetricPluginDeployment, operator: str):
        super().__init__(deployment, operator)
        self.plugin_manager: NodemanPluginManager | BuiltInPluginManager = get_nodeman_deploy_plugin_manager(
            self.plugin
        )

    def _get_subscription_scope(self, deployment_version: MetricPluginDeploymentVersion) -> ScopeParams:
        """构建订阅范围参数。

        Args:
            deployment_version: 部署版本。

        Returns:
            节点管理订阅范围参数。
        """
        return {
            "bk_biz_id": self.deployment.bk_biz_id,
            "object_type": self._label_to_object_type(self.plugin.label),
            "node_type": "INSTANCE"
            if deployment_version.target_scope.node_type == TargetNodeType.HOST.value
            else deployment_version.target_scope.node_type,
            "nodes": deployment_version.target_scope.nodes,
        }

    def _create_subscription(self, deployment_version: MetricPluginDeploymentVersion) -> CreateSubscriptionResult:
        """创建节点管理订阅。

        Args:
            deployment_version: 部署版本。

        Returns:
            节点管理创建订阅接口返回结果，由调用方负责回填部署状态。
        """
        create_subscription_params = self._get_deploy_params(deployment_version)
        logger.debug("install plugin %s: create_subscription params=%s", self.plugin.id, create_subscription_params)
        return create_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            params=create_subscription_params,
        )

    def _update_subscription(self, deployment_version: MetricPluginDeploymentVersion) -> dict[str, Any]:
        """更新节点管理订阅。

        Args:
            deployment_version: 部署版本。

        Returns:
            节点管理更新订阅接口返回结果，由调用方负责回填部署状态。

        Raises:
            MetricPluginDeploymentOperationError: 订阅ID不存在。
        """
        subscription_id = self.subscription_id
        if not subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        deploy_params: UpdateSubscriptionParams = {
            "subscription_id": subscription_id,
            "steps": self.plugin_manager.get_deploy_steps_params(
                bk_biz_id=self.deployment.bk_biz_id,
                collect_task_id=self.deployment.id,
                bk_data_ids=self.get_data_ids(),
                collect_params=deployment_version.params.get("collector", {}),
                plugin_params=deployment_version.params.get("plugin", {}),
                target_nodes=deployment_version.target_scope.nodes,
            ),
            "run_immediately": True,
            "scope": self._get_subscription_scope(deployment_version),
        }
        logger.debug("install plugin %s: update_subscription params=%s", self.plugin.id, deploy_params)
        return update_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            params=deploy_params,
        )

    @override
    def install(self, deployment_version: MetricPluginDeploymentVersion) -> Any:
        """安装特定的部署版本

        Args:
            deployment_version: 部署版本
        """
        # 加载当前版本（如果尚未加载）
        if not self.deployment_version:
            self.deployment_version = self._get_current_deployment_version()
        # 比对当前版本与新版本，判断是否存在差异(不存在current_version则视为有变化)
        is_modified, diff_result = self.get_version_diff(self.deployment_version, deployment_version)
        # 如果没有变化，则复用上一版本的版本号，不产生新版本记录
        if not is_modified:
            if not self.deployment_version:
                raise RuntimeError("安装逻辑错误：当前版本不存在且新版本无变化")
            deployment_version.version = self.deployment_version.version
        deployment_model = MetricPluginDeploymentModel.objects.get(id=deployment_version.deployment_id)
        # 保存版本记录并更新当前版本标识
        remote_scope = deployment_version.remote_scope
        MetricPluginDeploymentVersionModel.objects.update_or_create(
            bk_tenant_id=deployment_version.bk_tenant_id,
            bk_biz_id=deployment_version.bk_biz_id,
            deployment=deployment_model,
            version=deployment_version.version,
            defaults={
                "plugin_version": f"{deployment_version.plugin_version.major}.{deployment_version.plugin_version.minor}",
                "params": deployment_version.params,
                "target_node_type": deployment_version.target_scope.node_type,
                "target_nodes": deployment_version.target_scope.nodes,
                "remote_node_type": remote_scope.node_type if remote_scope else "",
                "remote_nodes": remote_scope.nodes if remote_scope else [],
                "is_current": True,
                "created_by": deployment_version.created_by,
            },
        )
        # 将该部署项的其他版本设置为非当前版本
        MetricPluginDeploymentVersionModel.objects.filter(
            deployment=deployment_model,
            bk_tenant_id=deployment_model.bk_tenant_id,
            bk_biz_id=deployment_model.bk_biz_id,
        ).exclude(version=deployment_version.version).update(is_current=False)

        # 如果当前版本不存在或订阅ID不存在，则创建订阅
        task_id: int | None
        if not self.deployment_version or not self.subscription_id:
            create_result = self._create_subscription(deployment_version)
            self.subscription_id = create_result["subscription_id"]
            task_id = create_result["task_id"]
            logger.debug(
                "install plugin %s: create_subscription result subscription_id=%s task_id=%s",
                self.plugin.id,
                self.subscription_id,
                task_id,
            )
        else:
            update_result = self._update_subscription(deployment_version)
            task_id = update_result.get("task_id")
            logger.debug(
                "install plugin %s: update_subscription result task_id=%s",
                self.plugin.id,
                task_id,
            )

        self.deployment.related_params["subscription_task_id"] = task_id

        # 更新部署状态
        self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value

        # 更新当前版本对象为新版本对象，以便保存
        self.deployment_version = deployment_version

        # 保存到数据库
        self._save()

        return {
            "deployment_id": self.deployment.id,
            "subscription_task_id": self.deployment.related_params["subscription_task_id"],
            "subscription_id": self.subscription_id,
            "diff_result": diff_result,
        }

    @override
    def uninstall(self) -> Any:
        """卸载插件

        Note:
            只有在停用状态下才能卸载
        """
        if self.deployment.status != MetricPluginDeploymentStatusEnum.STOPPED.value:
            raise MetricPluginDeploymentOperationError("只有在停用状态下才能卸载")

        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")

        # 获取部署步骤参数
        deploy_steps = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=self.deployment.bk_biz_id,
            collect_task_id=self.deployment.id,
            bk_data_ids=self.get_data_ids(),
            collect_params=current_version.params.get("collector", {}),
            plugin_params=current_version.params.get("plugin", {}),
            target_nodes=current_version.target_scope.nodes,
        )

        # 执行卸载操作
        if self.subscription_id:
            actions = {step["id"]: "UNINSTALL_AND_DELETE" for step in deploy_steps}
            logger.debug("uninstall plugin %s: run_subscription actions=%s", self.plugin.id, actions)
            run_subscription(
                bk_tenant_id=self.deployment.bk_tenant_id,
                subscription_id=self.subscription_id,
                actions=actions,
            )

        # 删除部署版本和部署项
        MetricPluginDeploymentVersionModel.objects.filter(deployment=self.deployment).delete()
        MetricPluginDeploymentModel.objects.filter(id=self.deployment.id).delete()

    @override
    def stop(self) -> Any:
        """停止插件

        Note:
            1. 如果部署状态为初始化（未下发）或已停止，则直接返回。
            2. 如果部署状态为运行中，则停止插件。
            3. 如果部署状态为停止中，也允许重复调用。
        """
        # 如果部署状态为初始化（未下发）或已停止，则直接返回
        if self.deployment.status in [
            MetricPluginDeploymentStatusEnum.INITIALIZING.value,
            MetricPluginDeploymentStatusEnum.STOPPED.value,
        ]:
            return

        # 检查订阅ID是否存在
        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        # 只有运行中或停止中状态才能执行停止
        if self.deployment.status not in [
            MetricPluginDeploymentStatusEnum.RUNNING.value,
            MetricPluginDeploymentStatusEnum.STOPPING.value,
        ]:
            raise MetricPluginDeploymentOperationError(f"部署状态为{self.deployment.status}，无法停止")

        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version

        # 停用订阅巡检
        switch_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            action="disable",
        )

        # 获取部署步骤参数
        deploy_steps = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=self.deployment.bk_biz_id,
            collect_task_id=self.deployment.id,
            bk_data_ids=self.get_data_ids(),
            collect_params=current_version.params.get("collector", {}),
            plugin_params=current_version.params.get("plugin", {}),
            target_nodes=current_version.target_scope.nodes,
        )
        actions = {step["id"]: "STOP" for step in deploy_steps}
        logger.debug("stop plugin %s: run_subscription actions=%s", self.plugin.id, actions)

        # 执行停止操作
        result = run_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            actions=actions,
        )

        # 更新部署状态
        task_id = result.get("task_id")
        self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPING.value
        self.deployment.related_params["subscription_task_id"] = task_id
        logger.debug("stop plugin %s: run_subscription result task_id=%s", self.plugin.id, task_id)

        # 保存到数据库
        self._save()

    @override
    def start(self) -> Any:
        """启动插件"""
        if self.deployment.status not in [
            MetricPluginDeploymentStatusEnum.STOPPED.value,
            MetricPluginDeploymentStatusEnum.STARTING.value,
        ]:
            raise MetricPluginDeploymentOperationError(f"部署状态为{self.deployment.status}，无法启动")

        # 检查订阅ID是否存在
        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version

        # 获取部署步骤参数
        deploy_steps = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=self.deployment.bk_biz_id,
            collect_task_id=self.deployment.id,
            bk_data_ids=self.get_data_ids(),
            collect_params=current_version.params.get("collector", {}),
            plugin_params=current_version.params.get("plugin", {}),
            target_nodes=current_version.target_scope.nodes,
        )
        actions = {step["id"]: "START" for step in deploy_steps}
        logger.debug("start plugin %s: run_subscription actions=%s", self.plugin.id, actions)

        # 执行启动操作
        result = run_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            actions=actions,
        )

        # 更新部署状态
        task_id = result.get("task_id")
        self.deployment.status = MetricPluginDeploymentStatusEnum.STARTING.value
        self.deployment.related_params["subscription_task_id"] = task_id
        logger.debug("start plugin %s: run_subscription result task_id=%s", self.plugin.id, task_id)

        # 保存到数据库
        self._save()

    @override
    def run(
        self,
        action: str | None = None,
        scope: MetricPluginDeploymentScope | None = None,
    ) -> Any:
        """主动执行操作"""
        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version

        deploy_steps = self.plugin_manager.get_deploy_steps_params(
            bk_biz_id=self.deployment.bk_biz_id,
            collect_task_id=self.deployment.id,
            bk_data_ids=self.get_data_ids(),
            collect_params=current_version.params.get("collector", {}),
            plugin_params=current_version.params.get("plugin", {}),
            target_nodes=current_version.target_scope.nodes,
        )
        actions = {step["id"]: action for step in deploy_steps}

        scope_params: ScopeParams | None = None
        if scope:
            scope_params = {
                "bk_biz_id": self.deployment.bk_biz_id,
                "node_type": scope.node_type,
                "nodes": scope.nodes,
            }

        logger.debug("run plugin %s: run_subscription actions=%s scope=%s", self.plugin.id, actions, scope_params)

        run_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            actions=actions,
            scope=scope_params,
        )

    @override
    def retry(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """重试

        Args:
            scope: 操作范围, 必须包含instance_id, 如果为 None，则为全部

        Raises:
            MetricPluginDeploymentOperationError: 当前版本不存在或订阅ID不存在
        """
        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version

        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        instance_ids: list[Any] | None = None
        if scope:
            instance_ids = [node["instance_id"] for node in scope.nodes]

        retry_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            instance_ids=instance_ids,
        )

    @override
    def revoke(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """终止执行

        Args:
            scope: 操作范围, 必须包含instance_id, 如果为 None，则为全部

        Raises:
            MetricPluginDeploymentOperationError: 当前版本不存在或订阅ID不存在
        """
        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version

        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        instance_ids: list[Any] | None = None
        if scope:
            instance_ids = [node["instance_id"] for node in scope.nodes]

        revoke_subscription(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            instance_ids=instance_ids,
        )

    @override
    def status(self):
        """获取当前采集下发的所有实例的状态

        Returns:
            list[list[dict[str, Any]]]:

            Examples:
            1. 目标是拓扑节点，实例类型为服务实例
            [
                {
                    "child": [
                        {
                            "instance_id": "service|instance|service|1",
                            "ip": "127.0.0.1",
                            "bk_cloud_id": 0,
                            "bk_host_id": 1,
                            "bk_host_name": "kafka-default-10",
                            "bk_supplier_id": "0",
                            "task_id": 1,
                            "status": "SUCCESS",
                            "plugin_version": "2.2",
                            "log": "",
                            "action": "install",
                            "steps": {
                                "kafka_BytesPerSec": "INSTALL",
                                "bkmonitorbeat": "INSTALL"
                            },
                            "instance_name": "127.0.0.1_kafka_9092",
                            "service_instance_id": 1,
                            "bk_module_id": 1
                        }
                    ],
                    "node_name": "蓝鲸/公共组件/kafka",
                    "node_type": "TOPO",
                    "node_id": "module|1",

                    "bk_obj_id": "module",
                    "bk_inst_id": 1,
                    "bk_inst_name": "kafka"
                }
            ]

            2. 目标是动态分组，实例类型为主机实例
            [
                {
                    "child": [
                        {
                            "instance_id": "host|instance|host|1",
                            "ip": "127.0.0.1",
                            "bk_cloud_id": 0,
                            "bk_host_id": 1,
                            "bk_host_name": "VM-test-host-149",
                            "bk_supplier_id": "0",
                            "task_id": 1,
                            "status": "SUCCESS",
                            "plugin_version": "1.1",
                            "log": "[bkmonitorbeat] 下发插件配置-初始化进程状态",
                            "action": "install",
                            "steps": {"bkmonitorbeat": "INSTALL"},
                            "instance_name": "127.0.0.1",
                            "bk_module_ids": [1]
                        },
                        {
                            "instance_id": "host|instance|host|2",
                            "ip": "127.0.0.2",
                            "bk_cloud_id": 0,
                            "bk_host_id": 2,
                            "bk_host_name": "VM-test-host-229",
                            "bk_supplier_id": "0",
                            "task_id": 1,
                            "status": "SUCCESS",
                            "plugin_version": "1.1",
                            "log": "[bkmonitorbeat] 下发插件配置-初始化进程状态",
                            "action": "install",
                            "steps": {"bkmonitorbeat": "INSTALL"},
                            "instance_name": "127.0.0.2",
                            "bk_module_ids": [1]
                        }
                    ],
                    "node_name": "动态分组1",
                    "node_type": "DYNAMIC_GROUP",
                    "node_id": "dynamic_group|1",

                    "bk_obj_id": "dynamic_group",
                    "bk_inst_id": "xxxxxxxx",
                    "bk_inst_name": "动态分组1"
                }
            ]

            3. 目标是主机实例，实例类型为主机实例
            [
                {
                    "child": [
                        {
                            "instance_id": "host|instance|host|1",
                            "ip": "127.0.0.1",
                            "bk_cloud_id": 0,
                            "bk_host_id": 1,
                            "bk_host_name": "VM-test-host-149",
                            "bk_supplier_id": "0",
                            "task_id": 1,
                            "status": "SUCCESS",
                            "plugin_version": "1.2",
                            "log": "",
                            "action": "install",
                            "steps": {"bkmonitorbeat": "INSTALL"},
                            "instance_name": "127.0.0.1",
                            "bk_module_ids": [1]
                        },
                        {
                            "instance_id": "host|instance|host|2",
                            "ip": "127.0.0.2",
                            "bk_cloud_id": 0,
                            "bk_host_id": 2,
                            "bk_host_name": "VM-test-host-229",
                            "bk_supplier_id": "0",
                            "task_id": 1,
                            "status": "SUCCESS",
                            "plugin_version": "1.2",
                            "log": "",
                            "action": "install",
                            "steps": {"lgtt": "INSTALL", "bkmonitorbeat": "INSTALL"},
                            "instance_name": "127.0.0.2",
                            "bk_module_ids": [1]
                        },
                    ],

                    "node_name": "主机",
                    "node_type": "HOST",
                    "node_id": "host"
                }
            ]

            返回的实例是双层的树状结构，第一层是节点类型，第二层是实例列表。
            如果目标类型直接就是实例，则第一层固定只有一个，节点类型就是实例类型。
        """
        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        self.deployment_version = self._get_current_deployment_version()
        if not self.deployment_version:
            raise MetricPluginDeploymentOperationError("部署版本不存在")

        bk_tenant_id = self.deployment.bk_tenant_id
        bk_biz_id = self.deployment.bk_biz_id

        # 如果部署版本有远程范围，则使用远程范围，否则使用目标范围
        target_scope = self.deployment_version.remote_scope or self.deployment_version.target_scope

        # 获取订阅是否准备就绪（未就绪跳过状态更新）可能出现后续获取状态订阅已经 ready 了，但是也就多轮询一轮而已
        is_task_ready = check_subscription_task_ready(
            bk_tenant_id=bk_tenant_id,
            subscription_id=self.subscription_id,
        )

        # 获取订阅任务结果
        results, _ = batch_get_subscription_task_result(
            bk_tenant_id=bk_tenant_id,
            params={
                "subscription_id": self.subscription_id,
                "need_detail": True,
                "need_aggregate_all_tasks": True,  # 全量则 nodeman 不会校验 task is ready
            },
        )

        if not is_task_ready:
            # 对 status 强制设置为 pending，因为此时节点管理的状态可能还未更新为 ready，导致外部获取到的状态不一致
            for result in results:
                result["status"] = CollectStatus.PENDING.value
        # 解析订阅任务结果为实例列表
        instance_results = [_process_instance_result(result) for result in results]

        # 更新部署项状态
        if instance_results:
            all_status = {result["status"] for result in instance_results}
            new_status = self.deployment.status
            if "FAILED" in all_status:
                new_status = MetricPluginDeploymentStatusEnum.FAILED.value
            elif all_status == {"SUCCESS"}:
                # 全部成功，根据当前动作判断
                if self.deployment.status == MetricPluginDeploymentStatusEnum.STOPPING.value:
                    new_status = MetricPluginDeploymentStatusEnum.STOPPED.value
                else:
                    new_status = MetricPluginDeploymentStatusEnum.RUNNING.value
            elif any(s in ["RUNNING", "PENDING"] for s in all_status):
                # 还在运行中，保持原有的中间状态（DEPLOYING/STARTING/STOPPING）
                if self.deployment.status not in [
                    MetricPluginDeploymentStatusEnum.DEPLOYING.value,
                    MetricPluginDeploymentStatusEnum.STARTING.value,
                    MetricPluginDeploymentStatusEnum.STOPPING.value,
                ]:
                    new_status = MetricPluginDeploymentStatusEnum.DEPLOYING.value

            if new_status != self.deployment.status:
                self.deployment.status = new_status
                MetricPluginDeploymentModel.objects.filter(id=self.deployment.id).update(status=new_status)

        # 获取拓扑节点状态结果
        topo_node_status_results: dict[str, dict[str, Any]] = {}

        if target_scope.node_type == TargetNodeType.TOPO.value:
            # 解析拓扑节点信息
            topo_node_status_results = _get_topo_infos(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                target_nodes=target_scope.nodes,
            )

            # 通过实例的related_node_ids关联拓扑节点
            for instance_result in instance_results:
                for related_node_id in instance_result["related_node_ids"]:
                    if related_node_id in topo_node_status_results:
                        topo_node_status_results[related_node_id]["child"].append(instance_result)
        elif target_scope.node_type == TargetNodeType.DYNAMIC_GROUP.value:
            # 解析动态分组节点信息
            topo_node_status_results, host_to_dynamic_group_ids = _get_dynamic_group_infos(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                target_nodes=target_scope.nodes,
            )

            # 通过主机ID到动态分组ID的映射，关联动态分组节点
            for instance_result in instance_results:
                bk_host_id = instance_result["bk_host_id"]
                dynamic_group_ids = host_to_dynamic_group_ids.get(bk_host_id, [])
                for dynamic_group_id in dynamic_group_ids:
                    node_id = f"dynamic_group|{dynamic_group_id}"
                    if node_id in topo_node_status_results:
                        topo_node_status_results[node_id]["child"].append(instance_result)
        elif target_scope.node_type in [TargetNodeType.SET_TEMPLATE.value, TargetNodeType.SERVICE_TEMPLATE.value]:
            topo_node_status_results, topo_node_to_template_id = _get_template_infos(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                target_nodes=target_scope.nodes,
            )

            # 通过集群ID到集群模板的映射，关联集群模板节点
            for instance_result in instance_results:
                for related_node_id in instance_result["related_node_ids"]:
                    if related_node_id not in topo_node_to_template_id:
                        continue
                    template_node_id = topo_node_to_template_id[related_node_id]
                    if template_node_id in topo_node_status_results:
                        topo_node_status_results[template_node_id]["child"].append(instance_result)
        elif target_scope.node_type == TargetNodeType.HOST.value:
            return [
                {
                    "child": instance_results,
                    "node_name": "主机",
                    "node_type": TargetNodeType.HOST.value,
                    "node_id": "host",
                }
            ]
        else:
            raise MetricPluginDeploymentOperationError("不支持的目标实例类型")

        return list(topo_node_status_results.values())

    def get_data_ids(self) -> dict[str, int]:
        """获取数据ID"""
        return self.plugin_manager.get_data_ids(bk_biz_id=self.deployment.bk_biz_id)

    @property
    def subscription_id(self) -> int | None:
        """获取订阅ID"""
        return self.deployment.related_params.get("subscription_id")

    @subscription_id.setter
    def subscription_id(self, value: int) -> None:
        """设置订阅ID"""
        self.deployment.related_params["subscription_id"] = value

        # 记录订阅ID历史
        subscription_id_history: list[int] = self.deployment.related_params.get("subscription_id_history", [])
        subscription_id_history.append(value)
        self.deployment.related_params["subscription_id_history"] = subscription_id_history

    @staticmethod
    def _label_to_object_type(label: str) -> Literal["HOST", "SERVICE"]:
        """将插件标签转换为目标对象类型"""
        if label in ["service_module", "component"]:
            return "SERVICE"
        else:
            return "HOST"

    def _get_deploy_params(self, deployment_version: MetricPluginDeploymentVersion) -> CreateSubscriptionParams:
        """获取订阅部署参数"""
        deploy_params: CreateSubscriptionParams = {
            "steps": self.plugin_manager.get_deploy_steps_params(
                bk_biz_id=self.deployment.bk_biz_id,
                collect_task_id=self.deployment.id,
                bk_data_ids=self.get_data_ids(),
                collect_params=deployment_version.params.get("collector", {}),
                plugin_params=deployment_version.params.get("plugin", {}),
                target_nodes=deployment_version.target_scope.nodes,
            ),
            "run_immediately": True,
            "scope": self._get_subscription_scope(deployment_version),
        }

        # 获取部署目标，如果远程采集且远程节点非空，则使用远程节点，否则使用目标节点
        if deployment_version.remote_scope and deployment_version.remote_scope.nodes:
            # 采集目标
            deploy_params["target_hosts"] = deployment_version.remote_scope.nodes

        return deploy_params

    def instance_status(self, instance_id: str) -> dict[str, Any]:
        """获取单个实例的状态

        Args:
            instance_id: 实例ID

        Returns:
            dict[str, Any]: 实例状态信息
        """
        if not self.subscription_id:
            raise MetricPluginDeploymentOperationError("订阅ID不存在")

        if "subscription_task_id" not in self.deployment.related_params:
            raise MetricPluginDeploymentOperationError("订阅任务ID不存在")

        result = get_subscription_task_result_detail(
            bk_tenant_id=self.deployment.bk_tenant_id,
            subscription_id=self.subscription_id,
            instance_id=instance_id,
            task_id_list=[int(self.deployment.related_params.get("subscription_task_id", 0))],
        )
        if result:
            log: list[str] = []
            for step in result.get("steps", []):
                log.append("{}{}{}\n".format("=" * 20, step["node_name"], "=" * 20))
                target_hosts = step.get("target_hosts") or []
                if not target_hosts:
                    logger.warning(
                        "instance_status: step %s target_hosts is empty or not a list: %s", step, target_hosts
                    )
                    continue
                for sub_step in target_hosts[0].get("sub_steps", []):
                    log.extend(["{}{}{}".format("-" * 20, sub_step["node_name"], "-" * 20), sub_step["log"]])
                    # 如果ex_data里面有值，则在日志里加上它
                    if sub_step["ex_data"]:
                        log.append(str(sub_step["ex_data"]))
                    # TODO: 这里考虑枚举定义还是代码中直接写死?
                    if sub_step["status"] != "SUCCESS":
                        return {"log_detail": "\n".join(log)}
            return {"log_detail": "\n".join(log)}
        else:
            return {"log_detail": "未找到日志"}


@staticmethod
def _get_topo_infos(
    bk_tenant_id: str,
    bk_biz_id: int,
    target_nodes: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """获取动态拓扑信息

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        target_nodes: 目标节点列表

    Returns:
        dict[str, dict[str, Any]]: 动态拓扑信息

        Examples:
        {
            "module|1": {
                "bk_biz_id": 1,
                "node_type": "TOPO",
                "node_id": "module|1",
                "node_name": "biz1/set1/module1",

                "bk_obj_id": "module",
                "bk_inst_id": 1,
                "bk_inst_name": "module1",
                "child": []
            }
        }
    """

    topo_infos: dict[str, dict[str, Any]] = {}
    # 将目标节点按业务ID分组
    biz_id_to_topo_nodes: dict[int, list[cmdb_api.FindTopoNodePathParams]] = collections.defaultdict(list)
    for node in target_nodes:
        if "bk_biz_id" not in node:
            node_biz_id = bk_biz_id
        else:
            node_biz_id = node["bk_biz_id"]
        biz_id_to_topo_nodes[node_biz_id].append(
            cmdb_api.FindTopoNodePathParams(bk_obj_id=node["bk_obj_id"], bk_inst_id=node["bk_inst_id"])
        )

    # 获取拓扑节点信息
    for node_biz_id, bk_nodes in biz_id_to_topo_nodes.items():
        topo_paths = cmdb_api.find_topo_node_path(bk_tenant_id=bk_tenant_id, bk_biz_id=node_biz_id, bk_nodes=bk_nodes)
        for topo_path in topo_paths:
            node_id = f"{topo_path['bk_obj_id']}|{topo_path['bk_inst_id']}"
            # bk_paths 返回的是 list[list[dict]]，取第一条路径进行展示
            target_path: list[FindTopoNodePathNode] = topo_path["bk_paths"][0] if topo_path.get("bk_paths") else []
            node_path = "/".join([path["bk_inst_name"] for path in target_path])
            topo_infos[node_id] = {
                "bk_biz_id": node_biz_id,
                "node_name": f"{node_path}/{topo_path['bk_inst_name']}",
                "node_type": TargetNodeType.TOPO.value,
                "node_id": node_id,
                "bk_obj_id": topo_path["bk_obj_id"],
                "bk_inst_id": topo_path["bk_inst_id"],
                "bk_inst_name": topo_path["bk_inst_name"],
                "child": [],
            }
    return topo_infos


@staticmethod
def _get_dynamic_group_infos(
    bk_tenant_id: str,
    bk_biz_id: int,
    target_nodes: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[int, list[str]]]:
    """获取动态分组信息

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        target_nodes: 目标节点列表

    Returns:
        dict[str, dict[str, Any]]: 动态分组信息

        Examples:
        {
            "dynamic_group|XXXXXXXX": {
                "node_name": "dynamic_group1",
                "node_type": "DYNAMIC_GROUP",
                "node_id": "dynamic_group|XXXXXXXX",
                "bk_biz_id": 1,
                "bk_obj_id": "host",
                "bk_inst_id": "XXXXXXXX",
                "bk_inst_name": "dynamic_group1",
                "child": [],
            }
        }
    """
    dynamic_group_infos: dict[str, dict[str, Any]] = {}

    # 主机ID到动态分组ID的映射
    host_to_dynamic_group_ids: dict[int, list[str]] = {}
    for topo_node in target_nodes:
        dynamic_group_id = topo_node["bk_inst_id"]

        # 获取动态分组配置
        dynamic_group = cmdb_api.get_dynamic_group(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            dynamic_group_id=dynamic_group_id,
        )

        # 执行动态分组，获取主机列表
        hosts = cmdb_api.execute_dynamic_group(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            dynamic_group_id=dynamic_group_id,
        )

        node_id = f"dynamic_group|{dynamic_group_id}"
        dynamic_group_infos[node_id] = {
            "node_name": dynamic_group["name"],
            "node_type": TargetNodeType.DYNAMIC_GROUP.value,
            "node_id": node_id,
            "bk_biz_id": bk_biz_id,
            "bk_obj_id": dynamic_group["bk_obj_id"],
            "bk_inst_id": dynamic_group_id,
            "bk_inst_name": dynamic_group["name"],
            "child": [],
        }

        # 构建主机ID到动态分组ID的映射
        for host in hosts:
            host_to_dynamic_group_ids[host["bk_host_id"]].append(dynamic_group_id)

    return dynamic_group_infos, host_to_dynamic_group_ids


def _process_instance_result(instance_result: SubscriptionTaskResult) -> dict[str, Any]:
    """处理实例结果

    Args:
        instance_result: 实例结果

    Returns:
        dict[str, Any]: 实例信息
    """

    instance_info = instance_result["instance_info"]
    host_info = instance_info["host"]
    service_info = instance_info.get("service")

    # 提取获取阶段日志，获取非SUCCESS的日志
    log = ""
    for step in instance_result.get("steps", []):
        if step["status"] == "SUCCESS":
            continue
        for sub_step in step["target_hosts"][0]["sub_steps"]:
            if sub_step["status"] == "SUCCESS":
                continue
            log = sub_step["log"]
            break
        if log:
            break

    # 操作类型
    action = "install"
    for step in instance_result.get("steps", []):
        if step.get("action") in ["UNINSTALL", "REMOVE_CONFIG"]:
            action = "uninstall"
        elif step.get("action") in ["INSTALL"]:
            action = "install"
        elif step.get("action") in ["PUSH_CONFIG"]:
            action = "update"

    instance: dict[str, Any] = {
        "instance_id": instance_result["instance_id"],
        "ip": host_info["bk_host_innerip"],
        "bk_cloud_id": host_info["bk_cloud_id"],
        "bk_host_id": host_info["bk_host_id"],
        "bk_host_name": host_info["bk_host_name"],
        "bk_supplier_id": host_info.get("bk_supplier_account", "0"),
        "status": instance_result["status"],
        "log": log,
        "action": action,
        "steps": {step["id"]: step["action"] for step in instance_result.get("steps", []) if step["action"]},
        "related_node_ids": [],
    }

    # 添加实例关联的拓扑节点ID
    for scope in instance_info.get("scope", []):
        if "bk_obj_id" in scope and "bk_inst_id" in scope:
            instance["related_node_ids"].append(f"{scope['bk_obj_id']}|{scope['bk_inst_id']}")

    if service_info:
        # 添加服务实例关联的模块和集群ID
        for relation in service_info.get("relations", []):
            instance["related_node_ids"].append(f"module|{relation['bk_module_id']}")
            instance["related_node_ids"].append(f"set|{relation['bk_set_id']}")

        instance.update(
            {
                "instance_name": service_info.get("name") or service_info["id"],
                "service_instance_id": service_info["id"],
                "service_template_id": service_info["service_template_id"],
                "bk_module_id": service_info["bk_module_id"],
            }
        )
    else:
        # 添加主机实例关联的模块和集群ID
        for relation in host_info.get("relations", []):
            instance["related_node_ids"].append(f"module|{relation['bk_module_id']}")
            instance["related_node_ids"].append(f"set|{relation['bk_set_id']}")

        instance.update(
            {
                "instance_name": host_info.get("bk_host_innerip") or host_info.get("bk_host_innerip_v6", ""),
                "bk_module_ids": list(
                    set(
                        [r.get("bk_module_id") for r in host_info.get("relations", []) if r.get("bk_module_id")]
                        + [
                            s["bk_inst_id"]
                            for s in instance_info.get("scope", [])
                            if s.get("bk_obj_id") == "module" and "bk_inst_id" in s
                        ]
                    )
                ),
            }
        )

    return instance


def _get_template_infos(
    bk_tenant_id: str,
    bk_biz_id: int,
    target_nodes: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """获取模板信息

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        target_nodes: 目标节点列表

    Returns:
        模板信息和集群到集群模板的映射

        Examples:
        {
            "set_template|1": {
                "node_name": "set1",
                "node_type": "SET_TEMPLATE",
                "node_id": "set_template|1",
                "template_id": 1,
                "template_name": "set1",
                "child": []
            },
            "service_template|1": {
                "node_name": "service1",
                "node_type": "SERVICE_TEMPLATE",
                "node_id": "service_template|1",
                "template_id": 1,
                "template_name": "service1",
                "child": []
            },
        }

        {
            "module|1": "service_template|1",
            "set|1": "set_template|1"
        }
    """
    set_template_ids: set[int] = set()
    service_template_ids: set[int] = set()
    for node in target_nodes:
        if node["bk_obj_id"].lower() == "set_template":
            set_template_ids.add(node["bk_inst_id"])
        elif node["bk_obj_id"].lower() == "service_template":
            service_template_ids.add(node["bk_inst_id"])

    # 获取模板信息
    set_templates = cmdb_api.list_set_template(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        set_template_ids=list(set_template_ids),
    )
    service_templates = cmdb_api.list_service_template(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        service_template_ids=list(service_template_ids),
    )
    template_infos: dict[str, dict[str, Any]] = {}
    for set_template in set_templates:
        node_id = f"set_template|{set_template.id}"
        template_infos[node_id] = {
            "node_name": set_template.name,
            "node_type": TargetNodeType.SET_TEMPLATE.value,
            "node_id": node_id,
            "template_id": set_template.id,
            "template_name": set_template.name,
            "child": [],
        }
    for service_template in service_templates:
        node_id = f"service_template|{service_template.id}"
        template_infos[node_id] = {
            "node_name": service_template.name,
            "node_type": TargetNodeType.SERVICE_TEMPLATE.value,
            "node_id": node_id,
            "template_id": service_template.id,
            "template_name": service_template.name,
            "child": [],
        }

    # 获取集群到集群模板的映射
    topo_node_to_template_id: dict[str, str] = {}
    if set_template_ids:
        _, set_infos = cmdb_api.search_set(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        for set_info in set_infos:
            if set_info.set_template_id not in set_template_ids:
                continue
            topo_node_to_template_id[f"set|{set_info.bk_set_id}"] = f"set_template|{set_info.set_template_id}"

    if service_template_ids:
        _, module_infos = cmdb_api.search_module(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        for module_info in module_infos:
            if module_info.service_template_id not in service_template_ids:
                continue
            topo_node_to_template_id[f"module|{module_info.bk_module_id}"] = (
                f"service_template|{module_info.service_template_id}"
            )

    return template_infos, topo_node_to_template_id
