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
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.constants import (
    NodeManV3OperationType,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.log_databus.nodeman_v3.identity import build_resource_key
from apps.log_databus.nodeman_v3.models import NodeManV3Binding
from apps.log_databus.nodeman_v3.reconciler import CollectorPolicyReconciler
from apps.utils.log import logger


class NodeManV3CollectorInstaller:
    """
    物理机采集项在 V3 下的生命周期入口。

    V2 的动作语义（create/update 订阅、switch enable/disable、run START/STOP、delete 订阅）
    在 V3 里全部折叠成同一件事：改写部署策略的期望态并触发一次收敛。这样做的原因是
    V3 没有「订阅」这个既承载配置又承载开关的对象，硬去模拟 switch 会引入两套状态源。

    停用与删除都表达为「期望态里没有任何目标」，而不是 disable 策略：节点管理执行策略时
    只捞 enabled=true 的策略（action_execute_deploy_policy.go 的查询条件带 Enabled: []bool{true}），
    被 disable 的策略不再参与收敛，已下发的子配置会永久留在主机上继续采集。
    """

    def __init__(self, collector_config: CollectorConfig):
        self.collector_config = collector_config
        self.reconciler = CollectorPolicyReconciler(collector_config)

    # ------------------------------------------------------------------
    # 期望态构造
    # ------------------------------------------------------------------
    def build_steps(self, params: dict) -> list[dict]:
        """
        复用 V2 的订阅步骤生成，六种采集场景的参数口径不做任何改动。
        """
        collector_scenario = CollectorScenario.get_instance(
            collector_scenario_id=self.collector_config.collector_scenario_id
        )
        params = dict(params or {})
        if isinstance(self.collector_config.collector_config_overlay, dict):
            params["collector_config_overlay"] = self.collector_config.collector_config_overlay

        return collector_scenario.get_subscription_steps(
            self.collector_config.bk_data_id,
            params,
            self.collector_config.collector_config_id,
            self.collector_config.data_link_id,
        )

    def _stored_params(self) -> dict:
        """
        停用/删除/重新收敛时没有入参，用采集项已保存的 params 还原期望态。
        """
        params = dict(self.collector_config.params or {})
        params.setdefault("encoding", self.collector_config.data_encoding)
        return params

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def apply(self, params: dict, force: bool = False):
        """创建或更新采集项：把最新期望态推下去。"""
        steps = self.build_steps(params)
        return self.reconciler.reconcile(steps, force=force)

    def start(self):
        """启用采集项：把目标范围恢复成采集项当前配置的目标。"""
        steps = self.build_steps(self._stored_params())
        return self.reconciler.reconcile(steps, target_nodes=self.collector_config.target_nodes)

    def stop(self):
        """
        停用采集项：清空目标范围，让收敛器按文件名精确删除本策略下发的子配置。

        删除子配置后节点管理只触发插件 reload，不会停止或卸载 bkunifylogbeat 进程，
        因此同机其它采集项不受影响。
        """
        if not self._has_deployed_policy():
            # 从未下发过的采集项没有子配置需要清理。这里必须提前返回：
            # 构造期望态需要 bk_data_id 等信息，未完成创建的采集项拿不到，
            # 会让停用与删除因为「渲染上下文缺少 dataid」直接失败
            logger.info(
                f"[nodeman_v3] no deploy policy bound, skip stop, "
                f"collector_config_id={self.collector_config.collector_config_id}"
            )
            return None

        steps = self.build_steps(self._stored_params())
        return self.reconciler.reconcile(steps, target_nodes=[], operation_type=NodeManV3OperationType.REMOVE)

    def _has_deployed_policy(self) -> bool:
        binding = NodeManV3Binding.objects.filter(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(self.collector_config.collector_config_id),
            bk_biz_id=self.collector_config.bk_biz_id,
        ).first()
        return bool(binding and binding.deploy_policy_id)

    def destroy(self):
        """
        删除采集项。

        节点管理没有提供 deploy_policy 删除接口（apigw 只暴露 create/update/execute/list），
        所以这里只能把策略清成空壳并保留：本地 binding 也一并保留，
        采集项 ID 重新出现时按策略名复用，避免同一采集项挂上多个策略造成重复采集。
        """
        return self.stop()

    def rerun(self):
        """
        重新触发一次收敛，对应 V2 的 run_subscription_task。

        期望态未变时也要强制下发：用户点「重试/重新下发」的场景本身就是要修复
        主机侧与期望态不一致，跳过就等于什么都没做。
        """
        steps = self.build_steps(self._stored_params())
        operation = self.reconciler.reconcile(steps, force=True)
        if operation is None:
            logger.warning(
                f"[nodeman_v3] rerun produced no operation, "
                f"collector_config_id={self.collector_config.collector_config_id}"
            )
        return operation

    # ------------------------------------------------------------------
    # 任务 ID
    # ------------------------------------------------------------------
    def latest_task_ids(self) -> list[str]:
        """
        返回最近一次收敛的任务标识。

        V3 的 trigger_id 是字符串，写不进 CollectorConfig.subscription_id（IntegerField），
        但可以写进 task_id_list（MultiStrSplitByCommaField 的 sub_type 默认为 str）。
        """
        binding = NodeManV3Binding.objects.filter(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(self.collector_config.collector_config_id),
            bk_biz_id=self.collector_config.bk_biz_id,
        ).first()
        if not binding:
            return []
        operation = binding.operations.order_by("-generation", "-created_at").first()
        if not operation:
            return []
        return [workflow.trigger_id for workflow in operation.workflows.all() if workflow.trigger_id]
