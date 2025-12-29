import time
import logging
from datetime import datetime
from collections import defaultdict
from django.db import transaction
from django.apps import apps

logger = logging.getLogger("metadata")


def clear_test_data():
    CustomTSTable = apps.get_model("monitor_web", "CustomTSTable")
    CustomTSField = apps.get_model("monitor_web", "CustomTSField")
    TimeSeriesMetric = apps.get_model("metadata", "TimeSeriesMetric")
    TimeSeriesScope = apps.get_model("metadata", "TimeSeriesScope")
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    with transaction.atomic():
        TimeSeriesMetric.objects.filter(group_id__gte=1000000).delete()
        TimeSeriesScope.objects.filter(group_id__gte=1000000).delete()

        CustomTSField.objects.filter(time_series_group_id__gte=1000000).delete()
        CustomTSTable.objects.filter(time_series_group_id__gte=1000000).delete()

        ResultTableField.objects.filter(table_id__regex=r"2_bkmonitor_time_series_1\d{6}\.base").delete()


def create_mock_data(num_groups=10, metrics_per_group=10, dimensions_per_group=25):
    CustomTSTable = apps.get_model("monitor_web", "CustomTSTable")
    CustomTSField = apps.get_model("monitor_web", "CustomTSField")
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    start_time = time.time()
    base_group_id = 1000000

    tables = []
    for i in range(num_groups):
        group_id = base_group_id + i
        tables.append(
            CustomTSTable(
                time_series_group_id=group_id,
                bk_data_id=100000 + i,
                bk_biz_id=2,
                bk_tenant_id="default",
                name=f"test_group_{i}",
                scenario="custom",
                table_id=f"2_bkmonitor_time_series_{group_id}.base",
                is_platform=False,
                data_label="custom_time_series",
                protocol="json",
                desc=f"Test group {i}",
                auto_discover=True,
            )
        )
    CustomTSTable.objects.bulk_create(tables, batch_size=100)

    fields = []
    dimension_names = [f"dim_{j}" for j in range(dimensions_per_group)]

    for i in range(num_groups):
        group_id = base_group_id + i

        for j in range(dimensions_per_group):
            fields.append(
                CustomTSField(
                    time_series_group_id=group_id,
                    type=CustomTSField.MetricType.DIMENSION,
                    name=dimension_names[j],
                    description=f"Dimension {j}",
                    disabled=False,
                    config={"common": True, "hidden": False},
                    create_time=datetime.now(),
                )
            )

        for j in range(metrics_per_group):
            label = []
            if j % 4 == 0:
                label = ["cpu"]
            elif j % 4 == 1:
                label = ["memory"]
            elif j % 4 == 2:
                label = ["disk"]

            num_dims_to_use = 20 + (j % 6)
            dimensions_used = dimension_names[:num_dims_to_use]

            fields.append(
                CustomTSField(
                    time_series_group_id=group_id,
                    type=CustomTSField.MetricType.METRIC,
                    name=f"metric_{j}",
                    description=f"Metric {j}",
                    disabled=j % 10 == 0,
                    config={
                        "unit": "percent" if j % 2 == 0 else "count",
                        "dimensions": dimensions_used,
                        "label": label,
                        "aggregate_method": "avg",
                    },
                    create_time=datetime.now(),
                )
            )

    CustomTSField.objects.bulk_create(fields, batch_size=500)

    rt_fields = []
    for i in range(num_groups):
        group_id = base_group_id + i
        table_id = f"2_bkmonitor_time_series_{group_id}.base"
        bk_tenant_id = "default"

        for j in range(dimensions_per_group):
            dim_name = dimension_names[j]
            rt_fields.append(
                ResultTableField(
                    table_id=table_id,
                    bk_tenant_id=bk_tenant_id,
                    field_name=dim_name,
                    field_type=ResultTableField.FIELD_TYPE_STRING,
                    description=f"维度 {dim_name} 的描述信息",
                    unit="",
                    tag=ResultTableField.FIELD_TAG_DIMENSION,
                    is_config_by_user=True,
                    default_value=None,
                    creator="system",
                    last_modify_user="system",
                    alias_name="",
                    is_disabled=False,
                )
            )

        for j in range(metrics_per_group):
            metric_name = f"metric_{j}"
            rt_fields.append(
                ResultTableField(
                    table_id=table_id,
                    bk_tenant_id=bk_tenant_id,
                    field_name=metric_name,
                    field_type=ResultTableField.FIELD_TYPE_FLOAT,
                    description=f"指标 {metric_name} 的描述信息",
                    unit="percent" if j % 2 == 0 else "count",
                    tag=ResultTableField.FIELD_TAG_METRIC,
                    is_config_by_user=True,
                    default_value=None,
                    creator="system",
                    last_modify_user="system",
                    alias_name="",
                    is_disabled=j % 10 == 0,
                )
            )

    ResultTableField.objects.bulk_create(rt_fields, batch_size=500)

    elapsed = time.time() - start_time
    logger.info(f"[数据创建] 数据创建完成，耗时: {elapsed:.2f}s")

    return num_groups, len(fields)


def get_scope_name(field, default_scope):
    labels = field.config.get("label", [])
    return labels[0] if labels else default_scope


def migrate_scope(apps, bk_tenant_id, dimension_fields, group_id, metric_fields, table_id, stats):
    """迁移 Scope 数据"""
    TimeSeriesScope = apps.get_model("metadata", "TimeSeriesScope")
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    # 收集所有配置信息到统一的数据结构
    scope_info = defaultdict(lambda: {"is_default": False, "dim_configs": {}})

    # 收集所有需要查询的维度名称
    dim_field_dict = {dim_field.name: dim_field for dim_field in dimension_fields}
    all_needed_dimension_names = set(dim_field_dict.keys()) | {
        dim for field in metric_fields for dim in field.config.get("dimensions", [])
    }

    rt_fields_dict = {
        item["field_name"]: item["description"]
        for item in ResultTableField.objects.filter(
            table_id=table_id, field_name__in=all_needed_dimension_names, bk_tenant_id=bk_tenant_id
        ).values("field_name", "description")
    }

    # 收集所有维度的配置信息
    dim_configs = {}
    for dim_name in all_needed_dimension_names:
        config = {}
        # 如果维度在 dim_field_dict 中，提取其配置
        if dim_name in dim_field_dict:
            config = {k: v for k, v in dim_field_dict[dim_name].config.items() if k in ["common", "hidden"]}
        # 添加 alias
        if description := rt_fields_dict.get(dim_name):
            config["alias"] = description

        dim_configs[dim_name] = config

    # 收集 scope 信息和维度使用情况
    for field in metric_fields:
        scope_name = get_scope_name(field, "default")

        scope_info[scope_name]["is_default"] = scope_name == "default"

        # 获取该指标使用的维度列表，并将维度配置合并进来
        for dim_name in field.config.get("dimensions", []):
            if dim_name in dim_configs:
                scope_info[scope_name]["dim_configs"][dim_name] = dim_configs[dim_name]

    # 根据收集的信息批量创建或更新所有 Scope，并配置维度
    existing_scopes = {
        scope.scope_name: scope
        for scope in TimeSeriesScope.objects.filter(group_id=group_id, scope_name__in=scope_info.keys())
    }

    scopes_to_create = []
    scopes_to_update = []

    for scope_name, info in scope_info.items():
        scope_dim_config = info["dim_configs"]

        if scope_name in existing_scopes:
            # 更新已存在的 scope
            scope_obj = existing_scopes[scope_name]
            merged_dim_config = (scope_obj.dimension_config or {}).copy()

            for dim_name, dim_config in scope_dim_config.items():
                merged_dim_config.setdefault(dim_name, {}).update(dim_config)

            if merged_dim_config != scope_obj.dimension_config:
                scope_obj.dimension_config = merged_dim_config
                scopes_to_update.append(scope_obj)
        else:
            # 创建新的 scope
            scopes_to_create.append(
                TimeSeriesScope(
                    group_id=group_id,
                    scope_name=scope_name,
                    dimension_config=scope_dim_config,
                    auto_rules=[],
                    create_from="default" if info["is_default"] else "user",
                )
            )

    # 批量创建和更新
    if scopes_to_create:
        TimeSeriesScope.objects.bulk_create(scopes_to_create, batch_size=500)
        stats["scopes_created"] += len(scopes_to_create)
    if scopes_to_update:
        TimeSeriesScope.objects.bulk_update(scopes_to_update, ["dimension_config"], batch_size=500)
        stats["scopes_updated"] += len(scopes_to_update)

    return {
        scope.scope_name: scope.id
        for scope in TimeSeriesScope.objects.filter(group_id=group_id, scope_name__in=scope_info.keys())
    }


def migrate_metric(apps, group_id, metric_fields, scope_name_to_id, table_id, stats):
    """迁移 Metric 数据"""
    TimeSeriesMetric = apps.get_model("metadata", "TimeSeriesMetric")

    # 定义指标配置字段列表
    METRIC_CONFIG_FIELDS = ["alias", "unit", "hidden", "aggregate_method", "function", "interval", "disabled"]

    # 批量查询所有已存在的指标到内存中
    existing_metrics = {
        (metric.field_scope, metric.field_name): metric for metric in TimeSeriesMetric.objects.filter(group_id=group_id)
    }

    # 处理指标字段，创建或更新 Metric
    metrics_to_create = []
    metrics_to_update = []

    for field in metric_fields:
        scope_name = get_scope_name(field, "default")
        tag_list = field.config.get("dimensions", [])

        # 构建字段配置
        field_config = {"disabled": field.disabled}
        if field.description:
            field_config["alias"] = field.description

        for key in METRIC_CONFIG_FIELDS:
            if key in field.config:
                field_config[key] = field.config[key]

        scope_id = scope_name_to_id.get(scope_name)
        existing = existing_metrics.get((scope_name, field.name))

        if existing:
            existing.scope_id = scope_id
            existing.field_config = field_config
            existing.create_time = field.create_time
            metrics_to_update.append(existing)
        else:
            metrics_to_create.append(
                TimeSeriesMetric(
                    group_id=group_id,
                    scope_id=scope_id,
                    table_id=table_id,
                    field_scope=scope_name,
                    field_name=field.name,
                    tag_list=tag_list,
                    field_config=field_config,
                    label="",
                    create_time=field.create_time,
                    last_modify_time=field.update_time,
                )
            )

    # 批量保存 Metric
    if metrics_to_create:
        TimeSeriesMetric.objects.bulk_create(metrics_to_create, batch_size=500)
        stats["metrics_created"] += len(metrics_to_create)
    if metrics_to_update:
        TimeSeriesMetric.objects.bulk_update(
            metrics_to_update, ["scope_id", "field_config", "create_time"], batch_size=500
        )
        stats["metrics_updated"] += len(metrics_to_update)


def run_migration_test():
    CustomTSTable = apps.get_model("monitor_web", "CustomTSTable")
    CustomTSField = apps.get_model("monitor_web", "CustomTSField")

    start_time = time.time()

    # 统计信息
    stats = {
        "total_groups": 0,
        "skipped_groups": 0,
        "processed_groups": 0,
        "scopes_created": 0,
        "scopes_updated": 0,
        "metrics_created": 0,
        "metrics_updated": 0,
    }

    ts_tables = CustomTSTable.objects.filter(time_series_group_id__gte=1000000).values(
        "bk_tenant_id", "time_series_group_id", "table_id"
    )
    stats["total_groups"] = ts_tables.count()

    logger.info(f"[测试迁移开始] 找到 {stats['total_groups']} 个 CustomTSTable")

    # 提前一次性获取所有 CustomTSField 到内存中
    all_custom_fields = list(CustomTSField.objects.filter(time_series_group_id__gte=1000000).order_by("id"))
    fields_by_group = defaultdict(list)
    for field in all_custom_fields:
        fields_by_group[field.time_series_group_id].append(field)

    logger.info(f"[数据加载] 已加载 {len(all_custom_fields)} 个 CustomTSField 到内存")

    for ts_table in ts_tables:
        bk_tenant_id = ts_table["bk_tenant_id"]
        group_id = ts_table["time_series_group_id"]
        table_id = ts_table["table_id"]

        try:
            # 从内存中获取字段
            custom_fields = fields_by_group.get(group_id, [])
            if not custom_fields:
                logger.warning(f"[跳过] Group {group_id} (table_id={table_id}): 没有找到字段数据")
                stats["skipped_groups"] += 1
                continue

            metric_fields = [f for f in custom_fields if f.type == CustomTSField.MetricType.METRIC]
            dimension_fields = [f for f in custom_fields if f.type == CustomTSField.MetricType.DIMENSION]

            logger.info(f"[处理中] Group {group_id} (table_id={table_id}) ")
            stats["processed_groups"] += 1

            # 迁移 Scope 和 Metric
            scope_name_to_id = migrate_scope(
                apps, bk_tenant_id, dimension_fields, group_id, metric_fields, table_id, stats
            )
            migrate_metric(apps, group_id, metric_fields, scope_name_to_id, table_id, stats)

            logger.info(f"[成功] Group {group_id} 迁移完成")

        except Exception as e:
            logger.error(f"[失败] Group {group_id} (table_id={table_id}) 迁移失败: {str(e)}", exc_info=True)
            stats["skipped_groups"] += 1

    elapsed = time.time() - start_time

    summary = (
        f"组: {stats['processed_groups']}/{stats['total_groups']} "
        f"(跳过: {stats['skipped_groups']})\n"
        f"Scope: 新建 {stats['scopes_created']}, 更新 {stats['scopes_updated']}\n"
        f"Metric: 新建 {stats['metrics_created']}, 更新 {stats['metrics_updated']}\n"
        f"耗时: {elapsed:.2f}s"
    )
    logger.info(f"[测试迁移完成] {summary}")


clear_test_data()
create_mock_data(1000, 1000, 10)
run_migration_test()
