"""按已知资源关联批量查询存储，配置查询不访问或修改下游服务。"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import logging

from django.conf import settings
from django.db.models import Q

from bkmonitor.views.resource_storage import matches_selector
from constants.common import DEFAULT_TENANT_ID
from metadata import models

logger = logging.getLogger("metadata")

BCS_DATA_FIELDS = {
    "k8s_metric": "K8sMetricDataID",
    "custom_metric": "CustomMetricDataID",
    "k8s_event": "K8sEventDataID",
    "custom_event": "CustomEventDataID",
    "system_log": "SystemLogDataID",
    "custom_log": "CustomLogDataID",
}
HOST_ETL_TYPES = {
    "bk_system_basereport": "base",
    "bk_multi_tenancy_basereport": "base",
    "bk_system_proc": "process_perf",
    "bk_multi_tenancy_system_proc_perf": "process_perf",
    "bk_system_proc_port": "process_port",
    "bk_multi_tenancy_system_proc_port": "process_port",
    "bk_multi_tenancy_agent_event": "event",
}
IDENTITY_FIELDS = ("scene", "resource_id", "resource_name", "resource_status", "data_type")
CLUSTER_FIELDS = ("cluster_id", "cluster_name", "display_name", "cluster_type", "is_default_cluster")


def builtin_data_ids():
    """仅这些内置 ID 可引用默认租户的数据源；不做任意跨租户回退。"""
    return {
        getattr(settings, name)
        for name in (
            "SNAPSHOT_DATAID",
            "PROCESS_PERF_DATAID",
            "PROCESS_PORT_DATAID",
            "GSE_CUSTOM_EVENT_DATAID",
            "UPTIMECHECK_HTTP_DATAID",
            "UPTIMECHECK_TCP_DATAID",
            "UPTIMECHECK_UDP_DATAID",
            "UPTIMECHECK_ICMP_DATAID",
        )
    }


def group_by(items, field):
    result = defaultdict(list)
    for item in items:
        result[getattr(item, field)].append(item)
    return result


def append_unique(items, item):
    if item not in items:
        items.append(item)


class ResourceStorageQuery:
    def __init__(self, bk_tenant_id, bk_biz_id):
        self.tenant = bk_tenant_id
        self.biz = bk_biz_id

    def query(self, resources, selectors, include_runtime, page, page_size, **kwargs):
        references = list(resources)
        scenes = {selector["scene"] for selector in selectors}
        if not scenes or "bcs" in scenes:
            references.extend(self.bcs_references())
        if not scenes or "host" in scenes:
            references.extend(self.host_references())
        references = [ref for ref in references if matches_selector(ref, selectors)]
        rows = self.resolve_references(references)
        if not scenes or "recording_rule" in scenes:
            rows.extend(self.recording_rule_rows(selectors))
        rows = self.add_derived_tables(rows)
        unique = {}
        for row in rows:
            key = tuple(
                row.get(field)
                for field in ("scene", "resource_id", "data_type", "_tenant_id", "bk_data_id", "result_table_id")
            )
            unique.setdefault(key, row)
        rows = sorted(
            unique.values(),
            key=lambda row: (
                row["scene"],
                row["resource_id"],
                row["data_type"],
                row["bk_data_id"] or 0,
                row["result_table_id"] or "",
            ),
        )
        total = len(rows)
        rows = rows[(page - 1) * page_size : page * page_size]
        for tenant, tenant_rows in self.group_rows(rows).items():
            context = self.prefetch_storage(tenant, tenant_rows)
            for row in tenant_rows:
                self.add_storage(row, context)
            if include_runtime:
                self.add_runtime(tenant, tenant_rows, context)
        for row in rows:
            row.pop("_tenant_id", None)
            row.pop("_source", None)
            row.pop("_recording_rule_output", None)
        return {"items": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def group_rows(rows):
        result = defaultdict(list)
        for row in rows:
            result[row["_tenant_id"]].append(row)
        return result

    def bcs_references(self):
        clusters = list(
            models.BCSClusterInfo.objects.filter(bk_tenant_id=self.tenant, bk_biz_id=self.biz).exclude(
                status__in=[
                    models.BCSClusterInfo.CLUSTER_STATUS_DELETED,
                    models.BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
                ]
            )
        )
        federal = group_by(
            models.BcsFederalClusterInfo.objects.filter(
                bk_tenant_id=self.tenant,
                fed_cluster_id__in=[cluster.cluster_id for cluster in clusters],
                is_deleted=False,
            ),
            "fed_cluster_id",
        )
        result = []
        for cluster in clusters:
            identity = {
                "scene": "bcs",
                "resource_id": cluster.cluster_id,
                "resource_name": cluster.cluster_id,
                "resource_status": cluster.status,
                "expand_tables": True,
            }
            for kind, field in BCS_DATA_FIELDS.items():
                data_id = getattr(cluster, field)
                if data_id:
                    result.append({**identity, "data_type": kind, "bk_data_id": data_id})
            for relation in federal[cluster.cluster_id]:
                for kind, field in (
                    ("k8s_metric", "fed_builtin_metric_table_id"),
                    ("k8s_event", "fed_builtin_event_table_id"),
                ):
                    table_id = getattr(relation, field)
                    if table_id:
                        result.append({**identity, "data_type": kind, "table_id": table_id, "expand_tables": False})
        return result

    def host_references(self):
        from bkm_space.utils import bk_biz_id_to_space_uid

        space_uid = bk_biz_id_to_space_uid(self.biz)
        space_type, space_id = space_uid.split("__", 1)
        space_ids = models.SpaceDataSource.objects.filter(
            bk_tenant_id=self.tenant,
            space_type_id=space_type,
            space_id__in=[space_id, "0"] if space_type == "bkcc" else [space_id],
        ).values_list("bk_data_id", flat=True)
        table_ids = models.ResultTable.objects.filter(bk_tenant_id=self.tenant, bk_biz_id=self.biz).values_list(
            "table_id", flat=True
        )
        table_data_ids = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=self.tenant, table_id__in=table_ids
        ).values_list("bk_data_id", flat=True)
        sources = list(
            models.DataSource.objects.filter(bk_tenant_id=self.tenant, etl_config__in=HOST_ETL_TYPES).filter(
                Q(space_uid=space_uid)
                | Q(bk_data_id__in=space_ids)
                | Q(bk_data_id__in=table_data_ids)
                | Q(is_platform_data_id=True, space_type_id__in=["all", space_type])
                | Q(is_tenant_specific_global=True)
            )
        )
        if self.tenant != DEFAULT_TENANT_ID:
            sources.extend(
                models.DataSource.objects.filter(
                    bk_tenant_id=DEFAULT_TENANT_ID,
                    bk_data_id__in=builtin_data_ids(),
                    etl_config__in=HOST_ETL_TYPES,
                    is_platform_data_id=True,
                )
            )
        return [
            {
                "scene": "host",
                "resource_id": str(self.biz),
                "resource_name": "主机监控",
                "resource_status": "enabled" if source.is_enable else "disabled",
                "data_type": HOST_ETL_TYPES[source.etl_config],
                "bk_data_id": source.bk_data_id,
                "expand_tables": True,
                "is_builtin": True,
            }
            for source in sources
        ]

    def recording_rule_rows(self, selectors):
        from bkm_space.utils import bk_biz_id_to_space_uid
        from metadata.models.record_rule.constants import RecordRuleV4DesiredStatus
        from metadata.models.record_rule.v4.models import RecordRuleV4

        space_type, space_id = bk_biz_id_to_space_uid(self.biz).split("__", 1)
        rules = (
            RecordRuleV4.objects.filter(
                bk_tenant_id=self.tenant, space_type=space_type, space_id=space_id, deleted_at__isnull=True
            )
            .exclude(desired_status=RecordRuleV4DesiredStatus.DELETED.value)
            .only("id", "name", "desired_status", "table_id", "dst_vm_table_id", "dst_vm_storage_name")
        )
        rows = []
        for rule in rules:
            ref = {
                "scene": "recording_rule",
                "resource_id": str(rule.pk),
                "resource_name": rule.name,
                "resource_status": rule.desired_status,
                "data_type": "metric",
            }
            if not matches_selector(ref, selectors):
                continue
            # V4 输出没有采集 Data ID / DSRT；Flow 负责创建下游表和存储绑定。
            row = self.make_row(ref, self.tenant, None, rule.table_id or None, None)
            row["_recording_rule_output"] = {
                "table": rule.dst_vm_table_id or None,
                "cluster_name": rule.dst_vm_storage_name or None,
            }
            rows.append(row)
        return rows

    def resolve_references(self, references):
        if not references:
            return []
        ids = {ref["bk_data_id"] for ref in references if ref.get("bk_data_id")}
        names = {ref["data_name"] for ref in references if ref.get("data_name") and not ref.get("bk_data_id")}
        tables = {ref["table_id"] for ref in references if ref.get("table_id")}
        shared_ids = {ref.get("bk_data_id") for ref in references if ref.get("is_builtin")} & builtin_data_ids()
        sources = list(
            models.DataSource.objects.filter(bk_tenant_id=self.tenant).filter(
                Q(bk_data_id__in=ids) | Q(data_name__in=names)
            )
        )
        if self.tenant != DEFAULT_TENANT_ID and shared_ids:
            sources.extend(models.DataSource.objects.filter(bk_tenant_id=DEFAULT_TENANT_ID, bk_data_id__in=shared_ids))
        by_id = {source.bk_data_id: source for source in sources}
        by_name = {source.data_name: source for source in sources if source.bk_tenant_id == self.tenant}
        ids.update(by_id)
        mappings = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=self.tenant).filter(
                Q(bk_data_id__in=ids) | Q(table_id__in=tables)
            )
        )
        # 1001 等公共入口可有租户专属结果表，优先采用这些明确关联。
        mapped_ids = {mapping.bk_data_id for mapping in mappings}
        if self.tenant != DEFAULT_TENANT_ID and shared_ids - mapped_ids:
            mappings.extend(
                models.DataSourceResultTable.objects.filter(
                    bk_tenant_id=DEFAULT_TENANT_ID, bk_data_id__in=shared_ids - mapped_ids
                )
            )
        for source in models.DataSource.objects.filter(
            bk_tenant_id=self.tenant, bk_data_id__in={mapping.bk_data_id for mapping in mappings} - set(by_id)
        ):
            by_id[source.bk_data_id] = source
        by_data = group_by(mappings, "bk_data_id")
        by_table = group_by(mappings, "table_id")
        rows = []
        for ref in references:
            source = by_id.get(ref.get("bk_data_id")) if ref.get("bk_data_id") else by_name.get(ref.get("data_name"))
            target_mappings = by_data[source.bk_data_id] if source else []
            if ref.get("table_id") and not ref.get("expand_tables"):
                target_mappings = [
                    m for m in by_table[ref["table_id"]] if not source or m.bk_data_id == source.bk_data_id
                ]
            if target_mappings:
                for mapping in target_mappings:
                    rows.append(
                        self.make_row(
                            ref,
                            mapping.bk_tenant_id,
                            mapping.bk_data_id,
                            mapping.table_id,
                            by_id.get(mapping.bk_data_id),
                        )
                    )
            else:
                row = self.make_row(
                    ref,
                    self.tenant,
                    ref.get("bk_data_id") or (source.bk_data_id if source else None),
                    ref.get("table_id") or None,
                    source,
                )
                row["errors"].append("未找到数据源与结果表关联")
                rows.append(row)
        return rows

    @staticmethod
    def make_row(ref, tenant, data_id, table_id, source):
        return {
            **{field: ref[field] for field in IDENTITY_FIELDS},
            "bk_data_id": data_id,
            "data_name": source.data_name if source else ref.get("data_name") or None,
            "result_table_id": table_id,
            "result_table_name": None,
            "kafka": [],
            "storages": [],
            "errors": [ref["error"]] if ref.get("error") else [],
            "_tenant_id": tenant,
            "_source": source,
        }

    def add_derived_tables(self, rows):
        result = list(rows)
        for tenant, tenant_rows in self.group_rows(rows).items():
            records = list(
                models.CMDBLevelRecord.objects.filter(
                    bk_tenant_id=tenant,
                    source_table_id__in={row["result_table_id"] for row in tenant_rows if row["result_table_id"]},
                    is_disable=False,
                )
            )
            sources = {
                source.bk_data_id: source
                for source in models.DataSource.objects.filter(
                    bk_tenant_id=tenant, bk_data_id__in={record.bk_data_id for record in records}
                )
            }
            by_source = group_by(records, "source_table_id")
            for row in tenant_rows:
                for record in by_source[row["result_table_id"]]:
                    derived = self.make_row(
                        row, tenant, record.bk_data_id, record.target_table_id, sources.get(record.bk_data_id)
                    )
                    derived["source_result_table_id"] = row["result_table_id"]
                    result.append(derived)
        return result

    @staticmethod
    def prefetch_storage(tenant, rows):
        tables = {row["result_table_id"] for row in rows if row["result_table_id"]}
        context = {
            "tables": {
                rt.table_id: rt for rt in models.ResultTable.objects.filter(bk_tenant_id=tenant, table_id__in=tables)
            }
        }
        for key, model in (
            ("kafka", models.KafkaStorage),
            ("influxdb", models.InfluxDBStorage),
            ("elasticsearch", models.ESStorage),
            ("doris", models.DorisStorage),
            ("redis", models.RedisStorage),
            ("argus", models.ArgusStorage),
            ("surrealdb", models.SurrealDBStorage),
            ("bkdata", models.BkDataStorage),
        ):
            context[key] = group_by(model.objects.filter(bk_tenant_id=tenant, table_id__in=tables), "table_id")
        # 日志/APM 虚拟表可引用另一个存储记录，按类型一次查询全部物理记录。
        origin_tables = set()
        for key, model in (("elasticsearch", models.ESStorage), ("doris", models.DorisStorage)):
            origins = {s.origin_table_id for group in context[key].values() for s in group if s.origin_table_id}
            physical = {s.table_id: s for s in model.objects.filter(bk_tenant_id=tenant, table_id__in=origins)}
            origin_tables.update(origins)
            for table, storages in context[key].items():
                context[key][table] = [physical.get(storage.origin_table_id, storage) for storage in storages]
        context["vm"] = group_by(
            models.AccessVMRecord.objects.filter(bk_tenant_id=tenant, result_table_id__in=tables), "result_table_id"
        )
        bkbase = list(models.BkBaseResultTable.objects.filter(bk_tenant_id=tenant, monitor_table_id__in=tables))
        context["bkbase"] = group_by(bkbase, "monitor_table_id")
        rt_names = {record.bkbase_rt_name for record in bkbase}
        # ResultTableConfig 保留 namespace，避免相同名称的不同资源互相匹配。
        rt_configs = list(
            models.ResultTableConfig.objects.filter(bk_tenant_id=tenant).filter(
                Q(table_id__in=tables) | Q(name__in=rt_names)
            )
        )
        context["rt_configs"] = defaultdict(list)
        for rt in rt_configs:
            if rt.table_id in tables:
                context["rt_configs"][rt.table_id].append(rt)
            else:
                for record in bkbase:
                    if record.bkbase_rt_name == rt.name and record.data_link_name == rt.data_link_name:
                        context["rt_configs"][record.monitor_table_id].append(rt)
        bindings = list(
            models.VMStorageBindingConfig.objects.filter(bk_tenant_id=tenant).filter(
                Q(table_id__in=tables)
                | Q(bkbase_result_table_name__in={rt.name for rt in rt_configs})
                | Q(bkbase_result_table_name="", name__in={rt.name for rt in rt_configs})
            )
        )
        context["bindings"] = defaultdict(list)
        for binding in bindings:
            if binding.table_id in tables:
                context["bindings"][binding.table_id].append(binding)
            else:
                for table_id, configs in context["rt_configs"].items():
                    if any(
                        rt.namespace == binding.namespace
                        and rt.name == (binding.bkbase_result_table_name or binding.name)
                        for rt in configs
                    ):
                        context["bindings"][table_id].append(binding)
        context["cmdb_options"] = group_by(
            models.ResultTableOption.objects.filter(bk_tenant_id=tenant, table_id__in=tables, name="cmdb_level_vm_rt"),
            "table_id",
        )
        context["cluster_history"] = group_by(
            models.StorageClusterRecord.objects.filter(
                bk_tenant_id=tenant, table_id__in=tables | origin_tables, is_deleted=False
            ),
            "table_id",
        )
        proxies = {
            storage.influxdb_proxy_storage_id
            for storages in context["influxdb"].values()
            for storage in storages
            if storage.influxdb_proxy_storage_id
        }
        context["proxies"] = {proxy.pk: proxy for proxy in models.InfluxDBProxyStorage.objects.filter(pk__in=proxies)}
        cluster_ids = {
            storage.storage_cluster_id
            for kind in ("kafka", "influxdb", "elasticsearch", "doris", "redis", "argus", "surrealdb")
            for storages in context[kind].values()
            for storage in storages
        }
        cluster_ids.update(record.vm_cluster_id for records in context["vm"].values() for record in records)
        cluster_ids.update(record.storage_cluster_id for record in bkbase)
        cluster_ids.update(record.cluster_id for records in context["cluster_history"].values() for record in records)
        cluster_ids.update(proxy.proxy_cluster_id for proxy in context["proxies"].values())
        cluster_names = {binding.vm_cluster_name for binding in bindings}
        cluster_names.update(
            row["_recording_rule_output"]["cluster_name"]
            for row in rows
            if row.get("_recording_rule_output", {}).get("cluster_name")
        )
        cluster_names.update(proxy.instance_cluster_name for proxy in context["proxies"].values())
        # 只读取可展示的集群列，不装载认证配置。
        context["clusters"] = {
            cluster["cluster_id"]: cluster
            for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=tenant)
            .filter(Q(cluster_id__in=cluster_ids) | Q(cluster_name__in=cluster_names))
            .values(*CLUSTER_FIELDS)
        }
        sources = [row["_source"] for row in rows if row["_source"]]
        source_clusters = {source.mq_cluster_id for source in sources}
        source_tenants = {source.bk_tenant_id for source in sources}
        context["source_clusters"] = {
            cluster["cluster_id"]: cluster
            for cluster in models.ClusterInfo.objects.filter(
                bk_tenant_id__in=source_tenants, cluster_id__in=source_clusters
            ).values(*CLUSTER_FIELDS)
        }
        context["topics"] = {
            topic.pk: topic
            for topic in models.KafkaTopicInfo.objects.filter(pk__in={source.mq_config_id for source in sources})
        }
        return context

    @staticmethod
    def cluster(context, cluster_id=None, name=None, cluster_type=None):
        if cluster_id in context["clusters"]:
            return context["clusters"][cluster_id]
        if name:
            for cluster in context["clusters"].values():
                if cluster["cluster_name"] == name and cluster["cluster_type"] == cluster_type:
                    return cluster
        return {
            "cluster_id": cluster_id,
            "cluster_name": name,
            "display_name": None,
            "cluster_type": cluster_type,
            "is_default_cluster": None,
        }

    def add_storage(self, row, context):
        table_id = row["result_table_id"]
        rt = context["tables"].get(table_id)
        if rt:
            row["result_table_name"] = rt.table_name_zh
        elif table_id:
            row["errors"].append("结果表元数据不存在")
        source = row["_source"]
        if source:
            topic = context["topics"].get(source.mq_config_id)
            if source.mq_cluster_id or topic:
                row["kafka"].append(
                    {
                        "stage": "ingestion",
                        "topic": topic.topic if topic else None,
                        "cluster": context["source_clusters"].get(source.mq_cluster_id)
                        or self.cluster(context, source.mq_cluster_id, cluster_type="kafka"),
                    }
                )
        elif row["bk_data_id"]:
            row["errors"].append("数据源元数据不存在")
        for storage in context["kafka"][table_id]:
            append_unique(
                row["kafka"],
                {
                    "stage": "cleaned",
                    "topic": storage.topic,
                    "cluster": self.cluster(context, storage.storage_cluster_id, cluster_type="kafka"),
                },
            )
        for record in context["vm"][table_id]:
            append_unique(
                row["storages"],
                {
                    "type": "victoria_metrics",
                    "table": record.vm_result_table_id,
                    "role": "query",
                    "cluster": self.cluster(context, record.vm_cluster_id, cluster_type="victoria_metrics"),
                },
            )
        output = row.get("_recording_rule_output")
        if output:
            append_unique(
                row["storages"],
                {
                    "type": "victoria_metrics",
                    "table": output["table"],
                    "role": "storage",
                    "cluster": self.cluster(context, name=output["cluster_name"], cluster_type="victoria_metrics")
                    if output["cluster_name"]
                    else None,
                },
            )
        for binding in context["bindings"][table_id]:
            binding_rt_name = binding.bkbase_result_table_name or binding.name
            configs = [
                rt
                for rt in context["rt_configs"][table_id]
                if rt.namespace == binding.namespace and rt.name == binding_rt_name
            ]
            physical_tables = [rt.bkbase_table_id for rt in configs if rt.bkbase_table_id]
            physical_tables.extend(
                record.bkbase_table_id
                for record in context["bkbase"][table_id]
                if record.bkbase_table_id
                and record.bkbase_rt_name == binding_rt_name
                and record.data_link_name == binding.data_link_name
            )
            # 没有明确物理表 ID 时保留资源名，不猜测 VM 表名。
            for physical_table in physical_tables or [None]:
                append_unique(
                    row["storages"],
                    {
                        "type": "victoria_metrics",
                        "table": physical_table,
                        "role": "storage",
                        "resource_name": binding.name,
                        "namespace": binding.namespace,
                        "cluster": self.cluster(context, name=binding.vm_cluster_name, cluster_type="victoria_metrics"),
                    },
                )
        for option in context["cmdb_options"][table_id]:
            if option.value:
                append_unique(
                    row["storages"],
                    {"type": "victoria_metrics", "table": option.value, "role": "derived", "cluster": None},
                )
        for record in context["bkbase"][table_id]:
            if record.bkbase_table_id and not any(
                storage["type"] == record.storage_type
                and storage["table"] == record.bkbase_table_id
                and storage["role"] == "storage"
                for storage in row["storages"]
            ):
                row["storages"].append(
                    {
                        "type": record.storage_type,
                        "table": record.bkbase_table_id,
                        "role": "storage",
                        "cluster": None
                        if record.storage_type == "victoria_metrics"
                        else self.cluster(context, record.storage_cluster_id, cluster_type=record.storage_type),
                    }
                )
        for kind in ("influxdb", "elasticsearch", "doris", "redis", "argus", "surrealdb", "bkdata"):
            for storage in context[kind][table_id]:
                item = {"type": kind, "table": None, "role": "storage", "cluster": None}
                cluster_id = getattr(storage, "storage_cluster_id", None)
                if kind == "influxdb":
                    proxy = context["proxies"].get(storage.influxdb_proxy_storage_id)
                    item.update(table=storage.real_table_name, database=storage.database)
                    if proxy:
                        item["cluster"] = self.cluster(context, name=proxy.instance_cluster_name, cluster_type=kind)
                        item["query_cluster"] = self.cluster(context, proxy.proxy_cluster_id, cluster_type=kind)
                elif kind == "elasticsearch":
                    item["table"] = storage.index_set
                elif kind == "doris":
                    item["table"] = storage.bkbase_table_id or storage.index_set
                elif kind == "redis":
                    item.update(table=storage.key, database=storage.db)
                elif kind == "bkdata":
                    item["table"] = storage.bk_data_result_table_id
                elif kind == "surrealdb":
                    item["table"] = storage.table_id
                item["cluster"] = item["cluster"] or self.cluster(context, cluster_id, cluster_type=kind)
                append_unique(row["storages"], item)
                if kind in ("elasticsearch", "doris"):
                    for history in context["cluster_history"][storage.table_id]:
                        cluster = context["clusters"].get(history.cluster_id)
                        if cluster and cluster["cluster_type"] == kind and history.cluster_id != cluster_id:
                            append_unique(row["storages"], {**item, "cluster": cluster, "role": "historical"})

    @staticmethod
    def add_runtime(tenant, rows, context):
        from metadata.resources.bkdata_link import QueryDataLinkMetadataResource
        from metadata.utils.es_tools import get_client_by_datasource_info

        reader = QueryDataLinkMetadataResource()
        # ES 的默认 get_client 会逐表查询 ClusterInfo；这里按集群一次预取并复用客户端。
        es_cluster_ids = {
            storage.storage_cluster_id for storages in context["elasticsearch"].values() for storage in storages
        }
        es_clients = {}
        for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=tenant, cluster_id__in=es_cluster_ids):
            try:
                es_clients[cluster.cluster_id] = get_client_by_datasource_info(
                    {
                        "domain_name": cluster.domain_name,
                        "port": cluster.port,
                        "schema": cluster.schema,
                        "version": cluster.version,
                        "is_ssl_verify": cluster.is_ssl_verify,
                        "auth_info": {"username": cluster.username, "password": cluster.password},
                    }
                )
            except Exception:
                logger.exception("resource storage ES client failed: tenant=%s cluster=%s", tenant, cluster.cluster_id)
        requests = {}
        row_requests = {}
        es_patterns = defaultdict(set)
        for index, row in enumerate(rows):
            ids = {record.bk_base_data_id for record in context["vm"][row["result_table_id"]] if record.bk_base_data_id}
            ids.update(
                storage.raw_data_id for storage in context["bkdata"][row["result_table_id"]] if storage.raw_data_id > 0
            )
            if not ids and row["bk_data_id"]:
                ids.add(row["bk_data_id"])
            row_requests[index] = [("bkbase", data_id) for data_id in sorted(ids)]
            for key in row_requests[index]:
                requests[key] = lambda data_id=key[1]: reader._fetch_bkbase_metadata(data_id, None, bk_tenant_id=tenant)
            if not ids:
                vm_tables = {
                    record.vm_result_table_id
                    for record in context["vm"][row["result_table_id"]]
                    if record.vm_result_table_id
                }
                output = row.get("_recording_rule_output")
                if output and output["table"]:
                    vm_tables.add(output["table"])
                for vm_table in sorted(vm_tables):
                    key = ("bkbase", "vm_result_table", vm_table)
                    row_requests[index].append(key)
                    requests[key] = lambda vm_table=vm_table: reader._fetch_bkbase_metadata(
                        None, vm_table, bk_tenant_id=tenant
                    )
            for storage in context["elasticsearch"][row["result_table_id"]]:
                key = ("elasticsearch", storage.storage_cluster_id)
                if key not in row_requests[index]:
                    row_requests[index].append(key)
                es_patterns[storage.storage_cluster_id].update((storage.search_format_v1(), storage.search_format_v2()))
        # 同一集群的全部索引模式合并请求，不逐结果表查询 ES。
        for cluster_id, patterns in es_patterns.items():
            client = es_clients.get(cluster_id)
            if client:
                requests[("elasticsearch", cluster_id)] = lambda client=client, patterns=patterns: {
                    "indices": client.cat.indices(index=",".join(sorted(patterns)), format="json", request_timeout=3)
                }
            else:
                requests[("elasticsearch", cluster_id)] = lambda: {"_error": True}
        results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {key: executor.submit(request) for key, request in requests.items()}
            for key, future in futures.items():
                try:
                    results[key] = future.result()
                except Exception:
                    logger.exception("resource storage runtime query failed: tenant=%s target=%s", tenant, key)
                    results[key] = {"_error": True}
        # 明确的字段白名单，避免下游新增字段或错误正文泄露地址/认证信息。
        branch_fields = (
            "result_table_id",
            "kafka_shipper_cluster_name",
            "kafka_shipper_topic_name",
            "doris_table_name",
        )
        for index, row in enumerate(rows):
            runtime = {"bkbase": [], "elasticsearch": [], "errors": []}
            physical_ids = {storage["table"] for storage in row["storages"] if storage["table"]}
            physical_ids.update(record.bkbase_table_id for record in context["bkbase"][row["result_table_id"]])
            for key in row_requests[index]:
                result = results[key]
                if result and result.get("_error"):
                    runtime["errors"].append({"source": key[0], "message": "运行信息查询失败或超时"})
                    continue
                if key[0] == "bkbase":
                    payload = reader._normalize_bkbase_metadata_payload(result) or {}
                    for branch in payload.get("branches", []):
                        # 共享 Data ID 的其他结果表不能被附到当前资源。
                        if branch.get("result_table_id") not in physical_ids | {row["result_table_id"]}:
                            continue
                        append_unique(
                            runtime["bkbase"], {field: branch[field] for field in branch_fields if field in branch}
                        )
                elif result:
                    for storage in context["elasticsearch"][row["result_table_id"]]:
                        if storage.storage_cluster_id == key[1]:
                            append_unique(
                                runtime["elasticsearch"],
                                {
                                    "result_table_id": storage.table_id,
                                    "indices": sorted(
                                        item["index"]
                                        for item in result["indices"]
                                        if storage.index_re_common.fullmatch(item["index"])
                                    ),
                                },
                            )
            row["runtime"] = runtime
