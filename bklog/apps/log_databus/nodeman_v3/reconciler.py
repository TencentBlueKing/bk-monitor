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
    NodeManV3DispatchStatus,
    NodeManV3OperationStatus,
    NodeManV3OperationType,
    NodeManV3ResultState,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.log_databus.nodeman_v3.exceptions import (
    NodeManV3CapabilityBlocked,
    NodeManV3UnknownResultError,
)
from apps.log_databus.nodeman_v3.identity import build_policy_name, build_resource_key
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3Operation,
    NodeManV3Workflow,
)
from apps.log_databus.nodeman_v3.policy import build_policy_payload, calculate_fingerprint
from apps.log_databus.nodeman_v3.versions import resolve_plugin_version
from apps.utils.log import logger


class CollectorPolicyReconciler:
    """
    采集项期望态收敛。

    采集项的下发、编辑、停用、删除在 V3 下统一表达为「改写部署策略的期望态 + 触发一次收敛」：
    节点管理的收敛器会 diff 该策略名下已存在的子配置与期望值，按需 apply 或按文件名精确删除
    （internal/backend/dpmgr/analyzer.go:232-248），删除后触发插件 reload 而不卸载进程。
    因此停用/删除采集项不需要我们自己调 remove_subconfig，也就不存在「本地删了、收敛器又补回来」
    的复活竞态。

    注意收敛不是周期性的：deploy_policy/execute 建的是一次性 trigger
    （NodeMan internal/backend/manager/deploypolicy_manager.go:31 用 trigger.CategoryOnce），
    节点管理不会自己重算策略。目标范围变化后的自动收敛需要日志侧定时触发（BKL-3）。
    """

    def __init__(self, collector_config: CollectorConfig):
        self.collector_config = collector_config
        self.bk_biz_id = collector_config.bk_biz_id

    # ------------------------------------------------------------------
    # binding
    # ------------------------------------------------------------------
    def get_or_create_binding(self) -> NodeManV3Binding:
        client = get_client(self.bk_biz_id)
        binding, created = NodeManV3Binding.objects.get_or_create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(self.collector_config.collector_config_id),
            bk_biz_id=self.bk_biz_id,
            bk_tenant_id=client.tenant_id,
            defaults={
                "collector_config_id": self.collector_config.collector_config_id,
                "policy_name": build_policy_name(self.collector_config.collector_config_id),
            },
        )
        if created:
            logger.info(
                f"[nodeman_v3] created binding for collector_config_id={self.collector_config.collector_config_id}"
            )
        return binding

    def recover_deploy_policy_id(self, binding: NodeManV3Binding) -> int | None:
        """
        本地 binding 丢了 deploy_policy_id 时按策略名找回。

        节点管理没有 deploy_policy 删除接口，策略一旦创建就长期存在。若不先找回就直接 create，
        同一个采集项会挂上两个策略，两个策略各自生成一份子配置（文件名含策略 ID，互不覆盖），
        同一份日志会被采两遍。
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
    # 期望态
    # ------------------------------------------------------------------
    def build_desired_payload(self, steps: list[dict], target_nodes: list[dict] | None) -> dict:
        client = get_client(self.bk_biz_id)
        plugin_version = resolve_plugin_version(
            client, plugin_name=LogPluginInfo.NAME, configured_version=LogPluginInfo.VERSION
        )
        return build_policy_payload(
            collector_config_id=self.collector_config.collector_config_id,
            bk_biz_id=self.bk_biz_id,
            target_node_type=self.collector_config.target_node_type,
            target_nodes=target_nodes,
            steps=steps,
            plugin_version=plugin_version,
            description=self.collector_config.description or "",
        )

    # ------------------------------------------------------------------
    # 收敛
    # ------------------------------------------------------------------
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

        返回 None 表示期望态无变化、本次未触发下发。
        """
        if target_nodes is None:
            target_nodes = self.collector_config.target_nodes

        payload = self.build_desired_payload(steps, target_nodes)
        fingerprint = calculate_fingerprint(payload)

        binding = self.get_or_create_binding()
        if not force and binding.policy_fingerprint == fingerprint and binding.deploy_policy_id:
            logger.info(
                f"[nodeman_v3] desired state unchanged, skip reconcile, "
                f"collector_config_id={self.collector_config.collector_config_id}"
            )
            return None

        with transaction.atomic():
            binding = NodeManV3Binding.objects.select_for_update().get(pk=binding.pk)
            binding.generation += 1
            binding.is_enabled = bool(payload["scopes"])
            binding.save(update_fields=["generation", "is_enabled", "updated_at", "updated_by"])

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

            # 指纹只在成功派发后写入：失败时保持旧指纹，下次保存采集项仍会重试收敛，
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
