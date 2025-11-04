"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from pathlib import Path

from django.core.management import BaseCommand

from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig
from metadata.models.bcs.cluster import BCSClusterInfo


class Command(BaseCommand):
    """
    手动下发配置文件到集群的管理命令

    用法:
    python manage.py deploy_manual_config --config-file /path/to/config.conf --cluster-id cluster-123 --namespace bkmonitor-operator
    python manage.py deploy_manual_config --config-dir /path/to/configs --cluster-id cluster-123 --namespace bkmonitor-operator
    """

    def add_arguments(self, parser):
        parser.add_argument("--config-file", type=str, help="配置文件路径（单个文件）")
        parser.add_argument("--config-dir", type=str, help="配置文件目录路径（批量处理）")
        parser.add_argument("--cluster-id", type=str, required=True, help="目标集群ID")
        parser.add_argument("--namespace", type=str, required=True, help="目标命名空间")

    def handle(self, *args, **options):
        config_file = options.get("config_file")
        config_dir = options.get("config_dir")
        cluster_id = options.get("cluster_id")
        namespace = options.get("namespace")

        # 验证参数
        if not config_file and not config_dir:
            self.stdout.write(self.style.ERROR("必须指定 --config-file 或 --config-dir 参数"))
            return

        if config_file and config_dir:
            self.stdout.write(self.style.ERROR("不能同时指定 --config-file 和 --config-dir 参数"))
            return

        # 验证集群是否存在
        try:
            BCSClusterInfo.objects.get(cluster_id=cluster_id)
            self.stdout.write(f"目标集群: {cluster_id}")
        except BCSClusterInfo.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"集群 {cluster_id} 不存在"))
            return

        # 收集配置文件
        config_files = self._collect_config_files(config_file or "", config_dir or "")
        if not config_files:
            self.stdout.write(self.style.WARNING("未找到任何配置文件"))
            return

        self.stdout.write(f"找到 {len(config_files)} 个配置文件")

        # 下发配置文件
        self._deploy_configs(config_files, cluster_id, namespace)

    def _collect_config_files(self, config_file: str, config_dir: str) -> list[Path]:
        """收集配置文件"""
        config_files = []

        if config_file:
            file_path = Path(config_file)
            if file_path.exists() and file_path.is_file():
                config_files.append(file_path)
            else:
                self.stdout.write(self.style.ERROR(f"配置文件不存在: {config_file}"))
        elif config_dir:
            dir_path = Path(config_dir)
            if not dir_path.exists() or not dir_path.is_dir():
                self.stdout.write(self.style.ERROR(f"配置目录不存在: {config_dir}"))
                return config_files

            # 仅支持.conf扩展名
            for file_path in dir_path.rglob("*.conf"):
                if file_path.is_file():
                    config_files.append(file_path)

        return config_files

    def _deploy_configs(self, config_files: list[Path], cluster_id: str, namespace: str):
        """下发配置文件到K8s集群"""
        # 初始化统计信息
        stats = {"total": len(config_files), "success": 0, "failed": 0, "errors": []}

        # 读取配置文件内容
        manual_configs = {}
        for config_file in config_files:
            try:
                self.stdout.write(f"处理配置文件: {config_file}")
                with open(config_file, encoding="utf-8") as f:
                    content = f.read()

                # 去除文件后缀作为配置ID
                config_id = config_file.stem  # 使用stem属性去除后缀
                manual_configs[config_id] = content
            except Exception as e:
                error_msg = f"读取配置文件 {config_file.name} 失败: {str(e)}"
                stats["errors"].append(error_msg)
                stats["failed"] += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))

        if not manual_configs:
            self.stdout.write(self.style.WARNING("没有有效的配置文件可以下发"))
            self._print_results(stats)
            return

        # 使用哈希环下发配置
        try:
            self.stdout.write(f"开始下发 {len(manual_configs)} 个配置文件到集群 {cluster_id}")
            BkCollectorClusterConfig.deploy_to_k8s_with_hash(cluster_id, manual_configs, "manual", namespace)
            stats["success"] = len(manual_configs)
            self.stdout.write(self.style.SUCCESS(f"✓ 成功下发 {len(manual_configs)} 个配置文件到命名空间 {namespace}"))
        except Exception as e:
            error_msg = f"使用哈希环下发配置失败: {str(e)}"
            stats["errors"].append(error_msg)
            stats["failed"] = len(manual_configs)
            self.stdout.write(self.style.ERROR(f"✗ {error_msg}"))

        # 显示统计结果
        self._print_results(stats)

    def _print_results(self, stats: dict):
        """打印下发结果统计"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("配置下发结果统计")
        self.stdout.write("=" * 60)

        total = stats["total"]
        success = stats["success"]
        failed = stats["failed"]

        self.stdout.write(f"总文件数: {total}")
        self.stdout.write(self.style.SUCCESS(f"成功数: {success}"))
        self.stdout.write(self.style.ERROR(f"失败数: {failed}"))

        if stats["errors"]:
            self.stdout.write(f"\n错误详情 ({len(stats['errors'])} 个错误):")
            for i, error in enumerate(stats["errors"], 1):
                self.stdout.write(self.style.ERROR(f"  {i}. {error}"))

        if failed == 0:
            self.stdout.write(self.style.SUCCESS("\n所有配置文件下发成功！"))
        else:
            self.stdout.write(self.style.WARNING(f"\n有 {failed} 个配置文件下发失败，请检查错误信息。"))
