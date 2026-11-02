"""多表采集插件迁移：保留旧表，通过 data_label_aliases 兼容历史查询。"""

import copy
import json
from collections import defaultdict

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q

from core.drf_resource import api
from metadata import config, models
from metadata.management.commands.migrate_default_plugin_v4 import (
    PLUGIN_PREFIXES,
    STRATEGIES,
    Command as DefaultPluginCommand,
)
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import DataBusConfig
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.vm.utils import create_bkbase_data_link


def merge_aliases(*groups):
    return list(dict.fromkeys(alias for group in groups for alias in group if isinstance(alias, str) and alias))


class PluginMigrationRouter(SpaceTableIDRedis):
    def _compose_record_rule_table_id_detail(self, bk_tenant_id):
        # 迁移只发布插件 RT，不附带全租户预计算规则；不修改公共路由接口。
        return {}


class Command(DefaultPluginCommand):
    help = "多表插件迁移到 default/V4，保留旧表及历史查询；precheck / pre-run / execute / status"

    def load_context(self, data_id, vm_cluster_name):
        super().load_context(data_id, vm_cluster_name)
        self.table_id = f"{self.source.data_name}.__default__"
        tables = list(
            models.ResultTable.objects.filter(bk_tenant_id=self.tenant, table_id__in=self.related_tables).order_by(
                "table_id"
            )
        )
        self.legacy_tables = [table for table in tables if table.table_id != self.table_id]
        self.table = next((table for table in tables if table.table_id == self.table_id), None)
        self.default_exists = self.table is not None
        # 未创建时用计划对象承载预演；业务读取仍使用 ResultTable.get_target_bk_biz_id。
        if not self.table:
            reference = tables[0] if tables else None
            self.table = models.ResultTable(
                bk_tenant_id=self.tenant,
                table_id=self.table_id,
                bk_biz_id=reference.bk_biz_id if reference else 0,
                label=reference.label if reference else models.Label.RESULT_TABLE_LABEL_OTHER,
                data_label=self.source.data_name,
            )
            self.table._related_datasource = self.source
        self.rt_case = "legacy_tables_with_default" if self.default_exists else "legacy_tables_without_default"
        self.options = defaultdict(dict)
        for option in models.ResultTableOption.objects.filter(
            bk_tenant_id=self.tenant, table_id__in=self.related_tables
        ):
            if (
                option.name == models.ResultTableOption.OPTION_DATA_LABEL_ALIASES
                and option.value_type != models.ResultTableOption.TYPE_LIST
            ):
                continue
            self.options[option.table_id][option.name] = option.get_value()
        self.group = models.TimeSeriesGroup.objects.filter(bk_tenant_id=self.tenant, bk_data_id=data_id).first()
        self.alias_plan = {
            table.table_id: merge_aliases(
                self.options[table.table_id].get(models.ResultTableOption.OPTION_DATA_LABEL_ALIASES, []),
                [self.table_id],
            )
            for table in self.legacy_tables
        }
        self.alias_plan[self.table_id] = merge_aliases(
            self.options[self.table_id].get(models.ResultTableOption.OPTION_DATA_LABEL_ALIASES, []),
            [table.table_id for table in self.legacy_tables],
        )
        self.labels = merge_aliases((self.table.data_label or "").split(","), self.alias_plan[self.table_id])
        self.vm_record = models.AccessVMRecord.objects.filter(
            bk_tenant_id=self.tenant, result_table_id=self.table_id
        ).last()
        self.vm_cluster_ids = set(
            models.AccessVMRecord.objects.filter(bk_tenant_id=self.tenant, result_table_id__in=self.related_tables)
            .exclude(vm_cluster_id__isnull=True)
            .values_list("vm_cluster_id", flat=True)
        )
        clusters = models.ClusterInfo.objects.filter(bk_tenant_id=self.tenant, cluster_type=models.ClusterInfo.TYPE_VM)
        if vm_cluster_name:
            self.cluster = clusters.get(cluster_name=vm_cluster_name)
        elif self.vm_record:
            self.cluster = clusters.filter(cluster_id=self.vm_record.vm_cluster_id).first()
        elif len(self.vm_cluster_ids) == 1:
            self.cluster = clusters.filter(cluster_id=next(iter(self.vm_cluster_ids))).first()
        else:
            self.cluster = None
        self.metric_info = []
        self.spaces = self.get_route_spaces()

    def get_route_spaces(self):
        """公共插件只刷新配有采集的业务，不枚举整个租户的空间。"""
        if self.table.bk_biz_id != 0:
            return list(
                models.SpaceDataSource.objects.filter(bk_tenant_id=self.tenant, bk_data_id=self.source.bk_data_id)
                .values("space_type_id", "space_id")
                .distinct()
            )

        from monitor_web.models import CollectConfigMeta

        plugin_type, _, plugin_id = self.source.data_name.partition("_")
        biz_ids = list(
            CollectConfigMeta.objects.filter(
                bk_tenant_id=self.tenant,
                plugin_id__iexact=plugin_id,
                collect_type__iexact=plugin_type,
                is_deleted=False,
                bk_biz_id__gt=0,
            )
            .order_by()
            .values_list("bk_biz_id", flat=True)
            .distinct()
        )
        if not biz_ids:
            return []
        return list(
            models.Space.objects.filter(
                bk_tenant_id=self.tenant, space_type_id="bkcc", space_id__in=[str(biz_id) for biz_id in biz_ids]
            )
            .order_by("space_id")
            .values("space_type_id", "space_id")
        )

    def precheck(self):
        errors = []
        if self.source.etl_config not in STRATEGIES or not self.source.data_name.startswith(PLUGIN_PREFIXES):
            errors.append("仅支持普通采集插件的 bk_exporter / bk_standard 数据源")
        if not self.source.is_enable:
            errors.append("数据源未启用")
        if not self.related_tables:
            errors.append("未找到插件结果表")
        existing_ids = {table.table_id for table in self.legacy_tables}
        if self.default_exists:
            existing_ids.add(self.table_id)
        if set(self.related_tables) - existing_ids:
            errors.append("DataID 关联了不存在的结果表，请先处理缺失记录")
        if self.default_exists and (not self.table.is_enable or self.table.is_deleted):
            errors.append("default 表已停用或删除")
        if self.default_exists and self.table.schema_type != models.ResultTable.SCHEMA_TYPE_FREE:
            errors.append("已有 default 为固定 schema，不能直接复用为单指标单表，需单独处理历史存储")
        if self.default_exists and self.table_id not in self.linked_tables:
            errors.append("已有 default 表未关联当前 DataID")
        if not self.legacy_tables and self.options[self.table_id].get("is_split_measurement"):
            errors.append("已是唯一 default 单指标单表，请使用 migrate_default_plugin_v4")
        if self.group and (self.group.table_id != self.table_id or self.group.is_delete):
            errors.append("已有 TimeSeriesGroup 未指向有效 default 表，请先单独处理")
        if any(table_id.endswith(("_cmdb_level", "_cmdb")) for table_id in self.related_tables):
            errors.append("包含 CMDB 分表，需单独处理节点聚合兼容")
        if models.CMDBLevelRecord.objects.filter(
            bk_tenant_id=self.tenant, source_table_id__in=self.related_tables, is_disable=False
        ).exists():
            errors.append("存在启用的 CMDB 分表关系，需先单独处理")
        if not self.cluster:
            errors.append("没有唯一可复用的 VM 集群，请指定 --vm-cluster-name")
        if not self.topic:
            errors.append("数据源未配置 Kafka Topic")
        if not settings.ENABLE_V2_VM_DATA_LINK:
            errors.append("ENABLE_V2_VM_DATA_LINK 未开启")

        # 别名写入列表 Option，不受主标签的 128 字符限制；只检查新表实际要写入的主标签。
        limit = models.ResultTable._meta.get_field("data_label").max_length
        if not self.default_exists and len(self.table.data_label) > limit:
            errors.append(f"新 default 主标签长度 {len(self.table.data_label)} 超过 {limit}")
        if errors:
            return errors

        components = self.component_records()
        if any(component.name for component in components) and any(not component.name for component in components):
            data_id_names = [
                component.name for component in components if component.kind == "DataId" and component.name
            ]
            historical = list(
                DataBusConfig.objects.filter(bk_tenant_id=self.tenant, namespace=self.namespace)
                .filter(Q(bk_data_id=self.source.bk_data_id) | Q(data_id_name__in=data_id_names))
                .values_list("name", flat=True)
            )
            errors.append(f"已有 V4 组件记录不完整，需先单独处理，禁止重复 apply；关联或历史 Databus：{historical}")
        if not self.group:
            self.metric_info, metric_errors = self.collect_metric_info()
            errors.extend(metric_errors)
        return errors

    def collect_metric_info(self):
        """从旧 RT 的指标/维度定义准备新组，不从全环境扫描插件配置。"""
        table_ids = self.related_tables
        fields = list(
            models.ResultTableField.objects.filter(
                bk_tenant_id=self.tenant, table_id__in=table_ids, is_disabled=False
            ).values("table_id", "field_name", "tag", "field_type", "description", "unit", "alias_name")
        )
        dimensions = defaultdict(list)
        for field in fields:
            if field["tag"] in ("dimension", "group"):
                dimensions[field["table_id"]].append(
                    {
                        "field_name": field["field_name"],
                        "description": field["description"],
                        "type": field["field_type"],
                        "unit": field["unit"],
                    }
                )
        metrics, owners, errors = [], {}, []
        for field in fields:
            if field["tag"] != "metric":
                continue
            name = field["field_name"]
            if name in owners:
                errors.append(f"旧表指标重名：{name}，来自 {owners[name]} 和 {field['table_id']}，需先明确合并语义")
                continue
            owners[name] = field["table_id"]
            metrics.append(
                {
                    "field_name": name,
                    "description": field["description"],
                    "unit": field["unit"],
                    "type": field["field_type"],
                    "alias_name": field["alias_name"],
                    "is_active": True,
                    "tag_list": copy.deepcopy(dimensions[field["table_id"]]),
                }
            )
        return metrics, errors

    def plan(self):
        plan = super().plan()
        plan.update(
            default_exists=self.default_exists,
            metric_count=len(self.metric_info) if not self.group else None,
            legacy_table_ids=[table.table_id for table in self.legacy_tables],
            data_label_aliases=self.alias_plan,
            space_routes_to_refresh=self.spaces,
            space_route_count=len(self.spaces),
            steps=[
                "仅准备 default、TimeSeriesGroup 和指标元数据，保留旧 RT、关系及存储",
                "首次申请 V4 链路；已有完整组件只复用，不重复 apply",
                "检查本地和远端 Databus 消费组；默认等待 Ok，--no-wait 仅跳过就绪等待",
                "设置单指标单表/V4 option，default 添加旧表 ID 别名，旧表添加 default ID 别名",
                "刷新 RT 详情、空间及 data_label 路由，最后清理 Transfer",
            ],
        )
        return plan

    def prepare_default(self):
        # 专用准备路径不调用会刷新 Transfer 的 create_time_series_group/access。
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            if not self.default_exists:
                self.table = models.ResultTable.create_result_table(
                    bk_tenant_id=self.tenant,
                    bk_data_id=self.source.bk_data_id,
                    table_id=self.table_id,
                    bk_biz_id=self.table.bk_biz_id,
                    table_name_zh=self.source.data_name,
                    is_custom_table=True,
                    schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
                    operator=self.operator,
                    default_storage=models.ClusterInfo.TYPE_INFLUXDB,
                    label=self.table.label,
                    data_label=self.source.data_name,
                    create_storage=False,
                    is_sync_db=False,
                    is_time_field_only=True,
                    field_list=copy.deepcopy(models.TimeSeriesGroup.STORAGE_FIELD_LIST),
                    option={"enable_default_value": False, "enable_field_black_list": False},
                )
                self.default_exists = True
                self.linked_tables.append(self.table_id)
                self.related_tables.append(self.table_id)
            if not self.group:
                _, self.group = models.TimeSeriesGroup._create(
                    table_id=self.table_id,
                    bk_data_id=self.source.bk_data_id,
                    bk_biz_id=self.biz_id,
                    custom_group_name=self.source.data_name,
                    time_series_group_name=self.source.data_name,
                    label=self.table.label,
                    operator=self.operator,
                    bk_tenant_id=self.tenant,
                    is_split_measurement=True,
                    is_need_deploy_collector_config=False,
                )
                models.TimeSeriesGroup._post_process_create(self.group, {})
                self.group.update_metrics(self.metric_info)
                # update_metrics 创建 RT 指标时使用默认类型；补回旧表的字段定义。
                definitions = {metric["field_name"]: metric for metric in self.metric_info}
                fields = list(
                    models.ResultTableField.objects.filter(
                        bk_tenant_id=self.tenant, table_id=self.table_id, field_name__in=definitions, tag="metric"
                    )
                )
                for field in fields:
                    definition = definitions[field.field_name]
                    field.field_type = definition["type"]
                    field.description = definition["description"]
                    field.unit = definition["unit"]
                    field.alias_name = definition["alias_name"]
                if fields:
                    models.ResultTableField.objects.bulk_update(
                        fields, ["field_type", "description", "unit", "alias_name"]
                    )

    def consumer_group_status(self):
        expected = compose_transfer_consumer_group(self.source)
        result = []
        for component in self.component_records():
            if component.kind != "Databus" or not component.name:
                continue
            remote = api.bkdata.get_data_link(
                bk_tenant_id=self.tenant,
                kind=DataLinkKind.get_choice_value(component.kind),
                namespace=component.namespace,
                name=component.name,
            )
            actual = (remote.get("spec") or {}).get("consumerGroup")
            result.append(
                {
                    "name": component.name,
                    "expected": expected,
                    "local": component.consumer_group,
                    "remote": actual,
                    "matches": bool(expected) and component.consumer_group == actual == expected,
                }
            )
        return result

    def execute_migration(self, *, no_wait=False, wait_timeout=300, poll_interval=10):
        self.prepare_default()
        components = self.component_records()
        newly_applied = not any(component.name for component in components)
        if newly_applied:
            self.source.register_to_bkbase(bk_biz_id=self.datalink_biz_id, namespace=self.namespace)
            create_bkbase_data_link(
                bk_biz_id=self.datalink_biz_id,
                data_source=self.source,
                monitor_table_id=self.table_id,
                storage_cluster_name=self.cluster.cluster_name,
                data_link_strategy=STRATEGIES[self.source.etl_config],
                namespace=self.namespace,
                consumer_group=compose_transfer_consumer_group(self.source),
            )
        else:
            self.stdout.write("复用已有完整 V4 组件，不重新注册或 apply……")
        components = self.component_records()
        if not components or any(not component.name for component in components):
            raise CommandError("V4 组件记录不完整，未发布兼容标签、路由或清理 Transfer")
        if not no_wait:
            self.wait_for_components(
                wait_timeout=wait_timeout, poll_interval=poll_interval, newly_applied=newly_applied
            )
        groups = self.consumer_group_status()
        self.output({"bk_data_id": self.source.bk_data_id, "consumer_groups": groups})
        if not groups or not all(item["matches"] for item in groups):
            raise CommandError("Databus 消费组未正确复用 Transfer，未发布兼容标签、路由或执行收尾")
        self.publish_and_finalize()

    def publish_and_finalize(self):
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            for table_id, aliases in self.alias_plan.items():
                models.ResultTableOption.objects.update_or_create(
                    bk_tenant_id=self.tenant,
                    table_id=table_id,
                    name=models.ResultTableOption.OPTION_DATA_LABEL_ALIASES,
                    defaults={
                        "value": json.dumps(aliases, ensure_ascii=False),
                        "value_type": models.ResultTableOption.TYPE_LIST,
                        "creator": self.operator,
                    },
                )
            for name in ("is_split_measurement", "enable_plugin_v4_data_link"):
                models.ResultTableOption.objects.update_or_create(
                    bk_tenant_id=self.tenant,
                    table_id=self.table_id,
                    name=name,
                    defaults={"value": "true", "value_type": "bool", "creator": self.operator},
                )
            for option in self.group.get_datasource_options() + [{"name": "is_split_measurement", "value": True}]:
                value = option["value"]
                value_type = option.get("value_type") or ("bool" if isinstance(value, bool) else "string")
                models.DataSourceOption.objects.update_or_create(
                    bk_tenant_id=self.tenant,
                    bk_data_id=self.source.bk_data_id,
                    name=option["name"],
                    defaults={
                        "value": json.dumps(value) if value_type == "bool" else value,
                        "value_type": value_type,
                        "creator": self.operator,
                    },
                )
            self.group.is_split_measurement = True
            self.group.save(update_fields=["is_split_measurement"])
        self.table.refresh_from_db()
        self.labels = merge_aliases((self.table.data_label or "").split(","), self.alias_plan[self.table_id])
        router = PluginMigrationRouter()
        router.push_table_id_detail(
            bk_tenant_id=self.tenant,
            table_id_list=list(self.alias_plan),
            is_publish=True,
        )
        self.spaces = self.get_route_spaces()
        for space in self.spaces:
            router.push_space_table_ids(space["space_type_id"], space["space_id"], is_publish=True)
        router.push_data_label_table_ids(bk_tenant_id=self.tenant, table_id_list=list(self.alias_plan), is_publish=True)
        self.source.delete_consul_config()
        self.stdout.write("default 与兼容路由已发布，Transfer 已清理；旧 RT 和存储保留。")

    def check_status(self):
        if not self.default_exists:
            return {
                "phase": "status",
                "bk_data_id": self.source.bk_data_id,
                "ready": False,
                "error": "default 表尚未准备",
            }
        report = super().check_status()
        try:
            report["consumer_groups"] = self.consumer_group_status()
            stored_aliases = {
                option.table_id: option.get_value()
                for option in models.ResultTableOption.objects.filter(
                    bk_tenant_id=self.tenant,
                    table_id__in=self.alias_plan,
                    name=models.ResultTableOption.OPTION_DATA_LABEL_ALIASES,
                    value_type=models.ResultTableOption.TYPE_LIST,
                )
            }
            report["data_label_aliases"] = {
                table_id: {"actual": stored_aliases.get(table_id, []), "expected": aliases}
                for table_id, aliases in self.alias_plan.items()
            }
            report["default_table_alias_route"] = self.redis_values(DATA_LABEL_TO_RESULT_TABLE_KEY, [self.table_id])[
                self.table_id
            ]
            report["split_measurement_enabled"] = bool(
                self.group
                and self.group.is_split_measurement
                and models.ResultTableOption.objects.filter(
                    bk_tenant_id=self.tenant, table_id=self.table_id, name="is_split_measurement", value="true"
                ).exists()
            )
            report["v4_option_enabled"] = models.ResultTableOption.objects.filter(
                bk_tenant_id=self.tenant,
                table_id=self.table_id,
                name="enable_plugin_v4_data_link",
                value="true",
            ).exists()
            report["ready"] = (
                not report.get("error")
                and self.source.created_from == "bkdata"
                and bool(report["components"])
                and all(c["phase"] == "Ok" for c in report["components"])
                and report["v4_option_enabled"]
                and report["split_measurement_enabled"]
                and report["transfer_config_exists"] is False
                and all(
                    all(alias in item["actual"] for alias in item["expected"])
                    for item in report["data_label_aliases"].values()
                )
                and all(self.table_id in (rts or []) for rts in report["data_label_routes"].values())
                and all(
                    table.table_id in (report["default_table_alias_route"] or [])
                    for table in self.legacy_tables
                    if table.is_enable and not table.is_deleted
                )
                and bool((report["result_table_route"] or {}).get("vm_rt"))
                and all(space["contains_default_table"] for space in report["spaces"])
                and bool(report["consumer_groups"])
                and all(g["matches"] for g in report["consumer_groups"])
            )
        except Exception as error:
            report.update(ready=False, error=str(error))
        return report
