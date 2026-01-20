"""
配置导出示例脚本
使用方法: python manage.py shell < scripts/example_usage.py
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

try:
    import django
    django.setup()
except Exception as e:
    print(f"Failed to setup Django: {e}")
    sys.exit(1)

from scripts.offshore_migration.export_config import ConfigExporter


def example_1_export_all():
    print("\n" + "=" * 60)
    print("示例 1: 导出所有业务的所有资源")
    print("=" * 60)
    
    config = {
        "export": {
            "bk_biz_ids": [],
            "resources": [],
            "output_dir": "./export_data"
        }
    }
    
    exporter = ConfigExporter(config_dict=config)
    result = exporter.export_all()
    output_file = exporter.save_to_file()
    
    print(f"\n✓ 导出完成！输出文件: {output_file}")
    print(f"\n📊 导出统计:")
    for resource_type, data in result.get("resources", {}).items():
        print(f"  - {resource_type}: {len(data)} 条记录")


def main():
    print("\n" + "=" * 60)
    print("🚀 监控配置导出示例")
    print("=" * 60)
    
    try:
        choice = input("请输入选项 (1): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    
    if choice == "1" or not choice:
        example_1_export_all()
    else:
        print(f"无效的选项: {choice}")


if __name__ == "__main__":
    main()
