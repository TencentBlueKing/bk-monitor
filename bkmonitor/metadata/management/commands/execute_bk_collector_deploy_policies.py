"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management import BaseCommand

from metadata.models.bk_collector import BkCollectorDeployPolicy


class Command(BaseCommand):
    """立即执行 bk-collector 在节点管理 V3 的部署策略

    节点管理每小时会自动执行全部启用的策略；运维在 Proxy / 直连区域主机上新装好 bk-collector 后，
    可执行本命令立即补发子配置，不必等待下一轮。
    """

    help = "execute bk-collector nodeman v3 deploy policies immediately"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default=None, help="only execute policies of this tenant")
        parser.add_argument("--scene", type=str, default=None, help="only execute policies of this scene")

    def handle(self, *args, **options):
        policies = BkCollectorDeployPolicy.objects.filter(deploy_policy_id__isnull=False)
        if options.get("bk_tenant_id"):
            policies = policies.filter(bk_tenant_id=options["bk_tenant_id"])
        if options.get("scene"):
            policies = policies.filter(scene=options["scene"])

        success, failed = 0, 0
        for policy in policies.order_by("id"):
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

        self.stdout.write(f"executed bk-collector deploy policies, success: {success}, failed: {failed}")
