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
from scripts.offshore_migration.import_offshore_data.import_utils import ImportIDMapper
from scripts.offshore_migration.export_offshore_data.export_utils import EXPORT_ORDER, safe_json_loads
from scripts.offshore_migration.import_offshore_data.importers import IMPORTER_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigImporter:
    def __init__(self, export_file: str, config_file: str|None = None, config_dict: dict|None = None):
        """
        初始化导入器
        
        Args:
            export_file: 导出文件路径
            config_file: 配置文件路径
            config_dict: 配置字典
        """
        # 加载导出文件
        self.export_data = self._load_export_file(export_file)
        
        # 加载配置
        if config_dict:
            self.config = config_dict
        elif config_file:
            self.config = self._load_config(config_file)
        else:
            self.config = self._get_default_config()
        
        # 初始化组件
        self.adapter_manager = ImportAdapterManager(self.config)
        self.id_mapper = ImportIDMapper()
        
        # 从导出文件的 metadata 初始化 ID 映射表
        if "metadata" in self.export_data:
            self.id_mapper.from_dict(self.export_data["metadata"])
        
        # 导入统计
        self.import_summary = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0
        }
    
    def _load_export_file(self, export_file: str) -> dict:
        """
        加载导出文件
        """
        if not os.path.exists(export_file):
            raise FileNotFoundError(f"导出文件不存在: {export_file}")
        
        with open(export_file, 'r', encoding='utf-8') as f:
            data = safe_json_loads(f.read())
        
        # 验证文件格式
        if not self._validate_export_file(data):
            raise ValueError("导出文件格式不正确")
        
        return data
    
    def _validate_export_file(self, data: dict) -> bool:
        """
        验证导出文件格式
        """
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
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.endswith(('.yaml', '.yml')):
                return yaml.safe_load(f)
            return json.load(f)
    
    def _get_default_config(self) -> dict:
        """
        获取默认配置
        """
        return {
            "import": {
                "resources": [],
                "conflict_strategy": "skip",
                "validate": True,
            },
            "adapters": {
                "biz_id_mapping": {"mapping": {}},
                "user_mapping": {"strategy": "keep"},
            }
        }
    
    def import_all(self) -> dict:
        """
        执行完整导入
        
        Returns:
            导入结果摘要
        """
        logger.info("Starting import...")
        
        resources_data = self.export_data.get("resources", {})
        
        # 按照依赖顺序确定要导入的资源类型
        resources_to_import = self.config.get("import", {}).get("resources", []) or list(resources_data.keys())
        ordered_resources = [r for r in EXPORT_ORDER if r in resources_to_import]
        ordered_resources.extend([r for r in resources_to_import if r not in ordered_resources])
        
        # 遍历每一类资源，调用对应的导入器进行数据导入
        for resource_type in ordered_resources:
            if resource_type not in resources_data:
                logger.info(f"Skipping {resource_type} (not in export data)")
                continue
            
            try:
                importer_class = IMPORTER_REGISTRY.get(resource_type)
                if not importer_class:
                    logger.warning(f"No importer found for {resource_type}, skipping")
                    continue
                
                importer = importer_class(self.config, self.adapter_manager, self.id_mapper)
                data_list = resources_data[resource_type]
                
                if data_list:
                    logger.info(f"Importing {len(data_list)} {resource_type} objects...")
                    results = importer.import_all(data_list)
                    
                    # 更新统计
                    self.import_summary["total"] += len(data_list)
                    self.import_summary["success"] += len(results)
                    logger.info(f"Successfully imported {len(results)}/{len(data_list)} {resource_type} objects")
                else:
                    logger.info(f"No {resource_type} objects to import")
                    
            except Exception as e:
                logger.error(f"Failed to import {resource_type}: {e}", exc_info=True)
                self.import_summary["failed"] += len(resources_data.get(resource_type, []))
        
        logger.info("Import completed!")
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
            "id_mapping": self.id_mapper.to_dict()
        }


def main():
    parser = argparse.ArgumentParser(description="Import BK Monitor configurations")
    parser.add_argument("--export-file", "-e", required=True, help="Export file path")
    parser.add_argument("--config", "-c", help="Configuration file path")
    
    args = parser.parse_args()
    
    importer = ConfigImporter(export_file=args.export_file, config_file=args.config)
    
    # 执行导入
    summary = importer.import_all()
    
    print(f"\n✓ Import completed!")
    print(f"  Success: {summary['success']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Skipped: {summary['skipped']}")
    print(f"  Total: {summary['total']}")


if __name__ == "__main__":
    main()
