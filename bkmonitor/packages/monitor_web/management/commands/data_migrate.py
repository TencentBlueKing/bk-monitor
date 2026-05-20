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
)
from monitor_web.data_migrate import (
    apply_auto_increment_from_directory,
    disable_models_in_directory,
    export_auto_increment_to_directory,
    export_biz_data_to_directory,
    import_biz_data_from_directory,
    replace_cluster_id_in_directory,
    replace_tenant_id_in_directory,
    restore_disabled_models_in_directory,
    sanitize_cluster_info_in_directory,
    upload_export_directory_to_storage,
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
            "  查询业务下需要添加双写路由的数据 ID:\n"
            "    python manage.py data_migrate find-custom-report-data-ids --bk-tenant-id tencent --bk-biz-ids 18901\n"
            "\n"
            "  为数据 ID 批量添加迁移双写路由:\n"
            "    python manage.py data_migrate add-migrate-data-id-routes --data-id-infos ./data_id_infos.json\n"
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
            "    python manage.py data_migrate restore-disabled-models --directory /tmp/bkmonitor-data-migrate-20260307120000"
        )
        parser.add_argument(
            "action",
            choices=[
                "export",
                "import",
                "rebuild",
                "find-custom-report-data-ids",
                "add-migrate-data-id-routes",
                "enable-closed-strategies",
                "apply-sequences",
                "replace-tenant-id",
                "replace-cluster-id",
                "sanitize-cluster-info",
                "disable-models",
                "restore-disabled-models",
            ],
            help="执行导出、导入、恢复游标或 handler 处理",
        )
        parser.add_argument("--directory", help="导出 zip 输出目录，或已解压的导入目录")
        parser.add_argument("--url", help="导入压缩包下载地址；仅 import 动作可用")
        parser.add_argument(
            "--bk-biz-ids",
            nargs="+",
            type=int,
            help="业务 ID 列表；export/import 中 0 代表全局数据，enable-closed-strategies 仅支持正整数业务 ID",
        )
        parser.add_argument("--format", default="json", help="导出文件格式，默认 json；仅 export 动作需要")
        parser.add_argument("--indent", type=int, default=2, help="导出文件缩进，默认 2；仅 export 动作需要")
        parser.add_argument(
            "--target-tenant-id",
            help="导出目标租户 ID；仅 export 动作需要，导出后默认执行租户 ID 替换",
        )
        parser.add_argument(
            "--disable-atomic",
            action="store_true",
            help="导入时关闭按单文件事务处理；仅 import 动作需要",
        )
        parser.add_argument("--bk-tenant-id", help="租户 ID；仅 rebuild 动作需要")
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
            help="导出时跳过上传到制品库；仅 export 动作需要",
        )
        parser.add_argument(
            "--models",
            nargs="+",
            help="需要关闭的模型列表，形如 monitor_web.CollectConfigMeta；仅 disable-models 动作需要",
        )
        parser.add_argument(
            "--metric-kafka-cluster-name",
            default=DEFAULT_KAFKA_CLUSTER_NAMES["metric"],
            help="指标 Kafka 集群名称；仅 rebuild 动作需要",
        )
        parser.add_argument(
            "--log-kafka-cluster-name",
            default=DEFAULT_KAFKA_CLUSTER_NAMES["event"],
            help="日志 Kafka 集群名称；仅 rebuild 动作需要",
        )
        parser.add_argument(
            "--log-es-cluster-name",
            default=DEFAULT_ES_CLUSTER_NAMES["log"],
            help="日志 ES 集群名称；仅 rebuild 动作需要",
        )
        parser.add_argument(
            "--event-es-cluster-name",
            default=DEFAULT_ES_CLUSTER_NAMES["event"],
            help="事件 ES 集群名称；仅 rebuild 动作需要",
        )
        parser.add_argument(
            "--data-id-infos",
            help="数据 ID 信息 JSON 或 JSON 文件路径；仅 add-migrate-data-id-routes 动作需要",
        )

    def handle(self, *args, **options):
        action = options["action"]
        handlers = {
            "export": self._handle_export,
            "import": self._handle_import,
            "rebuild": self._handle_rebuild,
            "find-custom-report-data-ids": self._handle_find_custom_report_data_ids,
            "add-migrate-data-id-routes": self._handle_add_migrate_data_id_routes,
            "enable-closed-strategies": self._handle_enable_closed_strategies,
            "apply-sequences": self._handle_apply_sequences,
            "replace-tenant-id": self._handle_replace_tenant_id,
            "replace-cluster-id": self._handle_replace_cluster_id,
            "sanitize-cluster-info": self._handle_sanitize_cluster_info,
            "disable-models": self._handle_disable_models,
            "restore-disabled-models": self._handle_restore_disabled_models,
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

    def _handle_rebuild(self, options):
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="rebuild")
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name="rebuild")
        metric_kafka_cluster_name = options["metric_kafka_cluster_name"]
        log_kafka_cluster_name = options["log_kafka_cluster_name"]
        log_es_cluster_name = options["log_es_cluster_name"]
        event_es_cluster_name = options["event_es_cluster_name"]

        self.stdout.write(
            self.style.SUCCESS(
                "rebuild initialized: "
                f"bk_tenant_id={bk_tenant_id}, bk_biz_ids={bk_biz_ids}, "
                f"metric_kafka_cluster_name={metric_kafka_cluster_name}, "
                f"log_kafka_cluster_name={log_kafka_cluster_name}, "
                f"log_es_cluster_name={log_es_cluster_name}, "
                f"event_es_cluster_name={event_es_cluster_name}"
            )
        )

        for bk_biz_id in bk_biz_ids:
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
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild bklog data source route completed: bk_biz_id={bk_biz_id}"))
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
                    "event": log_kafka_cluster_name,
                },
                es_cluster_names={"event": event_es_cluster_name},
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild collect plugins completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild k8s data started: bk_biz_id={bk_biz_id}"))
            rebuild_k8s_data(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                metric_kafka_cluster_name=metric_kafka_cluster_name,
                event_kafka_cluster_name=log_kafka_cluster_name,
                es_cluster_name=event_es_cluster_name,
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild k8s data completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild custom report started: bk_biz_id={bk_biz_id}"))
            rebuild_custom_report(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                metric_kafka_cluster_name=metric_kafka_cluster_name,
                event_kafka_cluster_name=log_kafka_cluster_name,
                es_cluster_name=event_es_cluster_name,
            )
            self.stdout.write(self.style.SUCCESS(f"rebuild custom report completed: bk_biz_id={bk_biz_id}"))
            self.stdout.write(self.style.SUCCESS(f"rebuild completed: bk_biz_id={bk_biz_id}"))

    def _handle_find_custom_report_data_ids(self, options) -> None:
        bk_tenant_id = self._load_bk_tenant_id(options.get("bk_tenant_id"), action_name="find-custom-report-data-ids")
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name="find-custom-report-data-ids")
        data_id_infos = find_biz_custom_report_data_ids(bk_tenant_id=bk_tenant_id, bk_biz_ids=bk_biz_ids)
        self.stdout.write(json.dumps(data_id_infos, ensure_ascii=False, indent=2, sort_keys=True))

    def _handle_add_migrate_data_id_routes(self, options) -> None:
        data_id_infos = self._load_data_id_infos(options.get("data_id_infos"))
        if not data_id_infos:
            self.stdout.write(self.style.WARNING("未找到可用的数据 ID 信息，已跳过添加迁移双写路由"))
            return
        add_new_migrate_data_id_routes(data_id_infos=data_id_infos)
        self.stdout.write(self.style.SUCCESS(f"add migrate data id routes completed: {len(data_id_infos)}"))

    def _handle_enable_closed_strategies(self, options) -> None:
        bk_biz_ids = self._load_positive_biz_ids(options.get("bk_biz_ids"), action_name="enable-closed-strategies")
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

    def _load_bk_tenant_id(self, raw_bk_tenant_id: str | None, action_name: str) -> str:
        """校验需要租户 ID 的动作参数。"""
        bk_tenant_id = str(raw_bk_tenant_id or "").strip()
        if not bk_tenant_id:
            raise CommandError(f"{action_name} 动作必须提供 --bk-tenant-id")
        return bk_tenant_id

    def _load_positive_biz_ids(self, bk_biz_ids: list[int] | None, action_name: str) -> list[int]:
        """校验仅支持正整数业务 ID 的动作入参。"""
        normalized_bk_biz_ids = list(dict.fromkeys(int(bk_biz_id) for bk_biz_id in (bk_biz_ids or [])))
        if not normalized_bk_biz_ids:
            raise CommandError(f"{action_name} 动作必须提供 --bk-biz-ids")
        invalid_bk_biz_ids = [bk_biz_id for bk_biz_id in normalized_bk_biz_ids if bk_biz_id <= 0]
        if invalid_bk_biz_ids:
            raise CommandError(f"{action_name} 动作不支持这些业务 ID: {invalid_bk_biz_ids}")
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

    def _build_export_biz_tenant_id_map(self, target_tenant_id: str) -> dict[int | str, str]:
        """构造导出流程默认使用的租户替换映射。"""
        return {"*": target_tenant_id}

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
