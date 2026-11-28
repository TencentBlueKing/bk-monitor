"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
"""

import argparse
import json
import logging
import os

import yaml

# 设置 Django 环境
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from scripts.offshore_migration.import_offshore_data.import_adapters import ImportAdapterManager
from scripts.offshore_migration.export_offshore_data.export_utils import EXPORT_ORDER, safe_json_loads
from scripts.offshore_migration.import_offshore_data.importers import IMPORTER_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # 强制重新配置，避免重复添加 handler
)
logger = logging.getLogger(__name__)
logger.propagate = False  # 禁用日志传播，避免重复输出


class ConfigImporter:
    def __init__(self, export_file: str, config_file: str | None = None, config_dict: dict | None = None):
        """
        初始化导入器

        Args:
            export_file: 导出文件路径
            config_file: 配置文件路径
            config_dict: 配置字典
        """
        # 加载导出文件
        self.export_data = self._load_export_file(export_file)

        # 加载配置(字典或者yaml文件)
        if config_dict:
            self.config = config_dict
        elif config_file:
            self.config = self._load_config(config_file)
        else:
            self.config = self._get_default_config()

        # 初始化组件
        self.adapter_manager = ImportAdapterManager(self.config)

        # 导入统计
        self.import_summary = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "by_resource": {},  # 按资源类型统计
        }

    def _load_export_file(self, export_file: str) -> dict:
        """
        加载导出文件
        """
        if not os.path.exists(export_file):
            raise FileNotFoundError(f"导出文件不存在: {export_file}")

        with open(export_file, encoding="utf-8") as f:
            data = safe_json_loads(f.read())

        # 验证文件格式
        if not self._validate_export_file(data):
            raise ValueError("导出文件格式不正确")

        return data

    def _validate_export_file(self, data: dict) -> bool:
        """
        验证导出文件格式
        """
        # 生成json文件的顶层结构
        required_fields = ["version", "export_time", "resources", "metadata"]
        for field in required_fields:
            if field not in data:
                logger.error(f"导出文件缺少必需字段: {field}")
                return False

        if not isinstance(data.get("resources"), dict):
            logger.error("导出文件的 resources 字段格式不正确")
            return False

        return True

    def _load_config(self, config_file: str) -> dict:
        """
        解析yaml配置文件为字典
        """
        with open(config_file, encoding="utf-8") as f:
            if config_file.endswith((".yaml", ".yml")):
                return yaml.safe_load(f)
            return json.load(f)

    def _get_default_config(self) -> dict:
        """
        获取默认配置（完整迁移模式）
        """
        return {
            "import": {
                "conflict_strategy": "skip",  # skip, overwrite, rename
                "validate": True,
            },
            "adapters": {
                "biz_id_mapping": {"mapping": {}},
                "user_mapping": {"strategy": "keep"},
            },
        }

    def import_all(self) -> dict:
        """
        执行完整导入

        Returns:
            导入结果摘要
        """
        logger.info("=" * 80)
        logger.info("开始迁移导入...")
        logger.info("=" * 80)

        resources_data = self.export_data.get("resources", {})

        # 完整迁移：导入所有导出的资源，按依赖顺序
        ordered_resources = [r for r in EXPORT_ORDER if r in resources_data]
        ordered_resources.extend([r for r in resources_data.keys() if r not in ordered_resources])

        total_objects = sum(len(resources_data.get(r, [])) for r in ordered_resources)
        logger.info(f"待导入: {len(ordered_resources)} 种资源类型, 共 {total_objects} 个对象")
        logger.info("=" * 80)

        # 遍历每一类资源，调用对应的导入器进行数据导入
        for resource_type in ordered_resources:
            if resource_type not in resources_data:
                continue

            try:
                importer_class = IMPORTER_REGISTRY.get(resource_type)
                if not importer_class:
                    logger.warning(f"未找到 {resource_type} 的导入器，跳过")
                    continue

                importer = importer_class(self.config.get("import", {}), self.adapter_manager)
                data_list = resources_data[resource_type]

                if not data_list:
                    continue

                # 导入资源
                results = importer.import_all(data_list)

                # 计算本次导入的统计
                success_count = len(results)
                total_count = len(data_list)
                failed_count = total_count - success_count

                # 更新总体统计
                self.import_summary["total"] += total_count
                self.import_summary["success"] += success_count
                self.import_summary["failed"] += failed_count

                # 更新按资源类型的统计
                self.import_summary["by_resource"][resource_type] = {
                    "success": success_count,
                    "failed": failed_count,
                    "total": total_count,
                }

                # 输出本资源类型的导入结果
                if failed_count > 0:
                    logger.warning(f"[{resource_type}] 完成: {success_count}/{total_count} 成功, {failed_count} 失败")
                else:
                    logger.info(f"[{resource_type}] 完成: {success_count}/{total_count} 全部成功")

            except Exception as e:
                resource_count = len(resources_data.get(resource_type, []))
                logger.error(f"[{resource_type}] 导入失败: {e}", exc_info=True)
                self.import_summary["failed"] += resource_count
                self.import_summary["total"] += resource_count
                self.import_summary["by_resource"][resource_type] = {
                    "success": 0,
                    "failed": resource_count,
                    "total": resource_count,
                }

        # 输出最终汇总
        logger.info("=" * 80)
        logger.info("导入完成汇总:")
        logger.info(f"  ✓ 成功: {self.import_summary['success']}")
        logger.info(f"  ✗ 失败: {self.import_summary['failed']}")
        logger.info(f"  ⊙ 总计: {self.import_summary['total']}")
        if self.import_summary["total"] > 0:
            success_rate = self.import_summary["success"] * 100 // self.import_summary["total"]
            logger.info(f"  成功率: {success_rate}%")
        logger.info("=" * 80)

        # 如果有失败，输出失败资源类型详情
        if self.import_summary["failed"] > 0:
            logger.warning("失败资源类型详情:")
            for resource_type, stats in self.import_summary["by_resource"].items():
                if stats["failed"] > 0:
                    logger.warning(f"  - {resource_type}: {stats['failed']}/{stats['total']} 失败")

        return self.get_import_summary()

    def get_import_summary(self) -> dict:
        """
        获取导入摘要
        """
        return {
            "success": self.import_summary["success"],
            "failed": self.import_summary["failed"],
            "skipped": self.import_summary["skipped"],
            "total": self.import_summary["total"],
            "by_resource": self.import_summary["by_resource"],
        }


def main():
    parser = argparse.ArgumentParser(description="Import BK Monitor configurations")
    parser.add_argument("--export-file", "-e", required=True, help="Export file path")
    parser.add_argument("--config", "-c", help="Configuration file path")

    args = parser.parse_args()

    importer = ConfigImporter(export_file=args.export_file, config_file=args.config)

    # 执行导入
    summary = importer.import_all()

    print(f"\n{'=' * 60}")
    print("✓ Import completed!")
    print(f"{'=' * 60}")
    print("\nOverall Summary:")
    print(f"  Total: {summary['total']}")
    print(f"  Success: {summary['success']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Skipped: {summary['skipped']}")

    if summary.get("by_resource"):
        print("\nDetailed Summary by Resource Type:")
        for resource_type, stats in summary["by_resource"].items():
            print(f"  {resource_type}:")
            print(f"    - Success: {stats['success']}/{stats['total']}")
            print(f"    - Failed: {stats['failed']}")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
