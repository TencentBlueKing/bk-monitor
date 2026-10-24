"""分阶段迁移已有单指标单表的采集插件，保留旧 RT 查询入口。"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from core.drf_resource import api
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    DataIdConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.utils import reformat_table_id
from metadata.models.vm.utils import create_bkbase_data_link
from metadata.utils.consul_tools import HashConsul
from metadata.utils.redis_tools import RedisTools

PLUGIN_PREFIXES = ("script_", "exporter_", "jmx_", "datadog_", "pushgateway_", "built-in_", "snmp_")
STRATEGIES = {
    "bk_exporter": models.DataLink.BK_EXPORTER_TIME_SERIES,
    "bk_standard": models.DataLink.BK_STANDARD_TIME_SERIES,
}


class Command(BaseCommand):
    help = "迁移单指标单表采集插件到 V4：precheck / pre-run（只读）/ execute / status"

    def add_arguments(self, parser):
        parser.add_argument("phase", choices=["precheck", "pre-run", "execute", "status"])
        parser.add_argument("--bk-tenant-id", required=True)
        parser.add_argument("--bk-data-id", required=True, type=int)
        parser.add_argument("--bk-biz-id", required=True, type=int, help="插件所属业务 ID")
        parser.add_argument("--namespace", default="bkmonitor")
        parser.add_argument("--vm-cluster-name", help="不传时沿用 __default__ 已接入的 VM 集群")
        parser.add_argument("--operator", default="system")

    def handle(self, *args, **options):
        self.tenant = options["bk_tenant_id"]
        self.biz_id = options["bk_biz_id"]
        self.namespace = options["namespace"]
        self.operator = options["operator"]
        try:
            self.load_context(options["bk_data_id"], options.get("vm_cluster_name"))
            if options["phase"] == "status":
                report = self.check_status()
                self.output(report)
                if not report["ready"]:
                    raise CommandError("链路尚未就绪，详见上述组件、Transfer 和查询路由状态")
                return

            errors = self.precheck()
            self.output({"phase": options["phase"], "plan": self.plan(), "errors": errors})
            if errors:
                raise CommandError("前置检查未通过，未执行迁移")
            if options["phase"] != "execute":
                return
            try:
                self.execute_migration()
            except CommandError:
                raise
            except Exception as error:
                raise CommandError(f"迁移中断，可能已执行部分步骤，请用 status 查看后重试：{error}") from error
            report = self.check_status()
            self.output(report)
            if not report["ready"]:
                raise CommandError("迁移配置已提交，链路尚未就绪；请根据 status 输出处理后重试 execute")
        except (models.DataSource.DoesNotExist, models.ClusterInfo.DoesNotExist) as error:
            raise CommandError(str(error)) from error

    def output(self, value):
        self.stdout.write(json.dumps(value, ensure_ascii=False, indent=2))

    def load_context(self, data_id, vm_cluster_name):
        self.source = models.DataSource.objects.get(bk_tenant_id=self.tenant, bk_data_id=data_id)
        try:
            self.topic = self.source.mq_config.topic
        except models.KafkaTopicInfo.DoesNotExist:
            self.topic = ""
        self.table_id = f"{self.source.data_name}.__default__"
        self.table = models.ResultTable.objects.filter(bk_tenant_id=self.tenant, table_id=self.table_id).first()
        self.linked_tables = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=self.tenant, bk_data_id=data_id)
            .order_by("table_id")
            .values_list("table_id", flat=True)
        )
        self.legacy_tables = list(
            models.ResultTable.objects.filter(bk_tenant_id=self.tenant, is_deleted=False, is_enable=True)
            .filter(Q(table_id__in=self.linked_tables) | Q(table_id__startswith=f"{self.source.data_name}."))
            .exclude(table_id=self.table_id)
            .exclude(table_id__endswith="_cmdb_level")
            .order_by("table_id")
            .values_list("table_id", flat=True)
        )
        labels = self.table.data_labels if self.table else []
        labels = [self.source.data_name, *labels]
        self.labels = list(dict.fromkeys([label.strip() for label in labels if label.strip()] + self.legacy_tables))
        self.vm_record = models.AccessVMRecord.objects.filter(
            bk_tenant_id=self.tenant, result_table_id=self.table_id
        ).last()
        clusters = models.ClusterInfo.objects.filter(bk_tenant_id=self.tenant, cluster_type=models.ClusterInfo.TYPE_VM)
        if vm_cluster_name:
            self.cluster = clusters.get(cluster_name=vm_cluster_name)
        else:
            self.cluster = clusters.filter(cluster_id=self.vm_record.vm_cluster_id).first() if self.vm_record else None
        self.spaces = list(
            models.SpaceDataSource.objects.filter(bk_tenant_id=self.tenant, bk_data_id=data_id)
            .values("space_type_id", "space_id")
            .distinct()
        )

    def precheck(self):
        errors = []
        if self.source.etl_config not in STRATEGIES or not self.source.data_name.startswith(PLUGIN_PREFIXES):
            errors.append("仅支持普通采集插件的 bk_exporter / bk_standard 数据源")
        if not self.source.is_enable:
            errors.append("数据源未启用")
        if not self.table:
            errors.append("尚无 __default__ 结果表，请先将插件转换为单指标单表")
        elif not self.table.is_enable or self.table.is_deleted:
            errors.append("__default__ 结果表未启用或已删除")
        elif not models.ResultTableOption.objects.filter(
            bk_tenant_id=self.tenant,
            table_id=self.table_id,
            name=models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT,
            value="true",
        ).exists():
            errors.append("__default__ 尚未启用 is_split_measurement，请先完成单指标单表转换")
        if self.linked_tables != [self.table_id]:
            errors.append("Data ID 仍关联其他写入 RT，请先完成单指标单表转换")
        if not self.cluster:
            errors.append("未找到 __default__ 已接入的 VM 集群，请指定 --vm-cluster-name")
        if not self.topic:
            errors.append("数据源未配置 Kafka Topic")
        if not settings.ENABLE_V2_VM_DATA_LINK:
            errors.append("ENABLE_V2_VM_DATA_LINK 未开启")
        return errors

    def plan(self):
        data_label = ",".join(self.labels)
        sync_data_label = len(data_label) <= models.ResultTable._meta.get_field("data_label").max_length
        return {
            "bk_tenant_id": self.tenant,
            "bk_biz_id": self.biz_id,
            "bk_data_id": self.source.bk_data_id,
            "data_name": self.source.data_name,
            "created_from": self.source.created_from,
            "table_id": self.table_id,
            "legacy_table_ids": self.legacy_tables,
            "data_labels": self.labels,
            "data_label": data_label if sync_data_label else (self.table.data_label if self.table else ""),
            "sync_data_label": sync_data_label,
            "data_label_candidate_length": len(data_label),
            "data_label_max_length": models.ResultTable._meta.get_field("data_label").max_length,
            "namespace": self.namespace,
            "data_link_strategy": STRATEGIES.get(self.source.etl_config),
            "vm_cluster_name": self.cluster.cluster_name if self.cluster else None,
            "topic": self.topic,
            "consumer_group": compose_transfer_consumer_group(self.source) if self.topic else None,
            "transfer_consul_path": self.source.consul_config_path,
            "steps": [
                "将原 Data ID 注册到 BKBase，沿用原 Kafka Topic",
                "申请 V4 链路，沿用 Transfer 消费组和选定的 VM 集群",
                "查询 BKBase 实时组件状态，未就绪时本命令不删除 Transfer 配置",
                "追加旧 RT 查询别名，发布结果表、data_label 和空间路由",
                "删除此 Data ID 的 Transfer Consul 配置",
            ],
        }

    def execute_migration(self):
        self.stdout.write("注册 Data ID 并申请 V4 链路……")
        self.source.register_to_bkbase(bk_biz_id=self.biz_id, namespace=self.namespace, update_created_from=False)
        create_bkbase_data_link(
            bk_biz_id=self.biz_id,
            data_source=self.source,
            monitor_table_id=self.table_id,
            storage_cluster_name=self.cluster.cluster_name,
            data_link_strategy=STRATEGIES[self.source.etl_config],
            namespace=self.namespace,
            consumer_group=compose_transfer_consumer_group(self.source),
        )
        components = self.component_status()
        if not components or any(item["phase"] != DataLinkResourceStatus.OK.value for item in components):
            self.output({"components": components})
            raise CommandError("V4 组件尚未就绪，尚未更新查询别名或删除 Transfer 配置；稍后重试 execute")

        models.ResultTableOption.objects.update_or_create(
            bk_tenant_id=self.tenant,
            table_id=self.table_id,
            name=models.ResultTableOption.OPTION_ENABLE_PLUGIN_V4_DATA_LINK,
            defaults={"value": "true", "value_type": "bool", "creator": self.operator},
        )
        self.table.data_labels = self.labels
        self.table.last_modify_user = self.operator
        self.table.save(update_fields=["data_labels", "last_modify_user", "last_modify_time"])
        self.stdout.write("发布查询别名与路由……")
        router = SpaceTableIDRedis()
        router.push_table_id_detail(
            bk_tenant_id=self.tenant, table_id_list=[self.table_id, *self.legacy_tables], is_publish=True
        )
        router.push_data_label_table_ids(bk_tenant_id=self.tenant, table_id_list=[self.table_id], is_publish=True)
        for space in self.spaces:
            router.push_space_table_ids(space["space_type_id"], space["space_id"], is_publish=True)
        self.source.created_from = DataIdCreatedFromSystem.BKDATA.value
        self.source.save(update_fields=["created_from"])
        self.source.delete_consul_config()
        self.stdout.write("已提交迁移配置，正在检查链路状态……")

    def component_status(self):
        components = list(
            DataIdConfig.objects.filter(
                bk_tenant_id=self.tenant, namespace=self.namespace, bk_data_id=self.source.bk_data_id
            )
        )
        link_names = models.BkBaseResultTable.objects.filter(
            bk_tenant_id=self.tenant, monitor_table_id=self.table_id
        ).values_list("data_link_name", flat=True)
        for model in (ResultTableConfig, VMStorageBindingConfig, DataBusConfig):
            instances = list(
                model.objects.filter(bk_tenant_id=self.tenant, namespace=self.namespace, data_link_name__in=link_names)
            )
            if not instances:
                components.append(model(name="", namespace=self.namespace))
            components.extend(instances)
        result = []
        for component in components:
            item = {"kind": component.kind, "namespace": component.namespace, "name": component.name, "phase": None}
            if not component.name:
                item["error"] = "本地组件记录缺失"
            else:
                try:
                    remote = api.bkdata.get_data_link(
                        bk_tenant_id=self.tenant,
                        kind=DataLinkKind.get_choice_value(component.kind),
                        namespace=component.namespace,
                        name=component.name,
                    )
                    item.update(remote.get("status", {}))
                except Exception as error:
                    item["error"] = str(error)
            result.append(item)
        if not any(item["kind"] == DataIdConfig.kind for item in result):
            result.append({"kind": DataIdConfig.kind, "name": "", "phase": None, "error": "DataId 记录缺失"})
        return result

    def redis_values(self, key, fields):
        redis_fields = [f"{field}|{self.tenant}" for field in fields] if settings.ENABLE_MULTI_TENANT_MODE else fields
        return {
            field: json.loads(value) if value else None
            for field, value in zip(fields, RedisTools.hmget(key, redis_fields))
        }

    def check_status(self):
        self.source.refresh_from_db()
        if self.table:
            self.table.refresh_from_db()
        components = self.component_status()
        report = {
            "phase": "status",
            "bk_tenant_id": self.tenant,
            "bk_data_id": self.source.bk_data_id,
            "created_from": self.source.created_from,
            "components": components,
            "data_label": self.table.data_label if self.table else None,
            "data_labels": self.table.data_labels if self.table else [],
            "ready": False,
        }
        try:
            report["transfer_config_exists"] = HashConsul().get(self.source.consul_config_path)[1] is not None
            aliases = self.redis_values(DATA_LABEL_TO_RESULT_TABLE_KEY, self.labels)
            table_id = reformat_table_id(self.table_id)
            report["data_label_routes"] = aliases
            report["result_table_route"] = self.redis_values(RESULT_TABLE_DETAIL_KEY, [table_id])[table_id]
            space_routes = self.redis_values(
                SPACE_TO_RESULT_TABLE_KEY,
                [f"{space['space_type_id']}__{space['space_id']}" for space in self.spaces],
            )
            report["spaces"] = [
                {
                    **space,
                    "contains_default_table": table_id
                    in (space_routes[f"{space['space_type_id']}__{space['space_id']}"] or {}),
                }
                for space in self.spaces
            ]
            report["ready"] = (
                self.source.created_from == DataIdCreatedFromSystem.BKDATA.value
                and bool(components)
                and all(item["phase"] == DataLinkResourceStatus.OK.value for item in components)
                and set(self.labels).issubset(report["data_labels"])
                and not report["transfer_config_exists"]
                and all(table_id in (tables or []) for tables in aliases.values())
                and bool((report["result_table_route"] or {}).get("vm_rt"))
                and all(space["contains_default_table"] for space in report["spaces"])
            )
        except Exception as error:
            report["error"] = str(error)
        report["data_status"] = "此阶段检查配置与组件状态，不将暂无上报数据判为链路异常"
        return report
