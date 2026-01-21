#!/usr/bin/env python
"""
构造测试数据用于迁移脚本耗时测试
生成 100 万个 CustomTSField（metric 类型）

使用方式:
1. 独立运行: python create_test_data.py
2. manage shell 环境:
   - python manage.py shell
   - >>> from create_test_data import main; main()
   - 或者: python manage.py shell < create_test_data.py
"""

import logging
import random
import time
from datetime import datetime

from django.db import transaction

from monitor_web.models import CustomTSTable, CustomTSField, CustomTSGroupingRule
from metadata.models import ResultTableField

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 配置参数
TOTAL_METRICS = 1_000_000  # 总指标数
GROUPS_COUNT = 10  # 分组数量
TABLES_PER_GROUP = 1  # 每个分组对应的表数量
DIMENSIONS_PER_GROUP = 30  # 每个分组的维度数量

# 测试 group_id 起始值（从 1000000 开始，便于区分测试数据）
TEST_GROUP_ID_START = 1000000

# 生成器常量
TENANT_IDS = ["tenant_1", "tenant_2", "tenant_3"]
SCOPE_NAMES = ["default", "scope_a", "scope_b", "scope_c"]
AGGREGATE_METHODS = ["sum", "avg", "max", "min", "count"]
COMMON_DIMENSIONS = ["host", "module", "service", "cluster", "pod"]


def generate_metric_name(group_id: int, index: int) -> str:
    """生成指标名称"""
    patterns = [
        f"g{group_id}_count_{index}",
        f"g{group_id}_latency_{index}",
        f"g{group_id}_throughput_{index}",
        f"g{group_id}_error_rate_{index}",
        f"g{group_id}_duration_{index}",
    ]
    return f"custom_{random.choice(patterns)}"


def generate_metric_config() -> dict:
    """生成指标配置"""
    return {
        "alias": f"指标描述_{random.randint(1, 1000)}",
        "unit": random.choice(["", "ms", "KB", "MB", "%", "count"]),
        "hidden": random.choice([True, False]),
        "aggregate_method": random.choice(AGGREGATE_METHODS),
        "function": random.choice(["", "rate", "delta"]),
        "interval": random.choice([10, 30, 60, 300]),
        "disabled": random.choice([True, False]),
        "dimensions": random.sample(COMMON_DIMENSIONS, random.randint(1, 3)),
        "common": random.choice([True, False]),
        "label": random.sample(SCOPE_NAMES, random.randint(1, 2)),
    }


def generate_dimension_config() -> dict:
    """生成维度配置"""
    return {
        "alias": f"维度描述_{random.randint(1, 100)}",
        "common": random.choice([True, False]),
        "hidden": random.choice([True, False]),
    }


def create_custom_ts_tables(group_ids: list) -> dict:
    """创建 CustomTSTable 数据"""
    logger.info("[1/4] 开始创建 CustomTSTable 数据...")
    start_time = time.time()

    tables_to_create = []
    group_to_tables = {}
    table_index = 0

    for group_id in group_ids:
        group_tables = []
        for _ in range(TABLES_PER_GROUP):
            table_id = f"rt_test_{table_index:06d}"
            tables_to_create.append(
                CustomTSTable(
                    bk_tenant_id=random.choice(TENANT_IDS),
                    time_series_group_id=group_id,
                    bk_data_id=2000000 + table_index,
                    table_id=table_id,
                    name=f"test_table_{table_index}",
                    scenario="custom_test",
                )
            )
            group_tables.append(table_id)
            table_index += 1
        group_to_tables[group_id] = group_tables

    # 批量创建
    if tables_to_create:
        CustomTSTable.objects.bulk_create(tables_to_create, batch_size=500)

    cost = time.time() - start_time
    logger.info(f"[1/4] CustomTSTable 创建完成: {len(tables_to_create)} 条, 耗时 {cost:.2f}s")
    return group_to_tables


def create_result_table_fields(group_to_tables: dict) -> dict:
    """创建 ResultTableField 数据"""
    logger.info("[2/4] 开始创建 ResultTableField 数据...")
    start_time = time.time()

    fields_to_create = []
    field_index = 0

    # 为每个表的每个维度创建字段
    for group_id, table_ids in group_to_tables.items():
        for table_id in table_ids:
            for dim in COMMON_DIMENSIONS:
                fields_to_create.append(
                    ResultTableField(
                        bk_tenant_id=random.choice(TENANT_IDS),
                        table_id=table_id,
                        field_name=dim,
                        field_type="string",
                        tag="dimension",
                        creator="system",
                        last_modify_user="system",
                        is_config_by_user=True,
                        description=f"{dim} 描述",
                    )
                )
                field_index += 1

    # 批量创建
    if fields_to_create:
        ResultTableField.objects.bulk_create(fields_to_create, batch_size=500)

    cost = time.time() - start_time
    logger.info(f"[2/4] ResultTableField 创建完成: {len(fields_to_create)} 条, 耗时 {cost:.2f}s")
    return group_to_tables


def create_custom_ts_fields_and_dimensions(group_ids: list, group_to_tables: dict) -> dict:
    """创建 CustomTSField 数据（指标和维度）"""
    logger.info("[3/4] 开始创建 CustomTSField 数据（指标和维度）...")
    start_time = time.time()

    fields_to_create = []
    metric_index = 0
    dimension_index = 0

    # 每个分组分配的指标数量
    metrics_per_group = TOTAL_METRICS // GROUPS_COUNT
    remaining_metrics = TOTAL_METRICS % GROUPS_COUNT

    now = datetime.now()

    for i, group_id in enumerate(group_ids):
        # 创建维度字段
        for _ in range(DIMENSIONS_PER_GROUP):
            fields_to_create.append(
                CustomTSField(
                    time_series_group_id=group_id,
                    name=f"dim_custom_{dimension_index}",
                    type="dimension",
                    description=f"自定义维度_{dimension_index}",
                    config=generate_dimension_config(),
                    disabled=False,
                    create_time=now,
                    update_time=now,
                )
            )
            dimension_index += 1

        # 创建指标字段
        group_metric_count = metrics_per_group + (1 if i < remaining_metrics else 0)

        for j in range(group_metric_count):
            fields_to_create.append(
                CustomTSField(
                    time_series_group_id=group_id,
                    name=generate_metric_name(group_id, j),
                    type="metric",
                    description=f"自定义指标_{metric_index}",
                    config=generate_metric_config(),
                    disabled=True,
                    create_time=now,
                    update_time=now,
                )
            )
            metric_index += 1

            # 每 10000 条批量创建一次，避免内存溢出
            if len(fields_to_create) >= 10000:
                CustomTSField.objects.bulk_create(fields_to_create, batch_size=500)
                logger.info(f"已创建 {metric_index}/{TOTAL_METRICS} 个指标")
                fields_to_create.clear()

    # 创建剩余的字段
    if fields_to_create:
        CustomTSField.objects.bulk_create(fields_to_create, batch_size=500)

    cost = time.time() - start_time
    logger.info(f"[3/4] CustomTSField 创建完成: 指标 {metric_index} 条, 维度 {dimension_index} 条, 耗时 {cost:.2f}s")

    return {"metrics_created": metric_index, "dimensions_created": dimension_index}


def create_custom_ts_grouping_rules(group_ids: list):
    """创建 CustomTSGroupingRule 数据"""
    logger.info("[4/4] 开始创建 CustomTSGroupingRule 数据...")
    start_time = time.time()

    rules_to_create = []

    # 为每个分组创建一些规则
    for group_id in group_ids:
        for scope_name in SCOPE_NAMES:
            rules_to_create.append(
                CustomTSGroupingRule(
                    time_series_group_id=group_id,
                    name=scope_name,
                    auto_rules=[{"type": "static", "tags": {dim: "*" for dim in random.sample(COMMON_DIMENSIONS, 2)}}],
                )
            )

    if rules_to_create:
        CustomTSGroupingRule.objects.bulk_create(rules_to_create, batch_size=500)

    cost = time.time() - start_time
    logger.info(f"[4/4] CustomTSGroupingRule 创建完成: {len(rules_to_create)} 条, 耗时 {cost:.2f}s")


@transaction.atomic
def run_create():
    """执行创建数据的主函数（在 transaction 之外调用）"""
    total_start = time.time()
    logger.info("=" * 60)
    logger.info(f"开始构造测试数据 - 目标: {TOTAL_METRICS} 个指标")
    logger.info("=" * 60)

    # 生成 group_id（整数形式）
    group_ids = [TEST_GROUP_ID_START + i for i in range(GROUPS_COUNT)]
    logger.info(
        f"计划创建 {GROUPS_COUNT} 个分组（group_id 范围: {group_ids[0]}-{group_ids[-1]}），每组平均 {TOTAL_METRICS // GROUPS_COUNT} 个指标"
    )

    # 1. 创建 CustomTSTable
    group_to_tables = create_custom_ts_tables(group_ids)

    # 2. 创建 ResultTableField
    create_result_table_fields(group_to_tables)

    # 3. 创建 CustomTSField（指标和维度）
    result = create_custom_ts_fields_and_dimensions(group_ids, group_to_tables)

    # 4. 创建 CustomTSGroupingRule
    create_custom_ts_grouping_rules(group_ids)

    total_cost = time.time() - total_start

    logger.info("=" * 60)
    logger.info("测试数据构造完成!")
    logger.info(f"  - 指标总数: {result['metrics_created']}")
    logger.info(f"  - 维度总数: {result['dimensions_created']}")
    logger.info(f"  - 分组数: {GROUPS_COUNT}")
    logger.info(f"  - 表数量: {GROUPS_COUNT * TABLES_PER_GROUP}")
    logger.info(f"总耗时: {total_cost:.2f}s ({total_cost / 60:.2f} 分钟)")
    logger.info("=" * 60)


run_create()
