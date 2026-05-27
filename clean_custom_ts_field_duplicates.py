#!/usr/bin/env python
"""
CustomTSField数据去重脚本
按time_series_group_id、type、name三个字段作为唯一键去重
"""

import os
import sys
import django
from django.db import transaction
from django.db.models import Count, Max

# 添加项目路径到Python路径
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)

# 配置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from bkmonitor.packages.monitor_web.models.custom_report import CustomTSField


def find_duplicate_records():
    """查找重复的记录"""
    # 按三个字段分组，统计重复数量
    duplicates = (
        CustomTSField.objects.values("time_series_group_id", "type", "name")
        .annotate(count=Count("id"), max_id=Max("id"))
        .filter(count__gt=1)
    )

    return list(duplicates)


def get_duplicate_details(group_id, field_type, field_name):
    """获取指定组合的重复记录详情"""
    return CustomTSField.objects.filter(time_series_group_id=group_id, type=field_type, name=field_name).order_by(
        "-update_time", "-create_time"
    )


def remove_duplicates():
    """删除重复记录，保留最新的记录"""
    print("开始查找CustomTSField中的重复记录...")

    duplicates = find_duplicate_records()

    if not duplicates:
        print("未发现重复记录")
        return

    print(f"发现 {len(duplicates)} 组重复记录")

    total_deleted = 0

    with transaction.atomic():
        for dup in duplicates:
            group_id = dup["time_series_group_id"]
            field_type = dup["type"]
            field_name = dup["name"]
            count = dup["count"]

            print(f"\n处理重复组: time_series_group_id={group_id}, type={field_type}, name={field_name}")
            print(f"  重复数量: {count}")

            # 获取所有重复记录
            records = get_duplicate_details(group_id, field_type, field_name)

            # 保留最新的记录（按update_time和create_time排序）
            records_to_keep = records.first()
            records_to_delete = records.exclude(id=records_to_keep.id)

            print(f"  保留记录ID: {records_to_keep.id} (最新记录)")
            print(f"  删除记录数量: {records_to_delete.count()}")

            # 显示要删除的记录详情
            for record in records_to_delete:
                print(f"    删除记录ID: {record.id}, 创建时间: {record.create_time}, 更新时间: {record.update_time}")

            # 确认删除
            confirm = input("  确认删除这些记录？(y/N): ")
            if confirm.lower() == "y":
                deleted_count = records_to_delete.delete()[0]
                total_deleted += deleted_count
                print(f"  已删除 {deleted_count} 条记录")
            else:
                print("  跳过该组重复记录")

    print(f"\n清理完成，总共删除了 {total_deleted} 条重复记录")


def preview_duplicates():
    """预览重复记录，不执行删除操作"""
    print("预览CustomTSField中的重复记录...")

    duplicates = find_duplicate_records()

    if not duplicates:
        print("未发现重复记录")
        return

    print(f"发现 {len(duplicates)} 组重复记录:")

    for i, dup in enumerate(duplicates, 1):
        group_id = dup["time_series_group_id"]
        field_type = dup["type"]
        field_name = dup["name"]
        count = dup["count"]

        print(f"\n{i}. time_series_group_id={group_id}, type={field_type}, name={field_name}")
        print(f"   重复数量: {count}")

        # 显示重复记录详情
        records = get_duplicate_details(group_id, field_type, field_name)
        for j, record in enumerate(records, 1):
            print(
                f"     {j}. ID: {record.id}, 描述: {record.description}, "
                f"创建: {record.create_time}, 更新: {record.update_time}"
            )


def main():
    """主函数"""
    print("CustomTSField数据去重工具")
    print("=" * 50)

    # 首先预览重复记录
    preview_duplicates()

    # 询问是否执行删除
    print("\n" + "=" * 50)
    choice = input("是否执行删除操作？(y/N): ")

    if choice.lower() == "y":
        remove_duplicates()
    else:
        print("已取消删除操作")


if __name__ == "__main__":
    main()
