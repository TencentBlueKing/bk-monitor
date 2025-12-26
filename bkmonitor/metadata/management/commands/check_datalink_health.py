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

from metadata import health_check


class Command(BaseCommand):
    """新链路健康检查"""

    help = "check datalink health"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, required=True, help="租户ID")
        parser.add_argument(
            "--scene", type=str, required=True, help="场景(uptimecheck/custom_metric/host/k8s/apm/custom_event/log)"
        )
        parser.add_argument("--bk_biz_id", type=int, required=True, help="业务ID")
        parser.add_argument("--bk_data_id", type=int, required=False, help="数据ID（当场景为custom_metric时需要）")
        parser.add_argument("--bcs_cluster_id", type=str, required=False, help="BCS集群ID（当场景为k8s时需要）")
        parser.add_argument("--app_name", type=str, required=False, help="应用名称（当场景为apm时需要）")

    def handle(self, *args, **options):
        """处理命令"""
        bk_tenant_id = options["bk_tenant_id"]
        scene = options["scene"]
        bk_biz_id = options["bk_biz_id"]
        bk_data_id = options.get("bk_data_id")
        bcs_cluster_id = options.get("bcs_cluster_id")
        app_name = options.get("app_name")

        msg = health_check.check_datalink_health(
            bk_tenant_id=bk_tenant_id,
            scene=scene,
            bk_biz_id=bk_biz_id,
            bk_data_id=bk_data_id,
            bcs_cluster_id=bcs_cluster_id,
            app_name=app_name,
        )

        self.stdout.write(msg)
