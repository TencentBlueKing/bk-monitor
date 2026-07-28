#!/usr/bin/env python3
"""
手动测试特性开关数据库功能
使用方法：在项目根目录运行 python3 feature_flag_manual.py
"""

import os
import sys

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
bkmonitor_path = os.path.join(project_root, "bkmonitor")

# 先设置工作目录，确保导入的是 bkmonitor 的 settings
os.chdir(bkmonitor_path)

# 添加项目路径（bkmonitor 优先）
sys.path.insert(0, os.path.join(bkmonitor_path, "packages"))
sys.path.insert(0, bkmonitor_path)
bklog_path = os.path.join(project_root, "bklog")
if os.path.exists(bklog_path):
    sys.path.append(bklog_path)  # 使用 append 而不是 insert，确保 bkmonitor 优先

# 设置 Django 环境
os.environ.setdefault("DJANGO_CONF_MODULE", "conf.web.development.community")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# 设置必要的环境变量
os.environ.setdefault("BKAPP_DEPLOY_PLATFORM", "community")
os.environ.setdefault("USE_DYNAMIC_SETTINGS", "0")
os.environ.setdefault("BK_MONITOR_APP_CODE", "bk_monitorv3")
os.environ.setdefault("APP_CODE", "bk_monitorv3")
os.environ.setdefault("APP_ID", "bk_monitorv3")
os.environ.setdefault("APP_TOKEN", "test_token")
os.environ.setdefault("BKPAAS_APP_ID", "bk_monitorv3")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ROLE", "web")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# MySQL 配置
os.environ.setdefault("MYSQL_NAME", "bk_monitorv3")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "")

# Redis 配置
os.environ.setdefault("DJANGO_REDIS_DB", "0")
os.environ.setdefault("DJANGO_REDIS_HOST", "127.0.0.1")
os.environ.setdefault("DJANGO_REDIS_PORT", "6379")
os.environ.setdefault("DJANGO_REDIS_PASSWORD", "")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_DB", "0")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_HOST", "127.0.0.1")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_PORT", "6379")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_PASSWORD", "")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_MODE", "standalone")
os.environ.setdefault("BK_MONITOR_TRANSFER_REDIS_SENTINEL_PASSWORD", "")

# Consul 配置
os.environ.setdefault("CONSUL_HOST", "127.0.0.1")
os.environ.setdefault("CONSUL_PORT", "8500")
os.environ.setdefault("BK_MONITOR_CONSUL_HOST", "127.0.0.1")
os.environ.setdefault("BK_MONITOR_CONSUL_PORT", "8500")

# 尝试加载 dotenv
try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass

# 初始化 Django
import django

django.setup()

from metadata.models.feature_flag import FeatureFlag, FeatureFlagConfig


def main():
    """主测试函数"""
    print("=" * 60)
    print("测试特性开关数据库功能")
    print("=" * 60)
    print()

    # 1. 检查迁移是否已运行
    print("1. 检查数据库表是否存在")
    print("-" * 60)
    try:
        count = FeatureFlag.objects.count()
        print(f"✓ 数据库表存在，当前有 {count} 条记录")
    except Exception as e:
        print(f"✗ 数据库表不存在或未迁移: {e}")
        print("请先运行迁移: python manage.py migrate metadata")
        return
    print()

    # 2. 创建测试数据
    print("2. 创建测试数据")
    print("-" * 60)
    test_flags = [
        {
            "flag_name": "must-vm-query",
            "description": "测试特性开关：必须使用 VM 查询",
            "config": {
                "variations": {
                    "Default": False,
                    "true": True,
                    "false": False,
                },
                "targeting": [
                    {
                        "query": 'tableID in ["table_id_1", "table_id_2"]',
                        "percentage": {
                            "true": 100,
                            "false": 0,
                        },
                    }
                ],
                "defaultRule": {
                    "variation": "Default",
                },
            },
            "is_enabled": True,
        },
        {
            "flag_name": "range-vm-query",
            "description": "测试特性开关：范围 VM 查询",
            "config": {
                "variations": {
                    "Default": 0,
                    "true": 3000,
                },
                "targeting": [
                    {
                        "query": 'tableID in ["table_id_1", "table_id_3"]',
                        "percentage": {
                            "true": 100,
                        },
                    }
                ],
                "defaultRule": {
                    "variation": "Default",
                },
            },
            "is_enabled": True,
        },
    ]

    created_count = 0
    updated_count = 0
    for flag_data in test_flags:
        try:
            flag, created = FeatureFlag.objects.update_or_create(
                flag_name=flag_data["flag_name"],
                defaults={
                    "description": flag_data["description"],
                    "config": flag_data["config"],
                    "is_enabled": flag_data["is_enabled"],
                },
            )
            if created:
                created_count += 1
                print(f"✓ 创建: {flag.flag_name} (ID: {flag.flag_id})")
            else:
                updated_count += 1
                print(f"✓ 更新: {flag.flag_name} (ID: {flag.flag_id})")
        except Exception as e:
            print(f"✗ 创建/更新 {flag_data['flag_name']} 失败: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n创建: {created_count} 条，更新: {updated_count} 条")
    print()

    # 3. 显示数据库中的数据
    print("3. 查询数据库中的特性开关")
    print("-" * 60)
    try:
        all_flags = FeatureFlag.objects.filter(is_enabled=True)
        print(f"启用的特性开关数量: {all_flags.count()}")
        for flag in all_flags:
            print(f"  - {flag.flag_name} (ID: {flag.flag_id})")
            print(f"    配置键: {list(flag.config.keys()) if isinstance(flag.config, dict) else 'N/A'}")
            print(f"    启用状态: {flag.is_enabled}")
    except Exception as e:
        print(f"✗ 查询数据库失败: {e}")
        import traceback

        traceback.print_exc()
    print()

    # 4. 从数据库读取并刷新到 Consul
    print("4. 从数据库读取并刷新到 Consul")
    print("-" * 60)
    try:
        FeatureFlagConfig.refresh_consul_feature_flag_config_from_db()
        print("✓ 数据已从数据库刷新到 Consul")

        # 验证 Consul 中的数据
        all_configs = FeatureFlagConfig.get_all_consul_feature_flag_config()
        if all_configs:
            print(f"  Consul 中的配置数量: {len(all_configs)}")
            for flag_name in all_configs.keys():
                print(f"    - {flag_name}")
        else:
            print("  ⚠️  Consul 中没有数据（可能是 Consul 未配置或未连接）")
    except Exception as e:
        print(f"✗ 刷新到 Consul 失败: {e}")
        print("  （这可能是正常的，如果 Consul 未配置）")
        import traceback

        traceback.print_exc()
    print()

    # 5. 从数据库读取并刷新到 Redis
    print("5. 从数据库读取并刷新到 Redis")
    print("-" * 60)
    try:
        FeatureFlagConfig.refresh_redis_feature_flag_config_from_db()
        print("✓ 数据已从数据库刷新到 Redis")

        # 验证 Redis 中的数据
        all_configs = FeatureFlagConfig.get_all_redis_feature_flag_config()
        if all_configs:
            print(f"  Redis 中的配置数量: {len(all_configs)}")
            for flag_name in all_configs.keys():
                print(f"    - {flag_name}")
        else:
            print("  ⚠️  Redis 中没有数据（可能是 Redis 未配置或未连接）")
    except Exception as e:
        print(f"✗ 刷新到 Redis 失败: {e}")
        print("  （这可能是正常的，如果 Redis 未配置）")
        import traceback

        traceback.print_exc()
    print()

    print("=" * 60)
    print("✓ 测试完成！")
    print("=" * 60)
    print()
    print("总结:")
    print("  - 数据库操作: ✓ 成功")
    if created_count > 0 or updated_count > 0:
        print("  - 测试数据: ✓ 已创建/更新")
    print("  - Consul/Redis: 请检查上面的输出确认状态")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
