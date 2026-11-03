"""分阶段迁移仅有一个 __default__ RT 的采集插件，不处理多表迁移。"""

import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from bkmonitor.utils.tenant import get_tenant_default_biz_id
from core.drf_resource import api, resource
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
    help = "逐个迁移唯一 RT 为 __default__ 的采集插件到 V4：precheck / pre-run（只读）/ execute / status"

    def add_arguments(self, parser):
        parser.add_argument("phase", choices=["precheck", "pre-run", "execute", "status"])
        parser.add_argument("--bk-tenant-id", required=True)
        data_ids = parser.add_mutually_exclusive_group(required=True)
        data_ids.add_argument("--bk-data-id", type=int, help="单个 DataID")
        data_ids.add_argument("--bk-data-ids", type=int, nargs="+", help="批量 DataID，以空格分隔；单个失败继续后续项")
        parser.add_argument(
            "--bk-biz-id", type=int, help="显式指定目标业务；不传时逐个沿用 modify_result_table 的业务读取逻辑"
        )
        parser.add_argument("--namespace", default="bkmonitor")
        parser.add_argument("--vm-cluster-name", help="不传时沿用 __default__ 已接入的 VM 集群")
        parser.add_argument("--operator", default="system")
        parser.add_argument(
            "--no-wait", action="store_true", help="execute 不等待组件 Ok，申请完成后直接设置 V4 option 并清理 Transfer"
        )
        parser.add_argument("--wait-timeout", type=int, default=300, help="execute 等待组件就绪的最长秒数，默认 300")
        parser.add_argument("--poll-interval", type=int, default=10, help="首次申请后及后续状态检查的间隔秒数，默认 10")
        parser.add_argument(
            "--check-kafka", action="store_true", help="使用 GSE 配置查询 Kafka 尾部，检查是否能查到数据"
        )
        parser.add_argument(
            "--expect-kafka-data",
            choices=["yes", "no"],
            help="预期是否能查到 Kafka 数据；指定即启用检查，结果不符合预期时停止执行",
        )

    def handle(self, *args, **options):
        self.tenant = options["bk_tenant_id"]
        self.namespace = options["namespace"]
        self.operator = options["operator"]
        if options["wait_timeout"] <= 0 or options["poll_interval"] <= 0:
            raise CommandError("--wait-timeout 和 --poll-interval 必须大于 0；不等待请使用 --no-wait")

        if not options.get("bk_data_ids"):
            self.handle_one(options["bk_data_id"], options)
            return

        data_ids = list(dict.fromkeys(options["bk_data_ids"]))
        succeeded = []
        failed = []
        for index, data_id in enumerate(data_ids, start=1):
            self.stdout.write(f"[{index}/{len(data_ids)}] 开始处理 DataID {data_id}……")
            try:
                self.handle_one(data_id, options)
            except Exception as error:
                item = {"bk_data_id": data_id, "error": str(error)}
                failed.append(item)
                self.output({"phase": options["phase"], "success": False, **item})
            else:
                succeeded.append(data_id)

        self.output(
            {
                "phase": options["phase"],
                "batch_summary": {
                    "total": len(data_ids),
                    "succeeded_count": len(succeeded),
                    "failed_count": len(failed),
                    "succeeded_data_ids": succeeded,
                    "failed": failed,
                },
            }
        )
        if failed:
            raise CommandError(f"批量处理完成：成功 {len(succeeded)} 个，失败 {len(failed)} 个，详见汇总")

    def handle_one(self, data_id, options):
        # 每次重新读取业务和当前 DataID 的上下文，避免沿用上一项的业务。
        self.biz_id = options.get("bk_biz_id")
        expected_kafka_data = options.get("expect_kafka_data")
        check_kafka = options.get("check_kafka", False) or expected_kafka_data is not None
        try:
            self.load_context(data_id, options.get("vm_cluster_name"))
            if options["phase"] == "status":
                report = self.check_status()
                if check_kafka:
                    report["kafka_check"] = self.check_kafka_data(expected_kafka_data)
                self.output(report)
                if check_kafka and report["kafka_check"]["error"]:
                    raise CommandError(report["kafka_check"]["error"])
                if not report["ready"]:
                    raise CommandError("链路尚未就绪，详见上述组件、Transfer 和查询路由状态")
                return

            errors = self.precheck()
            if not errors and self.biz_id is None:
                self.biz_id = self.table.get_target_bk_biz_id()
            # 与 access_v2_bkdata_vm 一致，公共插件的链路使用租户默认业务。
            # 保留原业务值，供多表迁移创建 TimeSeriesGroup 使用。
            self.datalink_biz_id = self.biz_id
            if not errors and self.datalink_biz_id == 0:
                self.datalink_biz_id = get_tenant_default_biz_id(self.tenant)
            plan = self.plan()
            plan.update(
                wait_for_components=not options["no_wait"],
                wait_timeout_seconds=options["wait_timeout"],
                poll_interval_seconds=options["poll_interval"],
            )
            report = {"phase": options["phase"], "plan": plan, "errors": errors}
            # 基础检查不通过时不发起 Kafka 查询；直接 execute 也必须经过全部前置检查。
            if check_kafka and not errors:
                report["kafka_check"] = self.check_kafka_data(expected_kafka_data)
                if report["kafka_check"]["error"]:
                    errors.append(report["kafka_check"]["error"])
            self.output(report)
            if errors:
                raise CommandError("前置检查未通过，未执行迁移：" + "；".join(errors))
            if options["phase"] != "execute":
                return
            try:
                self.execute_migration(
                    no_wait=options["no_wait"],
                    wait_timeout=options["wait_timeout"],
                    poll_interval=options["poll_interval"],
                )
            except CommandError:
                raise
            except Exception as error:
                raise CommandError(f"迁移中断，可能已执行部分步骤，请用 status 查看后重试：{error}") from error
            if options["no_wait"]:
                self.output(
                    {
                        "phase": "execute",
                        "bk_tenant_id": self.tenant,
                        "bk_data_id": self.source.bk_data_id,
                        "cutover_completed": True,
                        "components_checked": False,
                        "ready": None,
                        "message": "已设置 V4 option 并清理 Transfer，未检查组件是否 Ok；可另行运行 status 核对",
                    }
                )
                return
            report = self.check_status()
            self.output(report)
            if not report["ready"]:
                raise CommandError("迁移配置已提交，链路尚未就绪；请根据 status 输出处理后重试 execute")
        except (models.DataSource.DoesNotExist, models.ClusterInfo.DoesNotExist) as error:
            raise CommandError(str(error)) from error

    def output(self, value):
        self.stdout.write(json.dumps(value, ensure_ascii=False, indent=2))

    def check_kafka_data(self, expected):
        report = {
            "use_gse_config": True,
            "expected_has_data": None if expected is None else expected == "yes",
            "has_data": None,
            "sample_count": None,
            "error": None,
        }
        try:
            samples = resource.metadata.kafka_tail(
                bk_tenant_id=self.tenant,
                bk_data_id=self.source.bk_data_id,
                size=1,
                use_gse_config=True,
            )
        except Exception as error:
            report["error"] = f"Kafka 数据检查失败：{error}"
            return report
        # 仅按 Resource 是否返回样本判断，不判断消息时间或扩展 GSE 配置检查。
        report.update(has_data=bool(samples), sample_count=len(samples))
        if expected is not None and report["has_data"] != report["expected_has_data"]:
            report["error"] = (
                "预期 Kafka 无数据，但实际查到数据" if expected == "no" else "预期 Kafka 有数据，但实际未查到数据"
            )
        return report

    def load_context(self, data_id, vm_cluster_name):
        self.source = models.DataSource.objects.get(bk_tenant_id=self.tenant, bk_data_id=data_id)
        try:
            self.topic = self.source.mq_config.topic
        except models.KafkaTopicInfo.DoesNotExist:
            self.topic = ""
        self.linked_tables = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=self.tenant, bk_data_id=data_id)
            .order_by("table_id")
            .values_list("table_id", flat=True)
        )
        # 历史 RT 可能已解除 DataID 关联；同插件前缀下的 RT 仍计入多表，包含 CMDB 表及停用表。
        plugin_tables = models.ResultTable.objects.filter(bk_tenant_id=self.tenant).filter(
            Q(table_id__in=self.linked_tables) | Q(table_id__startswith=f"{self.source.data_name}.")
        )
        self.related_tables = sorted(set(self.linked_tables) | set(plugin_tables.values_list("table_id", flat=True)))
        self.table_id = f"{self.source.data_name}.__default__"
        if not self.related_tables:
            self.rt_case = "no_rt"
        elif len(self.related_tables) > 1:
            self.rt_case = "multiple_rts"
        else:
            self.table_id = self.related_tables[0]
            self.rt_case = "single_default_rt" if self.table_id.endswith(".__default__") else "single_non_default_rt"
        self.table = models.ResultTable.objects.filter(bk_tenant_id=self.tenant, table_id=self.table_id).first()
        labels = (self.table.data_label or "").split(",") if self.table else []
        self.labels = list(dict.fromkeys(label.strip() for label in labels if label.strip()))
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
        if self.rt_case == "no_rt":
            return ["未找到 RT，本阶段仅支持唯一 RT 为 __default__ 的插件"]
        if self.rt_case == "multiple_rts":
            return [f"发现 {len(self.related_tables)} 个 RT，本阶段不处理多表插件（包括历史表和 CMDB 表）"]
        if self.rt_case == "single_non_default_rt":
            return [f"唯一 RT 为 {self.table_id}，本阶段仅支持 __default__ 表"]
        errors = []
        if self.source.etl_config not in STRATEGIES or not self.source.data_name.startswith(PLUGIN_PREFIXES):
            errors.append("仅支持普通采集插件的 bk_exporter / bk_standard 数据源")
        if not self.source.is_enable:
            errors.append("数据源未启用")
        if not self.table:
            errors.append("DataID 关联的 __default__ 结果表不存在")
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
            errors.append("Data ID 必须且只能关联此 __default__ 结果表")
        if not self.cluster:
            errors.append("未找到 __default__ 已接入的 VM 集群，请指定 --vm-cluster-name")
        if not self.topic:
            errors.append("数据源未配置 Kafka Topic")
        if not settings.ENABLE_V2_VM_DATA_LINK:
            errors.append("ENABLE_V2_VM_DATA_LINK 未开启")
        return errors

    def plan(self):
        return {
            "bk_tenant_id": self.tenant,
            "bk_biz_id": self.biz_id,
            "datalink_biz_id": self.datalink_biz_id,
            "bk_data_id": self.source.bk_data_id,
            "data_name": self.source.data_name,
            "created_from": self.source.created_from,
            "table_id": self.table_id,
            "rt_case": self.rt_case,
            "related_table_ids": self.related_tables,
            "linked_table_ids": self.linked_tables,
            "data_label": self.table.data_label if self.table else None,
            "namespace": self.namespace,
            "data_link_strategy": STRATEGIES.get(self.source.etl_config),
            "vm_cluster_name": self.cluster.cluster_name if self.cluster else None,
            "topic": self.topic,
            "consumer_group": compose_transfer_consumer_group(self.source) if self.topic else None,
            "transfer_consul_path": self.source.consul_config_path,
            "steps": [
                "查询已有 V4 组件；已有组件记录时不重新注册 Data ID 或 apply 链路",
                "仅首次且无组件记录时注册 Data ID 并申请 V4 链路，沿用原 Kafka Topic、Transfer 消费组和 VM 集群",
                "默认等待组件 Ok；--no-wait 跳过等待及远端状态检查，直接收尾",
                "设置 enable_plugin_v4_data_link=true，保留原有查询路由及 data_label",
                "删除此 Data ID 的 Transfer Consul 配置",
            ],
        }

    def execute_migration(self, *, no_wait=False, wait_timeout=300, poll_interval=10):
        components = self.component_records()
        newly_applied = not any(component.name for component in components)
        if not newly_applied:
            # 重新 apply 会把已就绪组件重置为 Pending；续跑只读状态，不能再次申请。
            self.stdout.write("已有 V4 组件记录，复用已有资源，不重新注册或 apply……")
        else:
            self.stdout.write("首次注册 Data ID 并申请 V4 链路……")
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
            components = self.component_records()
        missing = [component.kind for component in components if not component.name]
        if not components or missing:
            self.output({"missing_components": missing})
            raise CommandError("V4 组件记录不完整，未执行收尾；请先检查缺失组件，不会自动重新 apply")
        if no_wait:
            self.stdout.write("已选择 --no-wait，跳过组件就绪检查，直接设置 V4 option 并清理 Transfer……")
        else:
            self.wait_for_components(
                wait_timeout=wait_timeout, poll_interval=poll_interval, newly_applied=newly_applied
            )

        models.ResultTableOption.objects.update_or_create(
            bk_tenant_id=self.tenant,
            table_id=self.table_id,
            name=models.ResultTableOption.OPTION_ENABLE_PLUGIN_V4_DATA_LINK,
            defaults={"value": "true", "value_type": "bool", "creator": self.operator},
        )
        self.source.delete_consul_config()
        self.stdout.write("已设置 V4 option 并清理 Transfer 配置。")

    def wait_for_components(self, *, wait_timeout, poll_interval, newly_applied):
        deadline = time.monotonic() + wait_timeout
        components = []
        # 新申请的资源先等一个间隔；续跑可直接检查已经就绪的组件。
        if not newly_applied:
            components = self.component_status()
        while True:
            if components and all(item["phase"] == DataLinkResourceStatus.OK.value for item in components):
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.output({"components": components})
                raise CommandError(
                    f"等待 V4 组件就绪超时（{wait_timeout} 秒），未执行收尾；稍后重试 execute 不会重新 apply"
                )
            delay = min(poll_interval, remaining)
            self.stdout.write(f"等待 V4 组件就绪，{delay:g} 秒后检查……")
            time.sleep(delay)
            components = self.component_status()

    def component_records(self):
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
        if not any(component.kind == DataIdConfig.kind for component in components):
            components.append(DataIdConfig(name="", namespace=self.namespace))
        return components

    def component_status(self):
        result = []
        for component in self.component_records():
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
        return result

    def redis_values(self, key, fields):
        if not fields:
            return {}
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
            "rt_case": self.rt_case,
            "related_table_ids": self.related_tables,
            "linked_table_ids": self.linked_tables,
            "components": components,
            "data_label": self.table.data_label if self.table else None,
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
                self.rt_case == "single_default_rt"
                and self.linked_tables == [self.table_id]
                and self.table is not None
                and self.source.created_from == DataIdCreatedFromSystem.BKDATA.value
                and bool(components)
                and all(item["phase"] == DataLinkResourceStatus.OK.value for item in components)
                and set(self.labels).issubset((report["data_label"] or "").split(","))
                and not report["transfer_config_exists"]
                and all(table_id in (tables or []) for tables in aliases.values())
                and bool((report["result_table_route"] or {}).get("vm_rt"))
                and all(space["contains_default_table"] for space in report["spaces"])
            )
        except Exception as error:
            report["error"] = str(error)
        report["data_status"] = "此阶段检查配置与组件状态，不将暂无上报数据判为链路异常"
        return report
