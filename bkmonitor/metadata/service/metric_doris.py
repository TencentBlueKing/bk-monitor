"""指标写入和窗口汇总的声明与 BKBase 配置。配置只归属发起请求的逻辑 RT。"""

from django.db import transaction

from core.drf_resource import api
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models import ClusterInfo, DataSource, DorisStorage, ResultTable, ResultTableField, ResultTableOption
from metadata.models.data_link import (
    DataBusConfig,
    DataIdConfig,
    DataLink,
    DorisStorageBindingConfig,
    MetricDorisPipeline,
    ResultTableConfig,
)
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR, DataLinkNameScene
from metadata.models.data_link.metric_options import MetricAggregateOption, MetricIngestOption, metric_fields
from metadata.models.data_link.utils import create_resource_with_random_name, find_registered_bkdata_data_id_name

INGEST = ResultTableOption.OPTION_METRIC_INGEST
AGGREGATE = ResultTableOption.OPTION_METRIC_AGGREGATE


def options_for(rt):
    return {
        r.name: r.get_value()
        for r in ResultTableOption.objects.filter(
            bk_tenant_id=rt.bk_tenant_id, table_id=rt.table_id, name__in=(INGEST, AGGREGATE)
        )
    }


def physical_ref(binding):
    db, table = binding.physical_tables["main"].split(".", 1)
    return {"kind": "DorisBinding", "id": binding.pk, "database": db, "table": table}


def binding_for(output):
    return DorisStorageBindingConfig.objects.get(
        bk_tenant_id=output.bk_tenant_id,
        namespace=output.namespace,
        data_link_name=output.data_link_name,
        bkbase_result_table_name=output.name,
    )


def get_source_option(rt):
    return MetricIngestOption.model_validate(options_for(rt)[INGEST])


def sync_fields(rt, fields):
    """只在输出启用时发布该版本的字段，保护换表期间仍在使用的旧口径。"""
    records = ResultTableField.objects.filter(bk_tenant_id=rt.bk_tenant_id, table_id=rt.table_id)
    names = [field["field_name"] for field in fields]
    records.exclude(field_name__in=[*names, "time"]).delete()
    existing = {row.field_name: row for row in records}
    for field in fields:
        name = field["field_name"]
        kind = field["field_type"]
        tag = "dimension" if field["is_dimension"] else "metric"
        if name.lower() in ("timestamp", "dteventtimestamp", "dteventtime"):
            tag = "timestamp"
        if name not in existing:
            records.create(
                bk_tenant_id=rt.bk_tenant_id,
                table_id=rt.table_id,
                field_name=name,
                field_type=kind,
                tag=tag,
                is_config_by_user=True,
                creator=rt.creator,
                last_modify_user=rt.last_modify_user,
            )
        elif (existing[name].tag, existing[name].field_type) != (tag, kind):
            records.filter(pk=existing[name].pk).update(tag=tag, field_type=kind)


def alias_for(ds, biz):
    lookup = {
        "bk_tenant_id": ds.bk_tenant_id,
        "namespace": BKBASE_NAMESPACE_BK_LOG,
        "bk_data_id": ds.pk,
        "event_type_override": "log",
    }
    alias = DataIdConfig.objects.filter(**lookup).first()
    if alias is None:
        # 与 register_to_bkbase 共用数据源行，两个新 RT 同时申请也只登记一个 log DataId。
        DataSource.objects.select_for_update().get(pk=ds.pk)
        alias = DataIdConfig.objects.select_for_update().filter(**lookup).first()
        if alias is None:
            alias = create_resource_with_random_name(
                DataIdConfig, DataLinkNameScene.DATA_ID, ds.pk, bk_biz_id=biz, **lookup
            )
    return alias


def compose_alias(alias, ds):
    config = alias.compose_predefined_config(ds)
    # 复用原注册的真实通道；动态分配的源从 ChannelBinding 获取，未登记的源使用采集端 MQ 配置。
    config["spec"]["predefined"]["channel"]["namespace"] = BKBASE_NAMESPACE_BK_MONITOR
    for namespace in (BKBASE_NAMESPACE_BK_MONITOR, BKBASE_NAMESPACE_BK_LOG):
        primary = find_registered_bkdata_data_id_name(ds, namespace=namespace)
        if primary:
            registered = api.bkdata.get_data_link(
                bk_tenant_id=ds.bk_tenant_id, namespace=namespace, kind="dataids", name=primary
            )
            config["spec"]["predefined"] = ds.get_registered_predefined(namespace, primary, registered["spec"])
            break
    return config


@transaction.atomic(using=DATABASE_CONNECTION_NAME)
def declare(rt, options, *, delay=True, target_cluster_id=None):
    """返回本次是否由指标链路处理；首次分配的身份必须先提交，Worker 才能下发。"""
    keys = options.keys() & {INGEST, AGGREGATE}
    if not keys and rt.default_storage != "doris":
        return False
    pipeline = MetricDorisPipeline.objects.filter(result_table=rt).first()
    if not keys and pipeline is None:
        return False
    if len(keys) > 1 or (keys and rt.default_storage != "doris"):
        raise ValueError("指标链路需要独立的 Doris RT，每张表只接受一种指标链路 option")

    if keys:
        raw = INGEST in keys
        strategy = DataLink.METRIC_DORIS_RAW if raw else DataLink.METRIC_DORIS_AGGREGATE
        scene = DataLinkNameScene.METRIC_DORIS_RAW if raw else DataLinkNameScene.METRIC_DORIS_AGGREGATE
        ds, biz = rt.get_related_datasource(), rt.get_target_bk_biz_id()
        scope = {"bk_tenant_id": rt.bk_tenant_id, "namespace": BKBASE_NAMESPACE_BK_LOG}
        storage = rt.get_storage("doris")
        if storage.origin_table_id or (pipeline is None and storage.bkbase_table_id):
            raise ValueError("请使用独立的新指标 RT，已有查询映射的表不能直接接管")
        cluster_id = (
            target_cluster_id or (pipeline.layout.get("cluster_id") if pipeline else None) or storage.storage_cluster_id
        )
        cluster = ClusterInfo.objects.get(bk_tenant_id=rt.bk_tenant_id, cluster_type="doris", pk=cluster_id)
        source, layout = None, {}
        if raw:
            MetricIngestOption.model_validate(options[INGEST])
        else:
            option = MetricAggregateOption.model_validate(options[AGGREGATE])
            source = ResultTable.objects.get(
                bk_tenant_id=rt.bk_tenant_id, table_id=option.source_table_id, default_storage="doris", is_deleted=False
            )
            source_options = options_for(source)
            if INGEST not in source_options or source.pk == rt.pk:
                raise ValueError("source_table_id 必须指向本租户的指标明细 RT")
            source_pipeline = MetricDorisPipeline.objects.filter(result_table=source).first()
            source_cluster = (
                source_pipeline.layout["cluster_id"]
                if source_pipeline
                else source.get_storage("doris").storage_cluster_id
            )
            if source_cluster != cluster.pk:
                raise ValueError("指标明细与汇总 RT 应使用同一个 Doris 集群")
            layout = option.layout(MetricIngestOption.model_validate(source_options[INGEST]))
        # 切换集群使用新的 BKBase RT/Binding，历史分段才能继续按旧集群实名查询。
        layout["cluster_id"] = cluster.pk
        if pipeline is None:
            link = create_resource_with_random_name(
                DataLink,
                scene,
                ds.pk,
                name_field="data_link_name",
                **scope,
                bk_data_id=ds.pk,
                table_ids=[rt.table_id],
                data_link_strategy=strategy,
            )
            pipeline = MetricDorisPipeline(result_table=rt, data_link=link)
        elif pipeline.data_link.data_link_strategy != strategy:
            raise ValueError("入库与汇总需要分别配置在两张 RT 上")
        if (
            pipeline.output_id is None
            or pipeline.layout != layout
            or binding_for(pipeline.output).doris_cluster_name != cluster.cluster_name
        ):
            pipeline.output = create_resource_with_random_name(
                ResultTableConfig,
                scene,
                ds.pk,
                conflict_models=(DorisStorageBindingConfig, DataBusConfig),
                bk_biz_id=biz,
                table_id=rt.table_id,
                data_type="log",
                data_link_name=pipeline.data_link_id,
                **scope,
            )
            pipeline.output.bkbase_table_id = f"{pipeline.output.datalink_biz_ids.data_biz_id}_{pipeline.output.name}"
            pipeline.output.save(update_fields=["bkbase_table_id"])
        pipeline.layout, pipeline.source = layout, source
        # Binding 名和实际物理表位置也在首次下发之前持久化。
        output = pipeline.output
        data_biz = output.bkbase_table_id.split("_", 1)[0]
        table = f"{output.name}_{data_biz}" if raw else output.name
        binding, _ = DorisStorageBindingConfig.objects.update_or_create(
            **scope,
            name=output.name,
            defaults={
                "bk_biz_id": biz,
                "data_link_name": pipeline.data_link_id,
                "table_id": rt.table_id,
                "bkbase_result_table_name": output.name,
                "doris_cluster_name": cluster.cluster_name,
                "physical_tables": {"main": f"mapleleaf_{data_biz}.{table}"},
            },
        )
        if raw:
            alias = alias_for(ds, biz)
            bus, _ = DataBusConfig.objects.get_or_create(
                **scope,
                data_link_name=pipeline.data_link_id,
                defaults={
                    "name": output.name,
                    "bk_biz_id": biz,
                    "bk_data_id": ds.pk,
                    "data_id_name": alias.name,
                    "source_name": alias.name,
                    "role": "clean",
                    "data_link_strategy": strategy,
                    "consumer_group": f"{output.namespace}_{output.name}",
                    "sink_names": [f"DorisBinding:{binding.name}"],
                },
            )
            sinks = [f"DorisBinding:{binding.name}"]
            if bus.sink_names != sinks:
                bus.sink_names = sinks
                bus.save(update_fields=["sink_names"])
    pipeline.phase = "apply" if keys and rt.is_enable else "stop"
    pipeline.status_reason = ""
    pipeline.save()
    if delay:
        from metadata.task.datalink import reconcile_metric_doris_rt

        transaction.on_commit(
            lambda: reconcile_metric_doris_rt.delay(rt.pk), using=DATABASE_CONNECTION_NAME, robust=True
        )
    return True


def stop_managed_pipeline(rt, *, target_cluster_id=None):
    # 暂停只需要本地归属，即使明细 option 或 Binding 不可用也能停止汇总。
    pipeline = MetricDorisPipeline.objects.filter(result_table=rt).first()
    if pipeline is None:
        return False
    if target_cluster_id is not None:
        pipeline.layout["cluster_id"] = target_cluster_id
    pipeline.phase, pipeline.status_reason = "stop", ""
    pipeline.save(update_fields=["layout", "phase", "status_reason"])
    from metadata.task.datalink import reconcile_metric_doris_rt

    transaction.on_commit(lambda: reconcile_metric_doris_rt.delay(rt.pk), using=DATABASE_CONNECTION_NAME, robust=True)
    return True


def compose_metric_configs(link, *, data_source, table_id, consumer_group=None):
    pipeline = MetricDorisPipeline.objects.select_related("result_table", "output").get(data_link=link)
    rt, output = pipeline.result_table, pipeline.output
    storage = DorisStorage.get_by_table_id(link.bk_tenant_id, table_id)
    binding = binding_for(output)
    target = physical_ref(binding)
    raw = pipeline.source_id is None
    ingest = get_source_option(rt) if raw else None
    labels = ingest.labels if raw else pipeline.layout["labels"]
    fields = metric_fields(labels, aggregate=not raw)
    keys = [] if raw else ["thedate", "dtEventTimeStamp", "metric_name", *labels]
    binding_config = binding.compose_config(
        storage_cluster_name=binding.doris_cluster_name,
        rt_name=output.name,
        db=target["database"],
        table=target["table"],
        storage_keys=keys,
        table_type="duplicate_table" if raw else "primary_table",
        flush_timeout=(storage.doris_storage_config or {}).get("flush_timeout"),
        expires=f"{storage.expire_days}d",
        json_fields=[],
        field_config_group={},
        original_json_fields=[],
    )
    binding_config["spec"]["storage_config"]["unique_partition_table"] = False
    configs = [output.compose_config(fields=fields), binding_config]
    if raw:
        bus = DataBusConfig.objects.get(
            data_link_name=link.pk, bk_tenant_id=link.bk_tenant_id, namespace=link.namespace
        )
        alias = DataIdConfig.objects.get(bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, name=bus.source_name)
        sink = {**binding_config["spec"]["data"], "kind": binding.kind, "name": binding.name}
        databus = bus.compose_config(sinks=[sink], transforms=[ingest.clean_transform()])
        databus["spec"].update(autoOffsetReset="latest", subTaskNum=ingest.task_num)
        configs = [compose_alias(alias, data_source), *configs, databus]
    return configs
