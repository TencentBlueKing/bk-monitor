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

from django.db import transaction
from django.utils.translation import gettext as _

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.client import get_client
from apps.log_databus.nodeman_v3.constants import (
    COLLECTOR_CONFIG_ID_NOT_APPLICABLE,
    NodeManV3DispatchStatus,
    NodeManV3OperationStatus,
    NodeManV3OperationType,
    NodeManV3ResultState,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
    RESOURCE_TYPE_COLLECTOR_PLUGIN,
)
from apps.log_databus.nodeman_v3.exceptions import (
    NodeManV3CapabilityBlocked,
    NodeManV3UnknownResultError,
)
from apps.log_databus.nodeman_v3.identity import (
    build_plugin_policy_name,
    build_plugin_resource_key,
    build_policy_name,
    build_resource_key,
)
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3Operation,
    NodeManV3Workflow,
)
from apps.log_databus.nodeman_v3.policy import (
    build_plugin_install_payload,
    build_policy_payload,
    calculate_fingerprint,
    merge_scopes,
)
from apps.log_databus.nodeman_v3.versions import resolve_plugin_version
from apps.utils.log import logger


class PolicyReconcilerBase:
    """
    部署策略期望态收敛的公共部分：binding 找回、派发、状态记账。

    日志侧维护两类策略，收敛动作完全一样（create 或 update 期望态 + execute 一次），
    差别只在期望态怎么算，所以把派发抽在这里：

    - 采集项子配置策略（CollectorPolicyReconciler）
    - 业务级采集器安装策略（CollectorPluginReconciler）

    注意收敛不是周期性的：deploy_policy/execute 建的是一次性 trigger
    （NodeMan internal/backend/manager/deploypolicy_manager.go:31 用 trigger.CategoryOnce），
    节点管理不会自己重算策略。目标范围变化后的自动收敛需要日志侧定时触发（BKL-3）。
    """

    resource_type: str = ""

    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id

    # ------------------------------------------------------------------
    # binding
    # ------------------------------------------------------------------
    def _binding_lookup(self) -> dict:
        raise NotImplementedError

    def _binding_defaults(self) -> dict:
        raise NotImplementedError

    def get_or_create_binding(self) -> NodeManV3Binding:
        client = get_client(self.bk_biz_id)
        binding, created = NodeManV3Binding.objects.get_or_create(
            bk_tenant_id=client.tenant_id,
            defaults=self._binding_defaults(),
            **self._binding_lookup(),
        )
        if created:
            logger.info(f"[nodeman_v3] created binding {binding.resource_type}:{binding.resource_key}")
        return binding

    def recover_deploy_policy_id(self, binding: NodeManV3Binding) -> int | None:
        """
        本地 binding 丢了 deploy_policy_id 时按策略名找回。

        节点管理没有 deploy_policy 删除接口，策略一旦创建就长期存在。若不先找回就直接 create，
        同一个资源会挂上两个策略。对采集项来说两个策略各自生成一份子配置
        （文件名含策略 ID，互不覆盖），同一份日志会被采两遍。
        """
        client = get_client(self.bk_biz_id)
        # deploy_policy/list 的分页参数是 {count, start, limit}，与插件包列表的 {offset, limit} 不同
        payload = {
            "page": {"count": False, "start": 0, "limit": 10},
            "exact_include_conditions": {"deploy_policy_name": [binding.policy_name]},
        }
        items = (client.list_deploy_policies(payload) or {}).get("items") or []
        for item in items:
            name = (item.get("meta") or {}).get("name") or item.get("name")
            if name == binding.policy_name and item.get("deploy_policy_id"):
                return int(item["deploy_policy_id"])
        return None

    # ------------------------------------------------------------------
    # 收敛
    # ------------------------------------------------------------------
    def _apply_desired_state(
        self,
        payload: dict,
        *,
        operation_type: str,
        force: bool = False,
    ) -> NodeManV3Operation | None:
        """
        把一条策略的期望态推到节点管理并触发一次收敛。

        返回 None 表示期望态无变化、本次未触发下发。
        """
        fingerprint = calculate_fingerprint(payload)

        binding = self.get_or_create_binding()
        if not force and binding.policy_fingerprint == fingerprint and binding.deploy_policy_id:
            logger.info(
                f"[nodeman_v3] desired state unchanged, skip reconcile, "
                f"binding={binding.resource_type}:{binding.resource_key}"
            )
            return None

        with transaction.atomic():
            binding = NodeManV3Binding.objects.select_for_update().get(pk=binding.pk)
            binding.generation += 1
            binding.is_enabled = bool(payload["scopes"])
            binding.desired_scopes = payload["scopes"]
            binding.save(update_fields=["generation", "is_enabled", "desired_scopes", "updated_at", "updated_by"])

            operation = NodeManV3Operation.objects.create(
                binding=binding,
                operation_type=operation_type,
                generation=binding.generation,
                status=NodeManV3OperationStatus.PENDING,
                request_summary={
                    "spec_types": [spec["type"] for spec in payload["specs"]],
                    "scope_types": [scope["type"] for scope in payload["scopes"]],
                    "fingerprint": fingerprint,
                },
            )

        self._dispatch(binding, operation, payload, fingerprint)
        return operation

    def _dispatch(
        self,
        binding: NodeManV3Binding,
        operation: NodeManV3Operation,
        payload: dict,
        fingerprint: str,
    ) -> None:
        client = get_client(self.bk_biz_id, operation_id=str(operation.id))

        operation.status = NodeManV3OperationStatus.DISPATCHING
        operation.save(update_fields=["status", "updated_at", "updated_by"])

        try:
            deploy_policy_id = binding.deploy_policy_id or self.recover_deploy_policy_id(binding)
            if deploy_policy_id:
                client.update_deploy_policy(
                    {
                        "deploy_policies": [
                            {
                                "deploy_policy_id": deploy_policy_id,
                                "meta": {
                                    "name": payload["name"],
                                    "description": payload["description"],
                                },
                                "specs": payload["specs"],
                                "scopes": payload["scopes"],
                                "enabled": payload["enabled"],
                            }
                        ],
                        "fields": {"meta": True, "scopes": True, "specs": True, "enabled": True},
                    }
                )
            else:
                created = client.create_deploy_policy(payload)
                deploy_policy_id = int(created.get("deploy_policy_id") or 0)
                if not deploy_policy_id:
                    raise NodeManV3UnknownResultError(
                        NodeManV3UnknownResultError.MESSAGE.format(err=_("创建部署策略未返回 deploy_policy_id"))
                    )

            binding.deploy_policy_id = deploy_policy_id
            binding.save(update_fields=["deploy_policy_id", "updated_at", "updated_by"])

            executed = client.execute_deploy_policy(deploy_policy_id)
            trigger_id = executed.get("trigger_id") or ""
            if not trigger_id:
                raise NodeManV3UnknownResultError(
                    NodeManV3UnknownResultError.MESSAGE.format(err=_("执行部署策略未返回 trigger_id"))
                )

            NodeManV3Workflow.objects.create(
                operation=operation,
                trigger_id=trigger_id,
                dispatch_status=NodeManV3DispatchStatus.SUBMITTED,
                normalized_status=NodeManV3OperationStatus.PENDING,
            )

            # 指纹只在成功派发后写入：失败时保持旧指纹，下次保存或定时收敛仍会重试，
            # 否则会出现「期望态记成已下发、实际一台机器都没生效」的静默丢失
            binding.policy_fingerprint = fingerprint
            binding.save(update_fields=["policy_fingerprint", "updated_at", "updated_by"])

            operation.status = NodeManV3OperationStatus.RUNNING
            operation.save(update_fields=["status", "updated_at", "updated_by"])
        except NodeManV3UnknownResultError as err:
            # 指纹此时仍是旧值，下一次保存或定时收敛会重新推一遍期望态；
            # create 会先按策略名反查、update 是整体覆盖，因此重放不会产生第二个策略或重复子配置。
            # 注意调用方可能处于事务中（start/stop 带 @transaction.atomic），这条记录会随之回滚，
            # 写结果未知的持久证据以出站审计日志为准。
            operation.status = NodeManV3OperationStatus.UNKNOWN
            operation.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            operation.error_message = str(err)
            operation.save(update_fields=["status", "result_state", "error_message", "updated_at", "updated_by"])
            raise
        except NodeManV3CapabilityBlocked as err:
            operation.status = NodeManV3OperationStatus.FAILED
            operation.result_state = NodeManV3ResultState.UNSUPPORTED
            operation.error_message = str(err)
            operation.save(update_fields=["status", "result_state", "error_message", "updated_at", "updated_by"])
            raise
        except Exception as err:  # pylint: disable=broad-except
            operation.status = NodeManV3OperationStatus.FAILED
            operation.error_message = str(err)
            operation.save(update_fields=["status", "error_message", "updated_at", "updated_by"])
            raise


class CollectorPluginReconciler(PolicyReconcilerBase):
    """
    业务级采集器安装策略收敛。

    一个业务一条策略，只声明 specify_plugin，不声明任何子配置。拆出来的原因见
    policy.build_plugin_install_payload：把 specify_plugin 放进采集项策略会让同插件的全部策略
    进同一个冲突闭包，导致同机后建的采集项被静默剔除并删掉已生效子配置。

    目标范围是本业务所有启用中采集项 scope 条目的并集，取自各 binding 的 desired_scopes，
    而不是回头重算 CollectorConfig：重算依赖调用方有没有先改 is_active / target_nodes，
    顺序稍有差别就会算出与实际下发不一致的并集。
    """

    resource_type = RESOURCE_TYPE_COLLECTOR_PLUGIN

    def __init__(self, bk_biz_id: int, plugin_name: str = LogPluginInfo.NAME):
        super().__init__(bk_biz_id)
        self.plugin_name = plugin_name

    def _binding_lookup(self) -> dict:
        return {
            "resource_type": RESOURCE_TYPE_COLLECTOR_PLUGIN,
            "resource_key": build_plugin_resource_key(self.plugin_name),
            "bk_biz_id": self.bk_biz_id,
        }

    def _binding_defaults(self) -> dict:
        return {
            "collector_config_id": COLLECTOR_CONFIG_ID_NOT_APPLICABLE,
            "policy_name": build_plugin_policy_name(self.bk_biz_id, self.plugin_name),
        }

    def collect_desired_scopes(self) -> list[dict]:
        bindings = NodeManV3Binding.objects.filter(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            bk_biz_id=self.bk_biz_id,
            is_enabled=True,
        ).order_by("collector_config_id")
        return merge_scopes([binding.desired_scopes or [] for binding in bindings])

    def build_desired_payload(self) -> dict:
        client = get_client(self.bk_biz_id)
        plugin_version = resolve_plugin_version(
            client, plugin_name=self.plugin_name, configured_version=LogPluginInfo.VERSION
        )
        return build_plugin_install_payload(
            bk_biz_id=self.bk_biz_id,
            plugin_version=plugin_version,
            scopes=self.collect_desired_scopes(),
            plugin_name=self.plugin_name,
        )

    def reconcile(self, force: bool = False) -> NodeManV3Operation | None:
        return self._apply_desired_state(
            self.build_desired_payload(),
            operation_type=NodeManV3OperationType.PLUGIN_RECONCILE,
            force=force,
        )


class CollectorPolicyReconciler(PolicyReconcilerBase):
    """
    采集项子配置策略收敛。

    采集项的下发、编辑、停用、删除在 V3 下统一表达为「改写部署策略的期望态 + 触发一次收敛」：
    节点管理的收敛器会 diff 该策略名下已存在的子配置与期望值，按需 apply 或按文件名精确删除
    （internal/backend/dpmgr/analyze_specific_plugin_sub_config_template.go:228-245），
    删除后触发插件 reload 而不卸载进程。因此停用/删除采集项不需要我们自己调 remove_subconfig，
    也就不存在「本地删了、收敛器又补回来」的复活竞态。
    """

    resource_type = RESOURCE_TYPE_COLLECTOR_CONFIG

    def __init__(self, collector_config: CollectorConfig):
        super().__init__(collector_config.bk_biz_id)
        self.collector_config = collector_config

    def _binding_lookup(self) -> dict:
        return {
            "resource_type": RESOURCE_TYPE_COLLECTOR_CONFIG,
            "resource_key": build_resource_key(self.collector_config.collector_config_id),
            "bk_biz_id": self.bk_biz_id,
        }

    def _binding_defaults(self) -> dict:
        return {
            "collector_config_id": self.collector_config.collector_config_id,
            "policy_name": build_policy_name(self.collector_config.collector_config_id),
        }

    def build_desired_payload(self, steps: list[dict], target_nodes: list[dict] | None) -> dict:
        return build_policy_payload(
            collector_config_id=self.collector_config.collector_config_id,
            bk_biz_id=self.bk_biz_id,
            target_node_type=self.collector_config.target_node_type,
            target_nodes=target_nodes,
            steps=steps,
            description=self.collector_config.description or "",
        )

    def reconcile(
        self,
        steps: list[dict],
        *,
        target_nodes: list[dict] | None = None,
        operation_type: str = NodeManV3OperationType.RECONCILE,
        force: bool = False,
    ) -> NodeManV3Operation | None:
        """
        把采集项的期望态推到节点管理并触发一次收敛。

        返回 None 表示采集项策略的期望态无变化、本次未触发子配置下发；
        安装策略是否下发与返回值无关，它有自己的期望态与指纹。
        """
        if target_nodes is None:
            target_nodes = self.collector_config.target_nodes

        payload = self.build_desired_payload(steps, target_nodes)
        fingerprint = calculate_fingerprint(payload)

        binding = self.get_or_create_binding()
        collector_changed = force or binding.policy_fingerprint != fingerprint or not binding.deploy_policy_id

        # 先把本采集项的期望范围落库，安装策略的并集才能算上这一次的变化。
        # 这一步刻意放在派发之前：desired_scopes 允许领先于实际下发，
        # 多装一台机器的采集器是无害的（specify_plugin 只装不卸），
        # 而漏装会让子配置无处落地——节点管理只对插件进程 running 的主机下发子配置。
        if binding.desired_scopes != payload["scopes"]:
            binding.desired_scopes = payload["scopes"]
            binding.is_enabled = bool(payload["scopes"])
            binding.save(update_fields=["desired_scopes", "is_enabled", "updated_at", "updated_by"])

        # 收敛顺序取决于范围是扩还是收，两个方向的失败后果不对称。
        stopping = not payload["scopes"]

        if not stopping:
            # 扩容方向先收敛安装策略：子配置只会下发到插件进程已 running 的主机
            # （analyze_specific_plugin_sub_config_template.go:113-117），采集器没装上就整轮落空。
            # 这里失败要整体失败，不能把子配置策略照常推下去记成「已下发」。
            # 两次 execute 都是异步的，顺序只能缩短而不能消除「插件还没装好」的窗口，
            # 兜底靠 BKL-3 的定时收敛。
            CollectorPluginReconciler(self.bk_biz_id).reconcile()

        operation = None
        if collector_changed:
            operation = self._apply_desired_state(payload, operation_type=operation_type, force=True)
        else:
            logger.info(
                f"[nodeman_v3] desired state unchanged, skip reconcile, "
                f"collector_config_id={self.collector_config.collector_config_id}"
            )

        if stopping:
            # 停用方向反过来：先摘子配置，再收窄安装范围。
            # 安装范围收窄纯粹是记账——specify_plugin 只装不升不卸，主机移出范围不会触发任何
            # 主机侧动作（analyzer.go:139-170 只遍历 params.Targets），只影响后续版本管理。
            # 所以它失败不能回滚已经成功的子配置清理，否则采集项显示已停用却还在继续采集。
            # 残留的记账偏差由下一次收敛（保存采集项或 BKL-3 定时任务）自行修正。
            try:
                CollectorPluginReconciler(self.bk_biz_id).reconcile()
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    f"[nodeman_v3] failed to shrink install policy scope after stopping "
                    f"collector_config_id={self.collector_config.collector_config_id}, "
                    f"sub configs are already removed, will retry on next reconcile"
                )

        return operation
