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
    help = "为某个业务/数据类型分配集群"

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", required=False, default="system", help="租户ID，默认为 system")
        parser.add_argument("--cluster_type", required=True, help="集群类型，如 elasticsearch, influxdb, kafka 等")
        parser.add_argument("--cluster_name", required=True, help="集群名称")
        parser.add_argument(
            "--bk_biz_ids",
            required=False,
            help="业务ID列表，多个用逗号分隔，如 100,200,300。传入空字符串表示置空（不限制业务）。不传此参数表示保持原值",
        )
        parser.add_argument(
            "--data_types",
            required=False,
            help="数据类型列表，多个用逗号分隔，如 time_series,log,event。传入空字符串表示置空（不限制数据类型）。不传此参数表示保持原值",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="确认执行操作（不加此参数仅显示预览）",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        cluster_type = options.get("cluster_type")
        cluster_name = options.get("cluster_name")
        bk_biz_ids = options.get("bk_biz_ids")
        data_types = options.get("data_types")
        confirm = options.get("confirm")

        # 解析参数
        # None: 参数未传入，保持原值
        # 空字符串: 显式置空
        # 有值: 解析并覆盖
        if bk_biz_ids is None:
            biz_id_list = None  # 不修改
        elif bk_biz_ids.strip() == "":
            biz_id_list = []  # 置空
        else:
            biz_id_list = [int(x.strip()) for x in bk_biz_ids.split(",")]

        if data_types is None:
            data_type_list = None  # 不修改
        elif data_types.strip() == "":
            data_type_list = []  # 置空
        else:
            data_type_list = [x.strip() for x in data_types.split(",")]

        # 获取集群
        try:
            cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=tenant_id,
                cluster_type=cluster_type,
                cluster_name=cluster_name,
            )
        except models.ClusterInfo.DoesNotExist:
            raise CommandError(f"集群不存在: {cluster_name}")

        # 显示当前配置
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("集群标签分配预览"))
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write("")
        self.stdout.write("集群信息:")
        self.stdout.write(f"  ID: {cluster.cluster_id}")
        self.stdout.write(f"  名称: {cluster.cluster_name}")
        self.stdout.write(f"  类型: {cluster.cluster_type}")
        self.stdout.write(f"  域名: {cluster.domain_name}:{cluster.port}")
        self.stdout.write("")
        self.stdout.write("当前标签配置:")
        if cluster.labels:
            current_biz_ids = cluster.labels.get("bk_biz_ids", [])
            current_data_types = cluster.labels.get("data_types", [])
            self.stdout.write(f"  业务ID: {current_biz_ids if current_biz_ids else '不限制'}")
            self.stdout.write(f"  数据类型: {current_data_types if current_data_types else '不限制'}")
        else:
            self.stdout.write("  未配置（兜底集群）")
        self.stdout.write("")

        # 计算新的标签配置
        new_labels = self._calculate_new_labels(cluster.labels, biz_id_list, data_type_list)

        # 显示操作内容
        self.stdout.write("新标签配置:")
        self.stdout.write(f"  业务ID: {new_labels.get('bk_biz_ids', []) or '不限制'}")
        self.stdout.write(f"  数据类型: {new_labels.get('data_types', []) or '不限制'}")
        self.stdout.write("")

        # 如果没有 --confirm 参数，仅显示预览
        if not confirm:
            self.stdout.write(self.style.WARNING("=" * 80))
            self.stdout.write(self.style.WARNING("这是预览模式，未执行实际操作"))
            self.stdout.write(self.style.WARNING("如需执行，请添加 --confirm 参数"))
            self.stdout.write(self.style.WARNING("=" * 80))
            return

        # 执行分配
        try:
            with transaction.atomic():
                cluster.labels = new_labels
                cluster.save()

                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("=" * 80))
                self.stdout.write(self.style.SUCCESS("✓ 分配成功！"))
                self.stdout.write(self.style.SUCCESS("=" * 80))
                self.stdout.write("")
                self.stdout.write(f"集群 {cluster.cluster_name} 的新标签:")
                self.stdout.write(f"  业务ID: {cluster.labels.get('bk_biz_ids', []) or '不限制（所有业务）'}")
                self.stdout.write(f"  数据类型: {cluster.labels.get('data_types', []) or '不限制（所有类型）'}")
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("验证建议:"))
                self.stdout.write("  使用 query_cluster 命令验证路由是否正确")

        except Exception as e:
            raise CommandError(f"分配失败: {str(e)}")

    def _calculate_new_labels(self, current_labels, biz_id_list, data_type_list) -> dict:
        """计算新的标签配置

        参数说明:
        - None: 保持原值不变
        - []: 置空
        - [值]: 覆盖为新值
        """
        # 初始化当前标签
        if not current_labels:
            current_labels = {}

        current_biz_ids = current_labels.get("bk_biz_ids", [])
        current_data_types = current_labels.get("data_types", [])

        # 直接覆盖赋值：None表示保持原值，否则覆盖
        new_biz_ids = biz_id_list if biz_id_list is not None else current_biz_ids
        new_data_types = data_type_list if data_type_list is not None else current_data_types

        return {
            "bk_biz_ids": new_biz_ids,
            "data_types": new_data_types,
        }
