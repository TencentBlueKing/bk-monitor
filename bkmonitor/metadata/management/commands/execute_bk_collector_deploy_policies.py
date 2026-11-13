"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Callable

from django.core.management import BaseCommand, CommandError

from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models.bk_collector import BkCollectorDeployPolicy, BkCollectorDeployScene

SCENES = [
    BkCollectorDeployScene.APM_PLATFORM,
    BkCollectorDeployScene.APM_APPLICATION,
    BkCollectorDeployScene.CUSTOM_LOG,
    BkCollectorDeployScene.CUSTOM_REPORT,
    BkCollectorDeployScene.PING_SERVER,
]


class Command(BaseCommand):
    """立即下发 bk-collector 在节点管理 V3 的部署策略

    默认只重新执行已有策略：适用于目标主机已在策略范围内、collector 后装或重装的场景。

    --refresh 全量刷新：同步执行各场景的定时下发逻辑，按当前 Proxy 列表与 CUSTOM_REPORT_DEFAULT_PROXY_IP
    重新计算目标主机，新建或更新策略，最后对本轮未变化的策略再执行一次。
    运维把新主机设为 Proxy（或填入全局配置）并装好 V3 bk-collector 后执行，不必等待定时任务。

    策略执行分批进行（含刷新中新建、更新策略后的立即执行）：每执行 --batch_size 条等待 --batch_interval 秒。
    节点管理按主机逐个渲染子配置，单步超时 60 秒，短时间触发大量策略会导致渲染超时、子配置未下发。
    """

    help = "execute bk-collector nodeman v3 deploy policies immediately, use --refresh to recalculate all scenes"

    DEFAULT_BATCH_SIZE = 10
    DEFAULT_BATCH_INTERVAL = 30

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default=None, help="only handle this tenant")
        parser.add_argument(
            "--scene",
            type=str,
            default=None,
            choices=SCENES,
            help="only handle this scene",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="recalculate target hosts and create/update policies of all scenes before executing",
        )
        parser.add_argument(
            "--batch_size",
            type=int,
            default=self.DEFAULT_BATCH_SIZE,
            help=f"execute policies in batches of this size, 0 means no batching (default {self.DEFAULT_BATCH_SIZE})",
        )
        parser.add_argument(
            "--batch_interval",
            type=float,
            default=self.DEFAULT_BATCH_INTERVAL,
            help=f"seconds to wait between batches (default {self.DEFAULT_BATCH_INTERVAL})",
        )

    def handle(self, *args, **options):
        if not BkCollectorDeployPolicy.is_enabled():
            raise CommandError(
                "ENABLE_BK_COLLECTOR_NODEMAN_V3 is disabled, bk-collector is still delivered by NodeMan V2"
            )

        bk_tenant_id = options.get("bk_tenant_id")
        scene = options.get("scene")
        batch_size = options.get("batch_size")
        batch_interval = options.get("batch_interval")
        if batch_size < 0 or batch_interval < 0:
            raise CommandError("--batch_size and --batch_interval must not be negative")

        with BkCollectorDeployPolicy.execute_in_batches(batch_size, batch_interval, on_wait=self._on_batch_wait):
            self._handle(bk_tenant_id=bk_tenant_id, scene=scene, refresh=options.get("refresh"))

    def _on_batch_wait(self, executed: int, interval: float):
        self.stdout.write(f"[batch] {executed} policies executed, wait {interval:g}s before next batch")

    def _handle(self, bk_tenant_id: str | None, scene: str | None, refresh: bool):
        policies = BkCollectorDeployPolicy.objects.all()
        if bk_tenant_id:
            policies = policies.filter(bk_tenant_id=bk_tenant_id)
        if scene:
            policies = policies.filter(scene=scene)

        # 刷新前记录各策略的最近一次执行，刷新中已执行过的策略不再重复执行
        last_workflow_ids = dict(policies.values_list("id", "last_workflow_id"))

        if refresh:
            origin_tenant_id = get_local_tenant_id()
            try:
                self._refresh(bk_tenant_id=bk_tenant_id, scene=scene)
            finally:
                # 刷新过程会切换线程内租户，结束后恢复，避免影响同进程后续逻辑
                set_local_tenant_id(origin_tenant_id)

        success, failed = 0, 0
        for policy in policies.filter(deploy_policy_id__isnull=False).order_by("id"):
            if policy.id in last_workflow_ids and policy.last_workflow_id != last_workflow_ids[policy.id]:
                self.stdout.write(f"[refreshed] {policy.bk_tenant_id} {policy.policy_name}({policy.deploy_policy_id})")
                continue
            if policy.id not in last_workflow_ids and policy.last_workflow_id:
                # 本轮刷新新建的策略，创建时已执行
                self.stdout.write(f"[created] {policy.bk_tenant_id} {policy.policy_name}({policy.deploy_policy_id})")
                continue
            try:
                workflow_id = policy.execute()
                success += 1
                self.stdout.write(
                    f"[ok] {policy.bk_tenant_id} {policy.policy_name}({policy.deploy_policy_id}) -> {workflow_id}"
                )
            except Exception as e:  # noqa
                failed += 1
                self.stderr.write(
                    f"[failed] {policy.bk_tenant_id} {policy.policy_name}({policy.deploy_policy_id}): {e}"
                )

        missing = list(policies.filter(deploy_policy_id__isnull=True).values_list("scene", "resource_key"))
        for missing_scene, resource_key in missing:
            self.stderr.write(f"[missing] {missing_scene} {resource_key}: no deploy policy, check worker logs")

        self.stdout.write(
            f"executed bk-collector deploy policies, success: {success}, failed: {failed}, missing: {len(missing)}"
        )

    def _refresh(self, bk_tenant_id: str | None, scene: str | None):
        """同步执行各场景的定时下发逻辑，与 celery 定时任务走同一套代码"""
        from apm.core.platform_config import PlatformConfig
        from apm.models import ApmApplication
        from apm.task.tasks import refresh_apm_application_config
        from metadata.models import CustomReportSubscription, LogGroup, LogSubscriptionConfig
        from metadata.task.ping_server import refresh_ping_conf

        tenant_ids = [bk_tenant_id] if bk_tenant_id else [tenant["id"] for tenant in api.bk_login.list_tenant()]

        def need(target_scene: str) -> bool:
            return scene is None or scene == target_scene

        for tenant_id in tenant_ids:
            set_local_tenant_id(tenant_id)

            if need(BkCollectorDeployScene.APM_PLATFORM):
                self._run(f"apm_platform {tenant_id}", PlatformConfig.refresh, tenant_id)

            if need(BkCollectorDeployScene.APM_APPLICATION):
                applications = ApmApplication.objects.filter(bk_tenant_id=tenant_id, is_enabled=True)
                for bk_biz_id, app_name in applications.values_list("bk_biz_id", "app_name"):
                    self._run(
                        f"apm_application {tenant_id} {bk_biz_id}-{app_name}",
                        refresh_apm_application_config,
                        bk_biz_id,
                        app_name,
                        skip_k8s=True,
                    )

            if need(BkCollectorDeployScene.CUSTOM_LOG):
                log_groups = LogGroup.objects.filter(
                    bk_tenant_id=tenant_id, is_enable=True, is_need_deploy_collector_config=True
                )
                for log_group in log_groups:
                    self._run(
                        f"custom_log {tenant_id} {log_group.bk_biz_id}-{log_group.log_group_name}",
                        LogSubscriptionConfig.refresh,
                        log_group,
                    )

            if need(BkCollectorDeployScene.CUSTOM_REPORT):
                self._run(
                    f"custom_report {tenant_id}",
                    CustomReportSubscription.refresh_collector_custom_conf,
                    bk_tenant_id=tenant_id,
                    deploy_targets=("node_man",),
                )

        if need(BkCollectorDeployScene.PING_SERVER):
            # 指定租户时只遍历该租户的主机，避免改动其他租户的 PingServer 策略
            set_local_tenant_id(bk_tenant_id or DEFAULT_TENANT_ID)
            self._run(
                f"ping_server {bk_tenant_id or 'all tenants'}",
                refresh_ping_conf,
                BkCollectorDeployPolicy.PLUGIN_NAME,
                bk_tenant_id=bk_tenant_id,
            )

    def _run(self, name: str, func: Callable, *args, **kwargs):
        # 各场景内部会自行记录单个资源的异常，这里只兜底整体失败，最终结果以策略记录为准
        try:
            func(*args, **kwargs)
            self.stdout.write(f"[refresh] {name} done")
        except Exception as e:  # noqa
            self.stderr.write(f"[refresh failed] {name}: {e}")
