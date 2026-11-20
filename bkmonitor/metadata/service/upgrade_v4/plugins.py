"""复用插件迁移的字段准备逻辑，不执行旧命令的路由/Transfer 收尾。"""

from bkmonitor.utils.tenant import get_tenant_default_biz_id
from metadata import models
from metadata.management.commands.migrate_default_plugin_v4 import PLUGIN_PREFIXES, STRATEGIES
from metadata.management.commands.migrate_multi_table_plugin_v4 import Command as MultiTableCommand
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.models.vm.utils import create_bkbase_data_link
from metadata.service.upgrade_v4.common import (
    changed,
    register_source,
    require_single_tenant,
    run_batch,
    set_option,
    set_source_options,
)


def prepare_plugin(data_id, *, vm_cluster_name, bk_tenant_id="system"):
    """只准备默认表及指标/维度；返回已有命令上下文供本模块接入使用。"""
    require_single_tenant()
    context = MultiTableCommand()
    context.tenant = bk_tenant_id
    context.namespace = "bkmonitor"
    context.operator = "system"
    context.biz_id = None
    context.load_context(data_id, vm_cluster_name)
    context.biz_id = context.table.get_target_bk_biz_id()
    if not context.source.is_enable or (context.table.pk and (not context.table.is_enable or context.table.is_deleted)):
        raise ValueError("插件数据源或默认表已停用")
    if context.source.etl_config not in STRATEGIES or not context.cluster:
        raise ValueError("插件类型或目标 VM 不适用")
    if context.default_exists and context.table.schema_type != models.ResultTable.SCHEMA_TYPE_FREE:
        raise ValueError("已有默认表是固定 schema，需先处理表结构")
    # 只复用字段整理，不使用旧命令拒绝部分组件的 precheck；重入交给原身份 apply。
    context.metric_info, errors = context.collect_metric_info()
    if errors:
        raise ValueError("；".join(errors))
    context.prepare_default()
    return context


def migrate_plugins(data_ids=None, *, vm_cluster_name, bk_tenant_id="system", **route_options):
    sources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, etl_config__in=STRATEGIES, is_enable=True)
    if data_ids is not None:
        sources = sources.filter(bk_data_id__in=data_ids)
    ids = [
        source.bk_data_id for source in sources.order_by("bk_data_id") if source.data_name.startswith(PLUGIN_PREFIXES)
    ]

    def migrate(data_id):
        context = prepare_plugin(data_id, vm_cluster_name=vm_cluster_name, bk_tenant_id=bk_tenant_id)
        biz_id = context.biz_id or get_tenant_default_biz_id(bk_tenant_id)
        register_source(context.source, biz_id)
        create_bkbase_data_link(
            bk_biz_id=biz_id,
            data_source=context.source,
            monitor_table_id=context.table_id,
            storage_cluster_name=context.cluster.cluster_name,
            data_link_strategy=STRATEGIES[context.source.etl_config],
            consumer_group=compose_transfer_consumer_group(context.source),
        )
        for name in ("is_split_measurement", "enable_plugin_v4_data_link"):
            set_option(context.table_id, name, True, bk_tenant_id=bk_tenant_id)
        if context.group:
            set_source_options(context.source, context.group.get_datasource_options())
            context.group.is_split_measurement = True
            context.group.save(update_fields=["is_split_measurement"])
        result = changed(context.source, [context.table_id])
        result["spaces"] = [(space["space_type_id"], space["space_id"]) for space in context.get_route_spaces()]
        result["legacy_table_ids"] = [table.table_id for table in context.legacy_tables]
        return result

    return run_batch(ids, migrate, bk_tenant_id=bk_tenant_id, **route_options)
