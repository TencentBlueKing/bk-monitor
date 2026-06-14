"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig
from constants.common import DEFAULT_TENANT_ID
from metadata.models.custom_report.event import EventGroup
from metadata.models.custom_report.log import LogGroup
from metadata.models.custom_report.subscription_config import CustomReportSubscription
from metadata.models.custom_report.time_series import TimeSeriesGroup


class Command(BaseCommand):
    """
    清理已关闭 collector 配置下发的数据源在 K8S 集群中的配置。

    默认清理中心化集群 CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER；如果指定 --cluster-id，则清理指定集群。
    """

    help = "清理 is_need_deploy_collector_config=False 的配置在 K8S 集群中的 bk-collector Secret 子配置"

    def add_arguments(self, parser):
        parser.add_argument("--bk-tenant-id", default=DEFAULT_TENANT_ID, help="租户 ID，默认 system")
        parser.add_argument("--bk-biz-id", type=int, help="业务 ID，不传则清理所有业务")
        parser.add_argument(
            "--bk-data-id",
            action="append",
            type=int,
            default=[],
            help="数据源 ID，支持传入多次；不传则清理所有匹配的数据源",
        )
        parser.add_argument(
            "--type",
            choices=["all", "event", "time_series", "log"],
            default="all",
            help="清理类型，默认 all",
        )
        parser.add_argument(
            "--cluster-id",
            action="append",
            default=[],
            help="K8S 集群 ID，支持传入多次；不传则默认使用 CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="真正执行清理；不传该参数时仅 dry-run",
        )

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        bk_biz_id = options.get("bk_biz_id")
        bk_data_ids = set(options.get("bk_data_id") or [])
        clean_type = options["type"]
        cluster_ids = self._get_target_cluster_ids(options.get("cluster_id") or [])
        dry_run = not options["execute"]

        if not cluster_ids:
            self.stdout.write("no target k8s cluster configured, skip")
            return

        protocol_to_configs = self._get_disabled_configs(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_ids=bk_data_ids,
            clean_type=clean_type,
        )
        if not protocol_to_configs:
            self.stdout.write("no disabled collector config found, skip")
            return

        self.stdout.write(
            "[{}] clean disabled collector config in k8s cluster, clusters={}, protocols={}".format(
                "DRY-RUN" if dry_run else "EXECUTE",
                sorted(cluster_ids),
                sorted(protocol_to_configs.keys()),
            )
        )
        for protocol, config_infos in sorted(protocol_to_configs.items()):
            config_ids = sorted({config_info["bk_data_id"] for config_info in config_infos})
            self.stdout.write(
                "[{}] protocol={}, config_count={}, config_ids={}".format(
                    "DRY-RUN" if dry_run else "EXECUTE",
                    protocol,
                    len(config_ids),
                    config_ids,
                )
            )
            for config_info in sorted(config_infos, key=lambda item: (item["bk_biz_id"], item["bk_data_id"])):
                self.stdout.write(
                    "  - type={type}, bk_tenant_id={bk_tenant_id}, bk_biz_id={bk_biz_id}, "
                    "bk_data_id={bk_data_id}, group_id={group_id}, group_name={group_name}".format(**config_info)
                )

        total_plan_count = 0
        for cluster_id in sorted(cluster_ids):
            for protocol, config_infos in sorted(protocol_to_configs.items()):
                config_ids = {config_info["bk_data_id"] for config_info in config_infos}
                plans = BkCollectorClusterConfig.clean_sub_configs(
                    cluster_id=cluster_id,
                    protocol=protocol,
                    config_ids=config_ids,
                    dry_run=dry_run,
                )
                total_plan_count += len(plans)
                for plan in plans:
                    self.stdout.write(
                        "[{}] cluster={}, namespace={}, protocol={}, secret={}, action={}, "
                        "config_ids={}, files={}".format(
                            "DRY-RUN" if dry_run else "EXECUTE",
                            plan["cluster_id"],
                            plan["namespace"],
                            plan["protocol"],
                            plan["secret_name"],
                            "delete_secret" if plan["delete_secret"] else "update_secret",
                            plan["config_ids"],
                            plan["sub_config_files"],
                        )
                    )

        self.stdout.write(
            "[{}] clean disabled collector config done, matched_secret_count={}".format(
                "DRY-RUN" if dry_run else "EXECUTE", total_plan_count
            )
        )

    def _get_target_cluster_ids(self, input_cluster_ids: list[str]) -> set[str]:
        if input_cluster_ids:
            return set(input_cluster_ids)
        return set(settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER or [])

    def _get_disabled_configs(
        self,
        bk_tenant_id: str,
        bk_biz_id: int | None,
        bk_data_ids: set[int],
        clean_type: str,
    ) -> dict[str, list[dict]]:
        protocol_to_configs = defaultdict(list)

        if clean_type in {"all", "event"}:
            for event_group in self._get_disabled_event_groups(bk_tenant_id, bk_biz_id, bk_data_ids):
                protocol_to_configs["json"].append(
                    {
                        "type": "event",
                        "bk_tenant_id": event_group.bk_tenant_id,
                        "bk_biz_id": event_group.bk_biz_id,
                        "bk_data_id": event_group.bk_data_id,
                        "group_id": event_group.event_group_id,
                        "group_name": event_group.event_group_name,
                    }
                )

        if clean_type in {"all", "time_series"}:
            for time_series_group in self._get_disabled_time_series_groups(bk_tenant_id, bk_biz_id, bk_data_ids):
                protocol = CustomReportSubscription.get_protocol(time_series_group.bk_data_id)
                protocol_to_configs[protocol].append(
                    {
                        "type": "time_series",
                        "bk_tenant_id": time_series_group.bk_tenant_id,
                        "bk_biz_id": time_series_group.bk_biz_id,
                        "bk_data_id": time_series_group.bk_data_id,
                        "group_id": time_series_group.time_series_group_id,
                        "group_name": time_series_group.time_series_group_name,
                    }
                )

        if clean_type in {"all", "log"}:
            for log_group in self._get_disabled_log_groups(bk_tenant_id, bk_biz_id, bk_data_ids):
                protocol_to_configs["log"].append(
                    {
                        "type": "log",
                        "bk_tenant_id": log_group.bk_tenant_id,
                        "bk_biz_id": log_group.bk_biz_id,
                        "bk_data_id": log_group.bk_data_id,
                        "group_id": log_group.log_group_id,
                        "group_name": log_group.log_group_name,
                    }
                )

        return dict(protocol_to_configs)

    def _get_disabled_event_groups(self, bk_tenant_id: str, bk_biz_id: int | None, bk_data_ids: set[int]):
        qs = EventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_enable=True,
            is_delete=False,
            is_need_deploy_collector_config=False,
        )
        return self._filter_group_queryset(qs, bk_biz_id, bk_data_ids)

    def _get_disabled_time_series_groups(self, bk_tenant_id: str, bk_biz_id: int | None, bk_data_ids: set[int]):
        qs = TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_enable=True,
            is_delete=False,
            is_need_deploy_collector_config=False,
        )
        return self._filter_group_queryset(qs, bk_biz_id, bk_data_ids)

    def _get_disabled_log_groups(self, bk_tenant_id: str, bk_biz_id: int | None, bk_data_ids: set[int]):
        qs = LogGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_enable=True,
            is_delete=False,
            is_need_deploy_collector_config=False,
        )
        return self._filter_group_queryset(qs, bk_biz_id, bk_data_ids)

    def _filter_group_queryset(self, qs, bk_biz_id: int | None, bk_data_ids: set[int]):
        if bk_biz_id is not None:
            qs = qs.filter(bk_biz_id=bk_biz_id)
        if bk_data_ids:
            qs = qs.filter(bk_data_id__in=bk_data_ids)
        return qs
