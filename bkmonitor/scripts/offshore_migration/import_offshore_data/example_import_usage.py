"""
监控配置导入使用示例
"""

import os
import django

# 设置 Django 环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from scripts.offshore_migration.import_offshore_data.import_config import ConfigImporter


def example_1_import_all():
    """
    示例1: 导入所有资源
    """
    print("=" * 60)
    print("示例1: 导入所有资源")
    print("=" * 60)
    
    # 创建导入器
    importer = ConfigImporter(
        export_file="export_data/monitor_config_export_20250119_155709.json",
        config_file="scripts/offshore_migration/import_config.example.yaml"
    )
    
    # 执行导入
    summary = importer.import_all()
    
    # 打印摘要
    print(f"\n导入完成!")
    print(f"  成功: {summary['success']}")
    print(f"  失败: {summary['failed']}")
    print(f"  跳过: {summary['skipped']}")
    print(f"  总计: {summary['total']}")


def example_2_import_specific_resources():
    """
    示例2: 导入指定资源类型
    """
    print("=" * 60)
    print("示例2: 导入指定资源类型")
    print("=" * 60)
    
    config = {
        "import": {
            "resources": ["strategy", "user_group"],  # 只导入策略和告警组
            "conflict_strategy": "skip"
        },
        "adapters": {
            "biz_id_mapping": {
                "mapping": {
                    "100": "200",
                    "101": "201"
                }
            },
            "user_mapping": {
                "strategy": "keep"
            }
        }
    }
    
    importer = ConfigImporter(
        export_file="export_data/monitor_config_export_20250119_155709.json",
        config_dict=config
    )
    
    summary = importer.import_all()
    print(f"\n导入完成: {summary}")


def example_3_import_with_overwrite():
    """
    示例3: 使用覆盖策略导入
    """
    print("=" * 60)
    print("示例3: 使用覆盖策略导入")
    print("=" * 60)
    
    config = {
        "import": {
            "resources": [],
            "conflict_strategy": "overwrite"  # 覆盖已存在的对象
        },
        "adapters": {
            "biz_id_mapping": {
                "mapping": {
                    "100": "200"
                }
            }
        }
    }
    
    importer = ConfigImporter(
        export_file="export_data/monitor_config_export_20250119_155709.json",
        config_dict=config
    )
    
    summary = importer.import_all()
    print(f"\n导入完成: {summary}")


if __name__ == "__main__":
    # 运行示例
    example_1_import_all()
    # example_2_import_specific_resources()
    # example_3_import_with_overwrite()
