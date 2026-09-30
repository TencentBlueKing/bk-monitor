"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand, CommandError

from metadata import models


class Command(BaseCommand):
    help = "查询某个业务/数据类型对应的集群"

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", required=False, default="system", help="租户ID，默认为 system")
        parser.add_argument("--cluster_type", required=True, help="集群类型，如 elasticsearch, influxdb, kafka 等")
        parser.add_argument("--bk_biz_id", required=False, type=int, help="业务ID")
        parser.add_argument("--data_type", required=False, help="数据类型，如 time_series, log, event, alert, trace")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        cluster_type = options.get("cluster_type")
        bk_biz_id = options.get("bk_biz_id")
        data_type = options.get("data_type")

        # 当两个参数都为空时,输出提示
        if not bk_biz_id and not data_type:
            self.stdout.write(self.style.WARNING("未指定业务ID和数据类型,将查询兜底集群"))
            self.stdout.write("")

        try:
            cluster = models.ClusterInfo.get_matched_cluster(
                bk_tenant_id=tenant_id,
                cluster_type=cluster_type,
                bk_biz_id=bk_biz_id,
                data_type=data_type,
            )

            # 输出结果
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self.stdout.write(self.style.SUCCESS("匹配到集群："))
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self.stdout.write(f"  集群ID: {cluster.cluster_id}")
            self.stdout.write(f"  集群名称: {cluster.cluster_name}")
            self.stdout.write(f"  显示名称: {cluster.display_name}")
            self.stdout.write(f"  集群类型: {cluster.cluster_type}")
            self.stdout.write(f"  域名: {cluster.domain_name}:{cluster.port}")
            self.stdout.write(f"  创建时间: {cluster.create_time}")
            self.stdout.write("")
            self.stdout.write("  标签配置:")
            # 输出labels
            if cluster.labels:
                biz_ids = cluster.labels.get("bk_biz_ids", [])
                data_types = cluster.labels.get("data_types", [])
                self.stdout.write(f"    业务ID: {biz_ids if biz_ids else '不限制（所有业务）'}")
                self.stdout.write(f"    数据类型: {data_types if data_types else '不限制（所有类型）'}")
            else:
                self.stdout.write("    未配置标签（兜底集群，匹配所有）")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self.stdout.write(self.style.SUCCESS("查询参数："))
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self.stdout.write(f"  租户ID: {tenant_id}")
            self.stdout.write(f"  集群类型: {cluster_type}")
            self.stdout.write(f"  业务ID: {bk_biz_id if bk_biz_id else '未指定'}")
            self.stdout.write(f"  数据类型: {data_type if data_type else '未指定'}")

        except ValueError as e:
            raise CommandError(f"查询失败: {str(e)}")
        except Exception as e:
            raise CommandError(f"发生错误: {str(e)}")
