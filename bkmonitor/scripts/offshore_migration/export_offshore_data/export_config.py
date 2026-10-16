"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
"""

import argparse
import json
import logging
import os
from datetime import datetime

import yaml

# 设置 Django 环境
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from scripts.offshore_migration.export_offshore_data.export_adapters import AdapterManager
from scripts.offshore_migration.export_offshore_data.export_utils import EXPORT_ORDER, safe_json_dumps
from scripts.offshore_migration.export_offshore_data.exporters import EXPORTER_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ConfigExporter:
    def __init__(self, config_file: str | None = None, config_dict: dict | None = None):
        if config_dict:
            self.config = config_dict
        elif config_file:
            self.config = self._load_config(config_file)
        else:
            self.config = self._get_default_config()

        self.adapter_manager = AdapterManager(self.config)
        self.export_results = {}

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
        获取默认配置（完整导出模式）
        """
        return {
            "export": {
                "bk_biz_ids": [],  # 空列表表示导出所有业务
                "output_dir": "./export_data",
            },
            "adapters": {
                "domain_mapping": {},
                "biz_id_mapping": {"auto": True},
                "user_mapping": {"strategy": "keep"},
                "sensitive_fields_config": {"strategy": "keep"},
            },
        }

    def export_all(self) -> dict:
        logger.info("=" * 80)
        logger.info("开始迁移导出...")
        logger.info("=" * 80)

        # 完整导出：导出所有已注册的资源类型，按依赖顺序
        all_resources = list(EXPORTER_REGISTRY.keys())
        ordered_resources = [r for r in EXPORT_ORDER if r in all_resources]
        ordered_resources.extend([r for r in all_resources if r not in ordered_resources])

        logger.info(f"准备导出 {len(ordered_resources)} 种资源类型")
        logger.info("=" * 80)

        resources_data = {}
        export_summary = {"total": 0, "success": 0, "failed": 0}

        # 遍历每一类资源，调用对应的导出器进行数据导出
        for resource_type in ordered_resources:
            try:
                exporter_class = EXPORTER_REGISTRY[resource_type]
                exporter = exporter_class(self.config, self.adapter_manager)
                data = exporter.export(self.config.get("export", {}).get("bk_biz_ids"))
                if data:
                    resources_data[resource_type] = data
                    export_summary["total"] += len(data)
                    export_summary["success"] += 1
                    logger.info(f"[{resource_type}] 导出 {len(data)} 个对象")
                else:
                    logger.info(f"[{resource_type}] 无数据")
            except Exception as e:
                export_summary["failed"] += 1
                logger.error(f"[{resource_type}] 导出失败: {e}", exc_info=True)

        self.export_results = {
            "version": "1.0",
            "export_time": int(datetime.now().timestamp()),
            "source_env": os.environ.get("BKAPP_DEPLOY_ENV", "unknown"),
            "resources": resources_data,
            "metadata": {
                "export_summary": {resource_type: len(data) for resource_type, data in resources_data.items()},
                "adapters_applied": self.adapter_manager.get_applied_adapter_names(),
            },
        }

        # 输出导出汇总
        logger.info("=" * 80)
        logger.info("导出完成汇总:")
        logger.info(f"  ✓ 成功: {export_summary['success']} 种资源类型")
        logger.info(f"  ⊙ 总计: {export_summary['total']} 个对象")
        if export_summary["failed"] > 0:
            logger.warning(f"  ✗ 失败: {export_summary['failed']} 种资源类型")
        logger.info("=" * 80)

        return self.export_results

    def save_to_file(self, output_file: str | None = None) -> str:
        """
        将导出的结果以json字符串的形式保存在文件

        Args:
            output_file: 输出文件路径，如果为None则自动生成

        Returns:
            保存的文件路径
        """
        # 确保输出目录存在
        if output_file is None:
            output_dir = self.config.get("export", {}).get("output_dir", "./export_data")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"monitor_config_export_{timestamp}.json")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(safe_json_dumps(self.export_results, indent=2, ensure_ascii=False))

        logger.info(f"Export results saved to {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description="Export BK Monitor configurations")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--biz-ids", "-b", help="Business IDs (comma-separated)")
    parser.add_argument("--resources", "-r", help="Resource types (comma-separated)")
    parser.add_argument("--list-resources", action="store_true")

    args = parser.parse_args()

    if args.list_resources:
        print("Available resource types:")
        for resource_type in EXPORTER_REGISTRY.keys():
            print(f"  - {resource_type}")
        return

    exporter = ConfigExporter(config_file=args.config)

    if args.biz_ids:
        exporter.config["export"]["bk_biz_ids"] = [int(bid.strip()) for bid in args.biz_ids.split(",")]

    if args.resources:
        exporter.config["export"]["resources"] = [r.strip() for r in args.resources.split(",")]

    # 将数据导出并保存到文件
    exporter.export_all()
    output_file = exporter.save_to_file(args.output)
    print(f"\n✓ Export completed! Output: {output_file}")


if __name__ == "__main__":
    main()
