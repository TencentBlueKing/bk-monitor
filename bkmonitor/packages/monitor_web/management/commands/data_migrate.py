"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from monitor_web.data_migrate.data_rebuilder import (
    DEFAULT_ES_CLUSTER_NAMES,
    DEFAULT_KAFKA_CLUSTER_NAMES,
    add_new_migrate_data_id_routes,
    enable_closed_strategies_from_application_config,
    find_biz_custom_report_data_ids,
    rebuild_bklog_data_source_route,
    rebuild_collect_plugins,
    rebuild_custom_report,
    rebuild_dashboard,
    rebuild_k8s_data,
    rebuild_system_data,
    rebuild_uptime_check,
    update_migrate_data_id_routes,
)
from monitor_web.data_migrate.subscription_tasks import stop_biz_subscription_tasks
from monitor_web.data_migrate import (
    PARTIAL_DATA_ID_INFOS_FILE,
    apply_auto_increment_from_directory,
    disable_biz_bk_collector_subscription_auto_inspection,
    disable_models_in_directory,
    export_auto_increment_to_directory,
    export_biz_data_to_directory,
    export_partial_data_to_directory,
    import_biz_data_from_directory,
    import_partial_data_from_directory,
    install_biz_bk_collector,
    load_partial_scope_from_directory,
    make_partial_export_archive,
    replace_cluster_id_in_directory,
    replace_tenant_id_in_directory,
    refresh_biz_bk_collector_proxy_configs,
    retry_biz_bk_collector_proxy_config_delivery,
    rebuild_partial_data,
    repair_plugin_dashboard_result_table_id,
    restore_disabled_models_in_directory,
    sanitize_cluster_info_in_directory,
    stop_biz_bk_collector,
    upload_export_directory_to_storage,
    migrate_builtin_strategy_config,
    migrate_gather_up_strategy_config,
    migrate_system_event_strategy_config,
)
from monitor_web.data_migrate.bk_collector import (
    CONFIG_TYPES as BK_COLLECTOR_CONFIG_TYPES,
    DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL,
    DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT,
    DEFAULT_PLUGIN_JOB_POLL_INTERVAL,
    DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT,
)
from monitor_web.data_migrate.handler.model_disable import MODEL_DISABLE_HANDLERS

FIXED_CLOSE_MODEL_LABELS: tuple[str, ...] = tuple(MODEL_DISABLE_HANDLERS.keys())


class Command(BaseCommand):
    help = "按目录结构导入导出监控业务迁移数据"

    def add_arguments(self, parser):
        parser.formatter_class = argparse.RawTextHelpFormatter
        parser.epilog = (
            "调用示例:\n"
            "  导出业务和全局数据（默认替换租户 ID、关闭模型并上传到制品库）:\n"
            "    python manage.py data_migrate export --directory /tmp/output --bk-biz-ids 2 3 0 --target-tenant-id tenant-a\n"
            "\n"
            "  导出但不上传到制品库:\n"
            "    python manage.py data_migrate export --directory /tmp/output --bk-biz-ids 2 3 0 --target-tenant-id tenant-a --no-upload\n"
            "\n"
            "  导入已解压的导出目录:\n"
            "    python manage.py data_migrate import --directory /tmp/bkmonitor-data-migrate-20260307120000\n"
            "\n"
            "  只导入指定业务和全局数据:\n"
            "    python manage.py data_migrate import --directory /tmp/bkmonitor-data-migrate-20260307120000 --bk-biz-ids 0 2 3\n"
            "\n"
            "  导入时关闭单文件事务:\n"
            "    python manage.py data_migrate import --directory /tmp/bkmonitor-data-migrate-20260307120000 --disable-atomic\n"
            "\n"
            "  通过导出下载链接自动下载、解压并导入:\n"
            "    python manage.py data_migrate import --url https://example.com/data_migrate/export/bkmonitor-data-migrate-20260307120000.tar.gz\n"
            "\n"
            "  导入后按业务执行重建脚本:\n"
            "    python manage.py data_migrate rebuild --bk-tenant-id tencent --bk-biz-ids 18901\n"
            "\n"
            "  导入后按业务执行重建脚本，并单独指定 APM Kafka / ES:\n"
            "    python manage.py data_migrate rebuild --bk-tenant-id tencent --bk-biz-ids 18901 --apm-kafka-cluster-name apm-kafka-public-1 --apm-es-cluster-name apm-es-public-1\n"
            "\n"
            "  查询业务下需要添加双写路由的数据 ID:\n"
            "    python manage.py data_migrate find-custom-report-data-ids --bk-tenant-id tencent --bk-biz-ids 18901\n"
            "\n"
            "  为数据 ID 批量添加迁移双写路由:\n"
            "    python manage.py data_migrate add-migrate-data-id-routes --data-id-infos ./data_id_infos.json\n"
            "\n"
            "  更新单个数据 ID 的迁移双写路由:\n"
            "    python manage.py data_migrate update-migrate-data-id-routes --bk-data-id 123 --kafka-cluster-name kafka_cluster\n"
            "\n"
            "  根据导入阶段记录开启被关闭的策略:\n"
            "    python manage.py data_migrate enable-closed-strategies --bk-biz-ids 18901\n"
            "\n"
            "  恢复自增游标:\n"
            "    python manage.py data_migrate apply-sequences --directory /tmp/bkmonitor-data-migrate-20260307120000\n"
            "\n"
            "  按业务替换 bk_tenant_id:\n"
            '    python manage.py data_migrate replace-tenant-id --directory /tmp/bkmonitor-data-migrate-20260307120000 --biz-tenant-id-map \'{"*":"tenant-a","2":"tenant-b"}\'\n'
            "\n"
            "  替换 cluster_id 引用:\n"
            '    python manage.py data_migrate replace-cluster-id --directory /tmp/bkmonitor-data-migrate-20260307120000 --cluster-id-map \'{"3":10003,"10":10010}\'\n'
            "\n"
            "  脱敏 ClusterInfo 连接配置:\n"
            "    python manage.py data_migrate sanitize-cluster-info --directory /tmp/bkmonitor-data-migrate-20260307120000\n"
            "\n"
            "  按模型关闭数据:\n"
            "    python manage.py data_migrate disable-models --directory /tmp/bkmonitor-data-migrate-20260307120000 --models monitor_web.CollectConfigMeta\n"
            "\n"
            "  恢复最近一次按模型关闭的数据:\n"
            "    python manage.py data_migrate restore-disabled-models --directory /tmp/bkmonitor-data-migrate-20260307120000\n"
            "\n"
            "  停用业务下拨测、插件采集和 k8s 采集任务:\n"
            "    python manage.py data_migrate stop-biz-subscription-tasks --bk-tenant-id tencent --bk-biz-ids 18901 --operator admin\n"
            "\n"
            "  为业务下 proxy 安装 bk-collector:\n"
            "    python manage.py data_migrate install-biz-bk-collector --bk-tenant-id tencent --bk-biz-ids 18901 --operator admin\n"
            "\n"
            "  禁用业务下 bk-collector 相关订阅自动巡检并加入新环境业务黑名单:\n"
            "    python manage.py data_migrate disable-biz-bk-collector-subscription-checks --bk-tenant-id system --bk-biz-ids 18901 --operator admin\n"
            "\n"
            "  停止业务下 proxy 上的 bk-collector:\n"
            "    python manage.py data_migrate stop-biz-bk-collector --bk-tenant-id tencent --bk-biz-ids 18901 --operator admin\n"
            "\n"
            "  触发业务下 proxy 的 bk-collector 配置下发:\n"
            "    python manage.py data_migrate refresh-biz-bk-collector-configs --bk-tenant-id tencent --bk-biz-ids 18901 --config-types apm_application custom_report log\n"
            "\n"
            "  对 render 失败的 bk-collector proxy 配置订阅补一轮下发:\n"
            "    python manage.py data_migrate retry-biz-bk-collector-config-delivery --bk-tenant-id tencent --bk-biz-ids 18901 --config-types apm_application custom_report log\n"
            "\n"
            "  迁移存量系统事件策略到多租户 custom event 链路:\n"
            "    python manage.py data_migrate migrate-system-event-strategies --bk-biz-ids 18901 --dry-run\n"
            "\n"
            "  迁移存量 gather_up 采集状态策略到多租户 data_label 引用:\n"
            "    python manage.py data_migrate migrate-gather-up-strategies --bk-biz-ids 18901 --dry-run\n"
            "\n"
            "  统一迁移全部内置策略（系统事件 + gather_up 采集状态）:\n"
            "    python manage.py data_migrate migrate-builtin-strategies --bk-biz-ids 18901 --dry-run\n"
            "\n"
            "  修复仪表盘中插件类指标的旧 result_table_id:\n"
            "    python manage.py data_migrate repair-plugin-dashboard-result-table --bk-biz-ids 18901 --dry-run\n"
            "\n"
            "  局部导出指定 BCS 集群、自定义上报 Data ID 和 APM 应用:\n"
            "    python manage.py data_migrate partial-export --directory /tmp/output --bk-tenant-id tencent --bk-biz-id 18901 --bcs-cluster-ids BCS-K8S-00000 --custom-report-data-ids 123 456 --app-names demo-app\n"
            "\n"
            "  局部导入，导入前会检查 bk_data_id/data_name/table_id/time_series_group_name 等关键冲突:\n"
            "    python manage.py data_migrate partial-import --directory /tmp/bkmonitor-partial-data-migrate-20260307120000\n"
            "\n"
            "  局部重建指定范围的数据链路:\n"
            "    python manage.py data_migrate partial-rebuild --bk-tenant-id tencent --bk-biz-id 18901 --app-names demo-app --event-kafka-cluster-name log-kafka-public-1"
        )
        parser.add_argument(
            "action",
            choices=[
                "export",
                "import",
                "rebuild",
                "find-custom-report-data-ids",
                "add-migrate-data-id-routes",
                "update-migrate-data-id-routes",
                "enable-closed-strategies",
                "apply-sequences",
                "replace-tenant-id",
                "replace-cluster-id",
                "sanitize-cluster-info",
                "disable-models",
                "restore-disabled-models",
                "stop-biz-subscription-tasks",
                "install-biz-bk-collector",
                "disable-biz-bk-collector-subscription-checks",
                "stop-biz-bk-collector",
                "refresh-biz-bk-collector-configs",
                "retry-biz-bk-collector-config-delivery",
                "migrate-system-event-strategies",
                "migrate-gather-up-strategies",
                "migrate-builtin-strategies",
                "repair-plugin-dashboard-result-table",
                "partial-export",
                "partial-import",
                "partial-rebuild",
            ],
            help="执行导出、导入、恢复游标或 handler 处理",
        )
        parser.add_argument("--directory", help="导出 zip 输出目录，或已解压的导入目录")
        parser.add_argument("--url", help="导入压缩包下载地址；仅 import 动作可用")
        parser.add_argument(
            "--bk-biz-ids",
            nargs="+",
            type=int,
            help=(
                "业务 ID 列表；export/import 中 0 代表全局数据；"
                "rebuild 支持正数和负数业务 ID，负数业务会跳过内置系统数据、拨测和采集插件重建；"
                "find-custom-report-data-ids 支持正数和负数业务 ID；"
                "enable-closed-strategies 支持正数和负数业务 ID；"
                "stop-biz-subscription-tasks 会跳过负数业务 ID；"
                "migrate-system-event-strategies/migrate-gather-up-strategies/migrate-builtin-strategies "
                "不传时扫描全量策略；repair-plugin-dashboard-result-table 不传时扫描全量仪表盘"
            ),
        )
        parser.add_argument(
            "--bk-biz-id",
            type=int,
            help="单个业务 ID；仅 partial-export、partial-import、partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--format", default="json", help="导出文件格式，默认 json；仅 export/partial-export 动作需要"
        )
        parser.add_argument(
            "--indent", type=int, default=2, help="导出文件缩进，默认 2；仅 export/partial-export 动作需要"
        )
        parser.add_argument(
            "--target-tenant-id",
            help="导出目标租户 ID；仅 export/partial-export 动作需要，导出后执行租户 ID 替换",
        )
        parser.add_argument(
            "--disable-atomic",
            action="store_true",
            help="导入时关闭按单文件事务处理；仅 import 动作需要",
        )
        parser.add_argument("--bk-tenant-id", help="租户 ID；仅 rebuild、partial-export、partial-rebuild 动作需要")
        parser.add_argument(
            "--bcs-cluster-ids",
            nargs="+",
            help="BCS 集群 ID 列表；仅 partial-export、partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--custom-report-data-ids",
            nargs="+",
            type=int,
            help="自定义上报 Data ID 列表；仅 partial-export、partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--app-names",
            nargs="+",
            help="APM 应用名列表；仅 partial-export、partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--biz-tenant-id-map",
            help='租户替换映射 JSON，形如 \'{"*":"tenant-a","2":"tenant-b"}\'；仅 replace-tenant-id 动作需要',
        )
        parser.add_argument(
            "--cluster-id-map",
            help='集群 ID 替换映射 JSON，形如 \'{"3":10003,"10":10010}\'；仅 replace-cluster-id 动作需要',
        )
        parser.add_argument(
            "--no-upload",
            action="store_true",
            help="导出时跳过上传到制品库；仅 export/partial-export 动作需要",
        )
        parser.add_argument(
            "--models",
            nargs="+",
            help="需要关闭的模型列表，形如 monitor_web.CollectConfigMeta；仅 disable-models 动作需要",
        )
        parser.add_argument(
            "--metric-kafka-cluster-name",
            default=DEFAULT_KAFKA_CLUSTER_NAMES["metric"],
            help="指标 Kafka 集群名称；仅 rebuild/partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--log-kafka-cluster-name",
            default=DEFAULT_KAFKA_CLUSTER_NAMES["event"],
            help="日志 Kafka 集群名称；仅 rebuild/partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--event-kafka-cluster-name",
            default=DEFAULT_KAFKA_CLUSTER_NAMES["event"],
            help="事件 Kafka 集群名称；仅 rebuild/partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--log-es-cluster-name",
            default=DEFAULT_ES_CLUSTER_NAMES["log"],
            help="日志 ES 集群名称；仅 rebuild/partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--event-es-cluster-name",
            default=DEFAULT_ES_CLUSTER_NAMES["event"],
            help="事件 ES 集群名称；仅 rebuild/partial-rebuild 动作需要",
        )
        parser.add_argument(
            "--apm-kafka-cluster-name",
            help=(
                "APM Kafka 集群名称；仅 rebuild/partial-rebuild 动作需要。"
                "为空时保持原有逻辑：APM trace/log 使用日志 Kafka，APM metric 使用指标 Kafka"
            ),
        )
        parser.add_argument(
            "--apm-es-cluster-name",
            help="APM trace/log ES 集群名称；仅 rebuild/partial-rebuild 动作需要。为空时保持原有逻辑：使用日志 ES",
        )
        parser.add_argument(
            "--data-id-infos",
            help="数据 ID 信息 JSON 或 JSON 文件路径；仅 add-migrate-data-id-routes 动作需要",
        )
        parser.add_argument("--bk-data-id", type=int, help="数据 ID；仅 update-migrate-data-id-routes 动作需要")
        parser.add_argument(
            "--kafka-cluster-name",
            help="迁移前 Kafka 集群名称；仅 update-migrate-data-id-routes 动作需要",
        )
        parser.add_argument(
            "--operator",
            default="system",
            help=(
                "操作人；仅 stop-biz-subscription-tasks、install-biz-bk-collector、"
                "disable-biz-bk-collector-subscription-checks、stop-biz-bk-collector、"
                "refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery 动作需要"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "仅预览不执行；仅 stop-biz-subscription-tasks、install-biz-bk-collector、"
                "disable-biz-bk-collector-subscription-checks、stop-biz-bk-collector、"
                "refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery、"
                "migrate-system-event-strategies、repair-plugin-dashboard-result-table 动作需要"
            ),
        )
        parser.add_argument(
            "--job-wait-timeout",
            type=int,
            default=DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT,
            help="等待节点管理插件任务完成的超时时间，单位秒；仅 install-biz-bk-collector、stop-biz-bk-collector 动作需要",
        )
        parser.add_argument(
            "--job-poll-interval",
            type=int,
            default=DEFAULT_PLUGIN_JOB_POLL_INTERVAL,
            help="轮询节点管理插件任务状态的间隔，单位秒；仅 install-biz-bk-collector、stop-biz-bk-collector 动作需要",
        )
        parser.add_argument(
            "--skip-hosts-without-agent",
            action=argparse.BooleanOptionalAction,
            default=None,
            help=(
                "执行前是否检查主机 Agent 状态并跳过 Agent 未安装的主机；"
                "install-biz-bk-collector 默认不跳过，stop-biz-bk-collector 默认跳过；"
                "可用 --skip-hosts-without-agent / --no-skip-hosts-without-agent 显式覆盖"
            ),
        )
        parser.add_argument(
            "--config-types",
            nargs="+",
            choices=BK_COLLECTOR_CONFIG_TYPES,
            help=(
                "需要刷新/重试的 bk-collector 配置类型；"
                "仅 refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery 动作需要"
            ),
        )
        parser.add_argument(
            "--skip-delivery-check",
            action="store_true",
            help="刷新 bk-collector proxy 配置后跳过节点管理配置下发状态检查；仅 refresh-biz-bk-collector-configs 动作需要",
        )
        parser.add_argument(
            "--skip-delivery-recheck",
            action="store_true",
            help=("补一轮下发后跳过节点管理配置下发状态复检；仅 retry-biz-bk-collector-config-delivery 动作需要"),
        )
        parser.add_argument(
            "--skip-render-failure-retry",
            action="store_true",
            help=("刷新并检查配置下发后跳过对 render 失败订阅的自动补发；仅 refresh-biz-bk-collector-configs 动作需要"),
        )
        parser.add_argument(
            "--include-details",
            action="store_true",
            help=(
                "输出完整 details；仅 refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery 动作需要"
            ),
        )
        parser.add_argument(
            "--delivery-wait-timeout",
            type=int,
            default=DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT,
            help=(
                "等待 bk-collector proxy 配置渲染下发完成的超时时间，单位秒；"
                "仅 refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery 动作需要"
            ),
        )
        parser.add_argument(
            "--delivery-poll-interval",
            type=int,
            default=DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL,
            help=(
                "轮询 bk-collector proxy 配置渲染下发状态的间隔，单位秒；"
                "仅 refresh-biz-bk-collector-configs、retry-biz-bk-collector-config-delivery 动作需要"
            ),
        )

    def handle(self, *args, **options):
        action = options["action"]
        handlers = {
            "export": self._handle_export,
            "import": self._handle_import,
            "rebuild": self._handle_rebuild,
            "find-custom-report-data-ids": self._handle_find_custom_report_data_ids,
            "add-migrate-data-id-routes": self._handle_add_migrate_data_id_routes,
            "update-migrate-data-id-routes": self._handle_update_migrate_data_id_routes,
            "enable-closed-strategies": self._handle_enable_closed_strategies,
            "apply-sequences": self._handle_apply_sequences,
            "replace-tenant-id": self._handle_replace_tenant_id,
            "replace-cluster-id": self._handle_replace_cluster_id,
            "sanitize-cluster-info": self._handle_sanitize_cluster_info,
            "disable-models": self._handle_disable_models,
            "restore-disabled-models": self._handle_restore_disabled_models,
            "stop-biz-subscription-tasks": self._handle_stop_biz_subscription_tasks,
            "install-biz-bk-collector": self._handle_install_biz_bk_collector,
            "disable-biz-bk-collector-subscription-checks": (self._handle_disable_biz_bk_collector_subscription_checks),
            "stop-biz-bk-collector": self._handle_stop_biz_bk_collector,
            "refresh-biz-bk-collector-configs": self._handle_refresh_biz_bk_collector_configs,
            "retry-biz-bk-collector-config-delivery": self._handle_retry_biz_bk_collector_config_delivery,
            "migrate-system-event-strategies": self._handle_migrate_system_event_strategies,
            "migrate-gather-up-strategies": self._handle_migrate_gather_up_strategies,
            "migrate-builtin-strategies": self._handle_migrate_builtin_strategies,
            "repair-plugin-dashboard-result-table": self._handle_repair_plugin_dashboard_result_table,
            "partial-export": self._handle_partial_export,
            "partial-import": self._handle_partial_import,
            "partial-rebuild": self._handle_partial_rebuild,
        }
        handlers[action](options)

    def _handle_export(self, options):
        bk_biz_ids = options.get("bk_biz_ids") or []
        if not bk_biz_ids:
            raise CommandError("export 动作必须提供 --bk-biz-ids")
        target_tenant_id = self._load_target_tenant_id(options.get("target_tenant_id"))

        output_directory = self._load_directory(options, action_name="export")
        output_directory.mkdir(parents=True, exist_ok=True)
        archive_name = f"bkmonitor-data-migrate-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        skip_upload = options.get("no_upload", False)

        with tempfile.TemporaryDirectory(prefix="bkmonitor-data-migrate-") as temp_directory:
            export_directory = Path(temp_directory) / archive_name
            export_biz_data_to_directory(
                directory_path=export_directory,
                bk_biz_ids=bk_biz_ids,
                format=options["format"],
                indent=options["indent"],
            )
            export_auto_increment_to_directory(export_directory)
            replace_tenant_id_in_directory(
                directory_path=export_directory,
                biz_tenant_id_map=self._build_export_biz_tenant_id_map(target_tenant_id),
            )
            disable_models_in_directory(
                directory_path=export_directory,
                model_labels=list(FIXED_CLOSE_MODEL_LABELS),
            )

            if not skip_upload:
                download_url = upload_export_directory_to_storage(export_directory)
                self.stdout.write(self.style.SUCCESS(f"upload completed, download_url: {download_url}"))

            archive_path = shutil.make_archive(
                base_name=str(Path(temp_directory) / archive_name),
                format="zip",
                root_dir=temp_directory,
                base_dir=archive_name,
            )
            target_archive_path = output_directory / f"{archive_name}.zip"
            if target_archive_path.exists():
                target_archive_path.unlink()
            shutil.move(archive_path, target_archive_path)

        self.stdout.write(self.style.SUCCESS(f"export completed: {target_archive_path}"))

    def _handle_import(self, options):
        import_url = options.get("url")
        if import_url:
            if options.get("directory"):
                raise CommandError("import 动作不能同时提供 --directory 和 --url")
            with tempfile.TemporaryDirectory(prefix="bkmonitor-data-migrate-import-") as temp_directory:
                extracted_directory = self._download_and_unpack_import_archive(
                    archive_url=import_url,
                    target_root=Path(temp_directory),
                )
                self._import_from_directory(extracted_directory, options)
                self.stdout.write(self.style.SUCCESS(f"import completed: {extracted_directory}"))
            return

        directory = self._load_directory(options, action_name="import")
        self._import_from_directory(directory, options)
        self.stdout.write(self.style.SUCCESS(f"import completed: {directory}"))

    def _handle_partial_export(self, options):
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="partial-export")
        bk_biz_id = self._load_bk_biz_id(options.get("bk_biz_id"), action_name="partial-export")
        selectors = self._load_partial_selectors(options, action_name="partial-export")
        output_directory = self._load_directory(options, action_name="partial-export")
        output_directory.mkdir(parents=True, exist_ok=True)
        archive_name = f"bkmonitor-partial-data-migrate-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        target_tenant_id = self._load_optional_tenant_id(options.get("target_tenant_id"))

        with tempfile.TemporaryDirectory(prefix="bkmonitor-partial-data-migrate-") as temp_directory:
            export_directory = Path(temp_directory) / archive_name
            export_partial_data_to_directory(
                directory_path=export_directory,
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                format=options["format"],
                indent=options["indent"],
                **selectors,
            )
            export_auto_increment_to_directory(export_directory)
            if target_tenant_id:
                replace_tenant_id_in_directory(
                    directory_path=export_directory,
                    biz_tenant_id_map=self._build_export_biz_tenant_id_map(target_tenant_id),
                )
                self._rewrite_partial_manifest_tenant_id(export_directory, target_tenant_id)
            disable_models_in_directory(
                directory_path=export_directory,
                model_labels=list(FIXED_CLOSE_MODEL_LABELS),
            )

            if not options.get("no_upload", False):
                download_url = upload_export_directory_to_storage(export_directory)
                self.stdout.write(self.style.SUCCESS(f"upload completed, download_url: {download_url}"))

            target_archive_path = make_partial_export_archive(
                export_directory=export_directory,
                output_directory=output_directory,
            )

        self.stdout.write(self.style.SUCCESS(f"partial export completed: {target_archive_path}"))

    def _handle_partial_import(self, options):
        directory = self._load_directory(options, action_name="partial-import")
        bk_biz_id = (
            self._load_bk_biz_id(options.get("bk_biz_id"), action_name="partial-import")
            if options.get("bk_biz_id") is not None
            else None
        )
        bk_biz_ids = [bk_biz_id] if bk_biz_id is not None else None
        try:
            result = import_partial_data_from_directory(
                directory_path=directory,
                bk_biz_ids=bk_biz_ids,
                atomic=not options["disable_atomic"],
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS(f"partial import completed: {directory}"))

    def _handle_partial_rebuild(self, options):
        partial_scope = self._load_partial_scope_from_options(options)
        bk_tenant_id = self._load_bk_tenant_id(
            options.get("bk_tenant_id") or partial_scope.get("bk_tenant_id"),
            action_name="partial-rebuild",
        )
        bk_biz_id = self._load_bk_biz_id(
            options.get("bk_biz_id") or partial_scope.get("bk_biz_id"),
            action_name="partial-rebuild",
        )
        selectors = self._load_partial_selectors(
            options,
            action_name="partial-rebuild",
            partial_scope=partial_scope,
        )
        result = rebuild_partial_data(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            metric_kafka_cluster_name=options["metric_kafka_cluster_name"],
            log_kafka_cluster_name=options["log_kafka_cluster_name"],
            event_kafka_cluster_name=options["event_kafka_cluster_name"],
            log_es_cluster_name=options["log_es_cluster_name"],
            event_es_cluster_name=options["event_es_cluster_name"],
            apm_kafka_cluster_name=self._load_optional_cluster_name(options.get("apm_kafka_cluster_name")),
            apm_es_cluster_name=self._load_optional_cluster_name(options.get("apm_es_cluster_name")),
            **selectors,
        )
        self._write_partial_data_id_infos(options, result)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS(f"partial rebuild completed: bk_biz_id={bk_biz_id}"))

    def _handle_rebuild(self, options):
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="rebuild")
        bk_biz_ids = self._load_non_zero_biz_ids(options.get("bk_biz_ids"), action_name="rebuild")
        metric_kafka_cluster_name = options["metric_kafka_cluster_name"]
        log_kafka_cluster_name = options["log_kafka_cluster_name"]
        event_kafka_cluster_name = options["event_kafka_cluster_name"]
        log_es_cluster_name = options["log_es_cluster_name"]
        event_es_cluster_name = options["event_es_cluster_name"]
        apm_kafka_cluster_name = self._load_optional_cluster_name(options.get("apm_kafka_cluster_name"))
        apm_es_cluster_name = self._load_optional_cluster_name(options.get("apm_es_cluster_name"))

        self.stdout.write(
            self.style.SUCCESS(
                "rebuild initialized: "
                f"bk_tenant_id={bk_tenant_id}, bk_biz_ids={bk_biz_ids}, "
                f"metric_kafka_cluster_name={metric_kafka_cluster_name}, "
                f"log_kafka_cluster_name={log_kafka_cluster_name}, "
                f"event_kafka_cluster_name={event_kafka_cluster_name}, "
                f"log_es_cluster_name={log_es_cluster_name}, "
                f"event_es_cluster_name={event_es_cluster_name}, "
                f"apm_kafka_cluster_name={apm_kafka_cluster_name}, "
                f"apm_es_cluster_name={apm_es_cluster_name}"
            )
        )

        for bk_biz_id in bk_biz_ids:
            is_negative_biz = bk_biz_id < 0
            self.stdout.write(self.style.SUCCESS(f"rebuild started: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild dashboard started: bk_biz_id={bk_biz_id}"))
            rebuild_dashboard(bk_biz_id)
            self.stdout.write(self.style.SUCCESS(f"rebuild dashboard completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild bklog data source route started: bk_biz_id={bk_biz_id}"))
            rebuild_bklog_data_source_route(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=log_kafka_cluster_name,
                es_cluster_name=log_es_cluster_name,
                apm_kafka_cluster_name=apm_kafka_cluster_name,
                apm_es_cluster_name=apm_es_cluster_name,
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild bklog data source route completed: bk_biz_id={bk_biz_id}"))
            if is_negative_biz:
                self.stdout.write(
                    self.style.WARNING(
                        f"rebuild system data skipped: bk_biz_id={bk_biz_id}, "
                        "reason=negative biz id has no bkcc builtin datalink"
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"rebuild uptime check skipped: bk_biz_id={bk_biz_id}, "
                        "reason=negative biz id has no uptime check tasks"
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"rebuild collect plugins skipped: bk_biz_id={bk_biz_id}, "
                        "reason=negative biz id has no collect configs"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"rebuild system data started: bk_biz_id={bk_biz_id}"))
                rebuild_system_data(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
                self.stdout.write(self.style.SUCCESS(f"rebuild system data completed: bk_biz_id={bk_biz_id}"))
                self.stdout.write(self.style.SUCCESS(f"rebuild uptime check started: bk_biz_id={bk_biz_id}"))
                rebuild_uptime_check(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
                self.stdout.write(self.style.SUCCESS(f"rebuild uptime check completed: bk_biz_id={bk_biz_id}"))
                self.stdout.write(self.style.SUCCESS(f"rebuild collect plugins started: bk_biz_id={bk_biz_id}"))
                rebuild_collect_plugins(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    kafka_cluster_names={
                        "metric": metric_kafka_cluster_name,
                        "event": event_kafka_cluster_name,
                    },
                    es_cluster_names={"event": event_es_cluster_name},
                )
                self.stdout.write(self.style.SUCCESS(f"rebuild collect plugins completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild k8s data started: bk_biz_id={bk_biz_id}"))
            rebuild_k8s_data(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                metric_kafka_cluster_name=metric_kafka_cluster_name,
                event_kafka_cluster_name=event_kafka_cluster_name,
                es_cluster_name=event_es_cluster_name,
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild k8s data completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild custom report started: bk_biz_id={bk_biz_id}"))
            rebuild_custom_report(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                metric_kafka_cluster_name=metric_kafka_cluster_name,
                event_kafka_cluster_name=event_kafka_cluster_name,
                es_cluster_name=event_es_cluster_name,
                apm_kafka_cluster_name=apm_kafka_cluster_name,
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild custom report completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild completed: bk_biz_id={bk_biz_id}"))

    def _handle_find_custom_report_data_ids(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="find-custom-report-data-ids")
        bk_biz_ids = self._load_non_zero_biz_ids(options.get("bk_biz_ids"), action_name="find-custom-report-data-ids")
        data_id_infos = find_biz_custom_report_data_ids(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids)
        self.stdout.write(json.dumps(data_id_infos, ensure_ascii=False, indent=2, sort_keys=True))

    def _handle_add_migrate_data_id_routes(self, options) -> None:
        data_id_infos = self._load_data_id_infos(options.get("data_id_infos"))
        if not data_id_infos:
            self.stdout.write(self.style.WARNING("未找到可用的数据 ID 信息，已跳过添加迁移双写路由"))
            return
        add_new_migrate_data_id_routes(data_id_infos=data_id_infos)
        self.stdout.write(self.style.SUCCESS(f"add migrate data id routes completed: {len(data_id_infos)}"))

    def _handle_update_migrate_data_id_routes(self, options) -> None:
        bk_data_id = self._load_bk_data_id(options.get("bk_data_id"), action_name="update-migrate-data-id-routes")
        kafka_cluster_name = self._load_kafka_cluster_name(
            options.get("kafka_cluster_name"),
            action_name="update-migrate-data-id-routes",
        )
        route_changes = update_migrate_data_id_routes({bk_data_id: kafka_cluster_name})
        self.stdout.write(json.dumps(route_changes, ensure_ascii=False, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS(f"update migrate data id routes completed: {len(route_changes)}"))

    def _handle_enable_closed_strategies(self, options) -> None:
        bk_biz_ids = self._load_non_zero_biz_ids(options.get("bk_biz_ids"), action_name="enable-closed-strategies")
        enable_results = enable_closed_strategies_from_application_config(bk_biz_ids=bk_biz_ids)
        self.stdout.write(json.dumps(enable_results, ensure_ascii=False, indent=2, sort_keys=True))
        enabled_count = sum(result["enabled_count"] for result in enable_results.values())
        self.stdout.write(self.style.SUCCESS(f"enable closed strategies completed: {enabled_count}"))

    def _handle_apply_sequences(self, options):
        directory = self._load_directory(options, action_name="apply-sequences")
        apply_auto_increment_from_directory(
            directory_path=directory,
        )
        self.stdout.write(self.style.SUCCESS(f"apply sequences completed: {directory}"))

    def _handle_replace_tenant_id(self, options):
        directory = self._load_directory(options, action_name="replace-tenant-id")
        biz_tenant_id_map = self._load_biz_tenant_id_map(options.get("biz_tenant_id_map"))
        replace_tenant_id_in_directory(
            directory_path=directory,
            biz_tenant_id_map=biz_tenant_id_map,
        )
        self.stdout.write(self.style.SUCCESS(f"replace tenant id completed: {directory}"))

    def _handle_replace_cluster_id(self, options):
        directory = self._load_directory(options, action_name="replace-cluster-id")
        cluster_id_map = self._load_cluster_id_map(options.get("cluster_id_map"))
        replace_cluster_id_in_directory(
            directory_path=directory,
            cluster_id_map=cluster_id_map,
        )
        self.stdout.write(self.style.SUCCESS(f"replace cluster id completed: {directory}"))

    def _handle_sanitize_cluster_info(self, options):
        directory = self._load_directory(options, action_name="sanitize-cluster-info")
        sanitize_cluster_info_in_directory(
            directory_path=directory,
        )
        self.stdout.write(self.style.SUCCESS(f"sanitize cluster info completed: {directory}"))

    def _handle_disable_models(self, options):
        directory = self._load_directory(options, action_name="disable-models")
        model_labels = options.get("models") or list(MODEL_DISABLE_HANDLERS.keys())
        if not model_labels:
            raise CommandError("disable-models 动作必须提供 --models")
        try:
            disable_models_in_directory(
                directory_path=directory,
                model_labels=model_labels,
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"disable models completed: {directory}"))

    def _handle_restore_disabled_models(self, options):
        directory = self._load_directory(options, action_name="restore-disabled-models")
        try:
            restore_disabled_models_in_directory(
                directory_path=directory,
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"restore disabled models completed: {directory}"))

    def _handle_stop_biz_subscription_tasks(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="stop-biz-subscription-tasks")
        bk_biz_ids = self._load_non_zero_biz_ids(options.get("bk_biz_ids"), action_name="stop-biz-subscription-tasks")
        operator = self._load_operator(options.get("operator"), action_name="stop-biz-subscription-tasks")
        result = stop_biz_subscription_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=bk_biz_ids,
            operator=operator,
            dry_run=options.get("dry_run", False),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        failed_count = result["summary"]["total"]["failed_count"]
        if failed_count:
            self.stdout.write(
                self.style.WARNING(f"stop biz subscription tasks completed with failures: {failed_count}")
            )
        else:
            self.stdout.write(self.style.SUCCESS("stop biz subscription tasks completed"))

    def _handle_install_biz_bk_collector(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="install-biz-bk-collector")
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name="install-biz-bk-collector")
        operator = self._load_operator(options.get("operator"), action_name="install-biz-bk-collector")
        result = install_biz_bk_collector(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=bk_biz_ids,
            operator=operator,
            dry_run=options.get("dry_run", False),
            job_wait_timeout=options.get("job_wait_timeout", DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT),
            job_poll_interval=options.get("job_poll_interval", DEFAULT_PLUGIN_JOB_POLL_INTERVAL),
            skip_hosts_without_agent=self._resolve_skip_hosts_without_agent(options, default=False),
        )
        self._write_report_result(
            result,
            success_message="install biz bk-collector completed",
            warning_message="install biz bk-collector completed with failures",
        )

    def _handle_disable_biz_bk_collector_subscription_checks(self, options) -> None:
        action_name = "disable-biz-bk-collector-subscription-checks"
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name=action_name)
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name=action_name)
        operator = self._load_operator(options.get("operator"), action_name=action_name)
        result = disable_biz_bk_collector_subscription_auto_inspection(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=bk_biz_ids,
            operator=operator,
            dry_run=options.get("dry_run", False),
        )
        self._write_report_result(
            result,
            success_message="disable biz bk-collector subscription checks completed",
            warning_message="disable biz bk-collector subscription checks completed with failures",
        )

    def _handle_stop_biz_bk_collector(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="stop-biz-bk-collector")
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name="stop-biz-bk-collector")
        operator = self._load_operator(options.get("operator"), action_name="stop-biz-bk-collector")
        result = stop_biz_bk_collector(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=bk_biz_ids,
            operator=operator,
            dry_run=options.get("dry_run", False),
            job_wait_timeout=options.get("job_wait_timeout", DEFAULT_PLUGIN_JOB_WAIT_TIMEOUT),
            job_poll_interval=options.get("job_poll_interval", DEFAULT_PLUGIN_JOB_POLL_INTERVAL),
            skip_hosts_without_agent=self._resolve_skip_hosts_without_agent(options, default=True),
        )
        self._write_report_result(
            result,
            success_message="stop biz bk-collector completed",
            warning_message="stop biz bk-collector completed with failures",
        )

    def _handle_refresh_biz_bk_collector_configs(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(
            options.get("bk_tenant_id"), action_name="refresh-biz-bk-collector-configs"
        )
        bk_biz_ids = self._load_positive_biz_ids(
            options.get("bk_biz_ids"), action_name="refresh-biz-bk-collector-configs"
        )
        operator = self._load_operator(options.get("operator"), action_name="refresh-biz-bk-collector-configs")
        try:
            result = refresh_biz_bk_collector_proxy_configs(
                bk_tenant_id=bk_tenant_id,
                bk_biz_ids=bk_biz_ids,
                config_types=options.get("config_types"),
                operator=operator,
                dry_run=options.get("dry_run", False),
                check_delivery=not options.get("skip_delivery_check", False),
                delivery_wait_timeout=options.get("delivery_wait_timeout", DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT),
                delivery_poll_interval=options.get("delivery_poll_interval", DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL),
                retry_render_failures=not options.get("skip_render_failure_retry", False),
                include_details=options.get("include_details", False),
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self._write_report_result(
            result,
            success_message="refresh biz bk-collector configs completed",
            warning_message="refresh biz bk-collector configs completed with failures",
        )

    def _handle_retry_biz_bk_collector_config_delivery(self, options) -> None:
        action_name = "retry-biz-bk-collector-config-delivery"
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name=action_name)
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name=action_name)
        operator = self._load_operator(options.get("operator"), action_name=action_name)
        try:
            result = retry_biz_bk_collector_proxy_config_delivery(
                bk_tenant_id=bk_tenant_id,
                bk_biz_ids=bk_biz_ids,
                config_types=options.get("config_types"),
                operator=operator,
                dry_run=options.get("dry_run", False),
                recheck_delivery=not options.get("skip_delivery_recheck", False),
                delivery_wait_timeout=options.get("delivery_wait_timeout", DEFAULT_CONFIG_DELIVERY_WAIT_TIMEOUT),
                delivery_poll_interval=options.get("delivery_poll_interval", DEFAULT_CONFIG_DELIVERY_POLL_INTERVAL),
                include_details=options.get("include_details", False),
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self._write_report_result(
            result,
            success_message="retry biz bk-collector config delivery completed",
            warning_message="retry biz bk-collector config delivery completed with failures",
        )

    def _handle_migrate_system_event_strategies(self, options) -> None:
        result = migrate_system_event_strategy_config(
            bk_biz_id=options.get("bk_biz_ids"),
            dry_run=options.get("dry_run", False),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result["stale_count"]:
            self.stdout.write(
                self.style.WARNING(
                    f"migrate system event strategies completed with stale records: {result['stale_count']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"migrate system event strategies completed: changed={result['changed_count']}, "
                    f"applied={result['applied_count']}, skipped={result['skipped_count']}"
                )
            )

    def _handle_migrate_gather_up_strategies(self, options) -> None:
        result = migrate_gather_up_strategy_config(
            bk_biz_id=options.get("bk_biz_ids"),
            dry_run=options.get("dry_run", False),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result["stale_count"]:
            self.stdout.write(
                self.style.WARNING(
                    f"migrate gather_up strategies completed with stale records: {result['stale_count']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"migrate gather_up strategies completed: changed={result['changed_count']}, "
                    f"applied={result['applied_count']}"
                )
            )

    def _handle_migrate_builtin_strategies(self, options) -> None:
        result = migrate_builtin_strategy_config(
            bk_biz_id=options.get("bk_biz_ids"),
            dry_run=options.get("dry_run", False),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result["stale_count"]:
            self.stdout.write(
                self.style.WARNING(f"migrate builtin strategies completed with stale records: {result['stale_count']}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"migrate builtin strategies completed: changed={result['changed_count']}, "
                    f"applied={result['applied_count']}"
                )
            )

    def _handle_repair_plugin_dashboard_result_table(self, options) -> None:
        result = repair_plugin_dashboard_result_table_id(
            bk_biz_id=options.get("bk_biz_ids"),
            dry_run=options.get("dry_run", False),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if result["stale_count"] or result["invalid_json_count"]:
            self.stdout.write(
                self.style.WARNING(
                    "repair plugin dashboard result table completed with warnings: "
                    f"changed={result['changed_count']}, applied={result['applied_count']}, "
                    f"stale={result['stale_count']}, invalid_json={result['invalid_json_count']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"repair plugin dashboard result table completed: changed={result['changed_count']}, "
                    f"applied={result['applied_count']}"
                )
            )

    def _write_report_result(self, result: dict[str, Any], *, success_message: str, warning_message: str) -> None:
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        self._write_skipped_hosts(result)
        total_summary = result["summary"]["total"]
        failed_count = total_summary["failed_count"]
        timeout_count = total_summary.get("timeout_count", 0)
        pending_count = total_summary.get("pending_count", 0)
        delivery_check = result.get("delivery_check") or {}
        delivery_failed = bool(delivery_check) and delivery_check.get("result") is False
        delivery_timed_out = delivery_check.get("timed_out") is True
        command_error_message = ""
        if timeout_count:
            command_error_message = f"{warning_message} with timeout jobs: {timeout_count}"
        elif delivery_timed_out:
            command_error_message = f"{warning_message} with delivery check timeout"
        elif failed_count:
            command_error_message = f"{warning_message}: {failed_count}"
        elif delivery_failed:
            command_error_message = f"{warning_message} with delivery check failures"
        elif pending_count:
            command_error_message = f"{success_message} with pending jobs: {pending_count}"
        else:
            self.stdout.write(self.style.SUCCESS(success_message))
            return

        self.stdout.write(self.style.WARNING(command_error_message))
        raise CommandError(command_error_message)

    @staticmethod
    def _resolve_skip_hosts_without_agent(options, *, default: bool) -> bool:
        """按动作解析是否跳过 Agent 未安装的主机；命令行显式指定时优先。"""
        value = options.get("skip_hosts_without_agent")
        if value is None:
            return default
        return bool(value)

    def _write_skipped_hosts(self, result: dict[str, Any]) -> None:
        """集中打印因 Agent 未安装等原因被跳过的主机及原因。"""
        skip_summary = result.get("skip_summary") or {}
        host_count = skip_summary.get("host_count", 0)
        if not host_count:
            return

        self.stdout.write(self.style.WARNING(f"skipped {host_count} host(s), detail:"))
        for record in skip_summary.get("records", []):
            for host in record.get("hosts", []):
                self.stdout.write(
                    self.style.WARNING(
                        "  bk_biz_id={bk_biz_id} bk_host_id={bk_host_id} ip={ip} "
                        "agent_status={agent_status} reason={reason}".format(
                            bk_biz_id=record.get("bk_biz_id"),
                            bk_host_id=host.get("bk_host_id"),
                            ip=host.get("ip"),
                            agent_status=host.get("agent_status"),
                            reason=host.get("reason"),
                        )
                    )
                )

    def _import_from_directory(self, directory: Path, options) -> None:
        """从已解压目录执行数据导入。"""
        try:
            import_biz_data_from_directory(
                directory_path=directory,
                bk_biz_ids=options.get("bk_biz_ids"),
                atomic=not options["disable_atomic"],
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

    def _load_directory(self, options, action_name: str) -> Path:
        """按动作校验并返回目录参数。"""
        raw_directory = options.get("directory")
        if not raw_directory:
            raise CommandError(f"{action_name} 动作必须提供 --directory")
        return Path(raw_directory)

    def _download_and_unpack_import_archive(self, archive_url: str, target_root: Path) -> Path:
        """下载导出压缩包并解压，返回包含 ``manifest.json`` 的目录。"""
        archive_path = self._download_import_archive(archive_url=archive_url, target_root=target_root)
        extract_directory = target_root / "extracted"
        extract_directory.mkdir(parents=True, exist_ok=True)
        try:
            shutil.unpack_archive(str(archive_path), extract_directory)
        except (shutil.ReadError, ValueError) as error:
            raise CommandError(f"无法解压导入压缩包: {error}") from error
        return self._locate_import_directory(extract_directory)

    def _download_import_archive(self, archive_url: str, target_root: Path) -> Path:
        """下载远端导出压缩包到临时目录。"""
        parsed_url = urlparse(archive_url)
        file_name = Path(parsed_url.path).name or "bkmonitor-data-migrate.tar.gz"
        archive_path = target_root / file_name
        try:
            with requests.get(archive_url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with archive_path.open("wb") as archive_file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            archive_file.write(chunk)
        except requests.RequestException as error:
            raise CommandError(f"下载导入压缩包失败: {error}") from error
        return archive_path

    def _locate_import_directory(self, extract_directory: Path) -> Path:
        """在解压结果中定位真正的导入根目录。"""
        manifest_path = extract_directory / "manifest.json"
        if manifest_path.exists():
            return extract_directory

        matched_directories = sorted(
            {manifest_file.parent for manifest_file in extract_directory.rglob("manifest.json")},
            key=lambda path: str(path),
        )
        if not matched_directories:
            raise CommandError("解压结果中未找到 manifest.json，无法执行导入")
        if len(matched_directories) > 1:
            raise CommandError(f"解压结果中找到多个导入目录，无法自动选择: {matched_directories}")
        return matched_directories[0]

    def _load_biz_tenant_id_map(self, raw_mapping):
        if not raw_mapping:
            raise CommandError("replace-tenant-id 动作必须提供 --biz-tenant-id-map")

        try:
            loaded_mapping = json.loads(raw_mapping)
            return {
                ("*" if str(biz_id) == "*" else int(biz_id)): tenant_id for biz_id, tenant_id in loaded_mapping.items()
            }
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise CommandError(f"--biz-tenant-id-map 不是合法 JSON 映射: {error}") from error

    def _load_target_tenant_id(self, raw_target_tenant_id):
        """校验导出流程需要的目标租户参数。"""
        target_tenant_id = str(raw_target_tenant_id or "").strip()
        if not target_tenant_id:
            raise CommandError("export 动作必须提供 --target-tenant-id")
        return target_tenant_id

    def _load_optional_tenant_id(self, raw_tenant_id):
        """规范化可选租户 ID。"""
        tenant_id = str(raw_tenant_id or "").strip()
        return tenant_id or None

    def _load_bk_tenant_id(self, raw_bk_tenant_id: str | None, action_name: str) -> str:
        """校验需要租户 ID 的动作参数。"""
        bk_tenant_id = str(raw_bk_tenant_id or "").strip()
        if not bk_tenant_id:
            raise CommandError(f"{action_name} 动作必须提供 --bk-tenant-id")
        return bk_tenant_id

    def _load_bk_biz_id(self, raw_bk_biz_id: int | None, action_name: str) -> int:
        """校验局部迁移使用的单业务 ID。"""
        if raw_bk_biz_id is None:
            raise CommandError(f"{action_name} 动作必须提供 --bk-biz-id")
        bk_biz_id = int(raw_bk_biz_id)
        if bk_biz_id == 0:
            raise CommandError(f"{action_name} 动作不支持业务 ID: 0")
        return bk_biz_id

    def _load_positive_biz_ids(self, bk_biz_ids: list[int] | None, action_name: str) -> list[int]:
        """校验仅支持正整数业务 ID 的动作入参。"""
        normalized_bk_biz_ids = self._load_biz_ids(bk_biz_ids, action_name=action_name)
        invalid_bk_biz_ids = [bk_biz_id for bk_biz_id in normalized_bk_biz_ids if bk_biz_id <= 0]
        if invalid_bk_biz_ids:
            raise CommandError(f"{action_name} 动作不支持这些业务 ID: {invalid_bk_biz_ids}")
        return normalized_bk_biz_ids

    def _load_non_zero_biz_ids(self, bk_biz_ids: list[int] | None, action_name: str) -> list[int]:
        """校验支持正负业务 ID 但不支持全局 0 的动作入参。"""
        normalized_bk_biz_ids = self._load_biz_ids(bk_biz_ids, action_name=action_name)
        if 0 in normalized_bk_biz_ids:
            raise CommandError(f"{action_name} 动作不支持这些业务 ID: [0]")
        return normalized_bk_biz_ids

    def _load_biz_ids(self, bk_biz_ids: list[int] | None, action_name: str) -> list[int]:
        """校验并去重业务 ID 入参。"""
        normalized_bk_biz_ids = list(dict.fromkeys(int(bk_biz_id) for bk_biz_id in (bk_biz_ids or [])))
        if not normalized_bk_biz_ids:
            raise CommandError(f"{action_name} 动作必须提供 --bk-biz-ids")
        return normalized_bk_biz_ids

    def _load_data_id_infos(self, raw_data_id_infos: str | None) -> dict[int, dict[str, Any]]:
        """解析双写路由需要的数据 ID 信息，支持 JSON 字符串或 JSON 文件路径。"""
        if not raw_data_id_infos:
            raise CommandError("add-migrate-data-id-routes 动作必须提供 --data-id-infos")

        raw_payload = raw_data_id_infos
        try:
            file_path = Path(raw_data_id_infos)
            if file_path.exists():
                raw_payload = file_path.read_text(encoding="utf-8")
        except OSError:
            pass

        try:
            loaded_payload = json.loads(raw_payload)
        except json.JSONDecodeError as error:
            raise CommandError(f"--data-id-infos 不是合法 JSON: {error}") from error

        return self._normalize_data_id_infos_payload(loaded_payload)

    def _normalize_data_id_infos_payload(self, payload: Any) -> dict[int, dict[str, Any]]:
        """兼容完整查询结果或单分类结果，统一转成 ``data_id -> info`` 结构。"""
        if not isinstance(payload, dict):
            raise CommandError("--data-id-infos 必须是 JSON 对象")

        if self._is_single_data_id_info(payload):
            return {int(payload["data_id"]): self._normalize_single_data_id_info(payload)}

        normalized_data_id_infos: dict[int, dict[str, Any]] = {}
        for value in payload.values():
            if not isinstance(value, dict):
                continue
            if self._is_single_data_id_info(value):
                normalized_info = self._normalize_single_data_id_info(value)
                normalized_data_id_infos[int(normalized_info["data_id"])] = normalized_info
                continue
            for nested_value in value.values():
                if not isinstance(nested_value, dict) or not self._is_single_data_id_info(nested_value):
                    continue
                normalized_info = self._normalize_single_data_id_info(nested_value)
                normalized_data_id_infos[int(normalized_info["data_id"])] = normalized_info
        return normalized_data_id_infos

    def _is_single_data_id_info(self, payload: dict[str, Any]) -> bool:
        """判断对象是否符合单条数据 ID 信息结构。"""
        required_fields = {"data_id", "topic_name", "kafka_cluster_name"}
        return required_fields.issubset(payload.keys())

    def _normalize_single_data_id_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        """标准化单条数据 ID 信息。"""
        try:
            return {
                "data_id": int(payload["data_id"]),
                "topic_name": str(payload["topic_name"]),
                "kafka_cluster_name": str(payload["kafka_cluster_name"]),
            }
        except (TypeError, ValueError, KeyError) as error:
            raise CommandError(f"数据 ID 信息结构非法: {payload}, error: {error}") from error

    def _load_bk_data_id(self, raw_bk_data_id: int | None, action_name: str) -> int:
        """校验单数据 ID 参数。"""
        if raw_bk_data_id is None:
            raise CommandError(f"{action_name} 动作必须提供 --bk-data-id")
        if raw_bk_data_id <= 0:
            raise CommandError(f"{action_name} 动作不支持这个数据 ID: {raw_bk_data_id}")
        return raw_bk_data_id

    def _load_kafka_cluster_name(self, raw_kafka_cluster_name: str | None, action_name: str) -> str:
        """校验 Kafka 集群名称参数。"""
        kafka_cluster_name = str(raw_kafka_cluster_name or "").strip()
        if not kafka_cluster_name:
            raise CommandError(f"{action_name} 动作必须提供 --kafka-cluster-name")
        return kafka_cluster_name

    def _load_optional_cluster_name(self, raw_cluster_name: str | None) -> str | None:
        """规范化可选集群名称，空值表示沿用旧逻辑。"""
        cluster_name = str(raw_cluster_name or "").strip()
        return cluster_name or None

    def _load_operator(self, raw_operator: str | None, action_name: str) -> str:
        """校验操作人参数。"""
        operator = str(raw_operator or "").strip()
        if not operator:
            raise CommandError(f"{action_name} 动作必须提供 --operator")
        return operator

    def _build_export_biz_tenant_id_map(self, target_tenant_id: str) -> dict[int | str, str]:
        """构造导出流程默认使用的租户替换映射。"""
        return {"*": target_tenant_id}

    def _load_partial_scope_from_options(self, options) -> dict[str, Any]:
        raw_directory = options.get("directory")
        if not raw_directory:
            return {}
        directory = Path(raw_directory)
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            return load_partial_scope_from_directory(directory)
        except ValueError as error:
            raise CommandError(str(error)) from error

    def _load_partial_selectors(
        self,
        options,
        action_name: str,
        partial_scope: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        scope_selectors = (partial_scope or {}).get("selectors") or {}
        selectors = {
            "bcs_cluster_ids": options.get("bcs_cluster_ids") or scope_selectors.get("bcs_cluster_ids") or [],
            "custom_report_data_ids": (
                options.get("custom_report_data_ids") or scope_selectors.get("custom_report_data_ids") or []
            ),
            "app_names": options.get("app_names") or scope_selectors.get("app_names") or [],
        }
        if not any(selectors.values()):
            raise CommandError(f"{action_name} 动作必须提供 --bcs-cluster-ids、--custom-report-data-ids 或 --app-names")
        return selectors

    def _rewrite_partial_manifest_tenant_id(self, directory: Path, target_tenant_id: str) -> None:
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        partial_scope = manifest.get("partial")
        if isinstance(partial_scope, dict):
            partial_scope["bk_tenant_id"] = target_tenant_id
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _write_partial_data_id_infos(self, options, result: dict[str, Any]) -> None:
        """将局部重建后的新环境 Data ID 信息写回迁移目录。"""
        raw_directory = options.get("directory")
        if not raw_directory or "data_id_infos" not in result:
            return

        directory = Path(raw_directory)
        if not directory.exists():
            raise CommandError(f"partial-rebuild 写入 {PARTIAL_DATA_ID_INFOS_FILE} 失败，目录不存在: {directory}")

        target_path = directory / PARTIAL_DATA_ID_INFOS_FILE
        target_path.write_text(
            json.dumps(result["data_id_infos"], ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load_cluster_id_map(self, raw_mapping) -> dict[int | str, int | str]:
        if not raw_mapping:
            raise CommandError("replace-cluster-id 动作必须提供 --cluster-id-map")

        try:
            loaded_mapping = json.loads(raw_mapping)
            return {
                int(source_cluster_id): int(target_cluster_id)
                for source_cluster_id, target_cluster_id in loaded_mapping.items()
            }
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise CommandError(f"--cluster-id-map 不是合法 JSON 映射: {error}") from error
