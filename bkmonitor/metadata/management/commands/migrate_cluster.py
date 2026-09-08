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
from django.db import transaction

from metadata import models


class Command(BaseCommand):
    help = "迁移集群（将旧集群的流量切换到新集群）"

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", required=False, default="system", help="租户ID，默认为 system")
        parser.add_argument("--cluster_type", required=True, help="集群类型，如 elasticsearch, influxdb, kafka 等")
        parser.add_argument("--src_cluster_name", required=True, help="源集群名称（旧集群）")
        parser.add_argument("--dst_cluster_name", required=True, help="目标集群名称（新集群）")
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="确认执行迁移操作（不加此参数仅显示预览）",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        cluster_type = options.get("cluster_type")
        src_cluster_name = options.get("src_cluster_name")
        dst_cluster_name = options.get("dst_cluster_name")
        confirm = options.get("confirm")

        # 获取源集群和目标集群
        try:
            src_cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=tenant_id,
                cluster_type=cluster_type,
                cluster_name=src_cluster_name,
            )
        except models.ClusterInfo.DoesNotExist:
            raise CommandError(f"源集群不存在: {src_cluster_name}")

        try:
            dst_cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=tenant_id,
                cluster_type=cluster_type,
                cluster_name=dst_cluster_name,
            )
        except models.ClusterInfo.DoesNotExist:
            raise CommandError(f"目标集群不存在: {dst_cluster_name}")

        # 显示迁移信息
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("集群迁移预览"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write("")
        self.stdout.write("源集群（旧）:")
        self.stdout.write(f"  ID: {src_cluster.cluster_id}")
        self.stdout.write(f"  名称: {src_cluster.cluster_name}")
        self.stdout.write(f"  域名: {src_cluster.domain_name}:{src_cluster.port}")
        self.stdout.write(f"  当前标签: {src_cluster.labels if src_cluster.labels else '{}'}")
        self.stdout.write("")
        self.stdout.write("目标集群（新）:")
        self.stdout.write(f"  ID: {dst_cluster.cluster_id}")
        self.stdout.write(f"  名称: {dst_cluster.cluster_name}")
        self.stdout.write(f"  域名: {dst_cluster.domain_name}:{dst_cluster.port}")
        self.stdout.write(f"  当前标签: {dst_cluster.labels if dst_cluster.labels else '{}'}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("操作内容:"))
        self.stdout.write("  1. 将源集群的 labels 复制到目标集群")
        self.stdout.write("  2. 清空源集群的 labels（停止接收新流量）")
        self.stdout.write("")

        # 如果没有 --confirm 参数，仅显示预览
        if not confirm:
            self.stdout.write(self.style.WARNING("=" * 80))
            self.stdout.write(self.style.WARNING("这是预览模式，未执行实际操作"))
            self.stdout.write(self.style.WARNING("如需执行，请添加 --confirm 参数"))
            self.stdout.write(self.style.WARNING("=" * 80))
            return

        # 执行迁移
        try:
            with transaction.atomic():
                # 复制源集群的 labels 到目标集群
                dst_cluster.labels = src_cluster.labels.copy() if src_cluster.labels else {}
                dst_cluster.save()

                # 清空源集群的 labels
                src_cluster.labels = {}
                src_cluster.save()

                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("=" * 80))
                self.stdout.write(self.style.SUCCESS("✓ 迁移成功！"))
                self.stdout.write(self.style.SUCCESS("=" * 80))
                self.stdout.write("")
                self.stdout.write(f"目标集群新标签: {dst_cluster.labels}")
                self.stdout.write(f"源集群新标签: {src_cluster.labels}")
                self.stdout.write("")

        except Exception as e:
            raise CommandError(f"迁移失败: {str(e)}")
