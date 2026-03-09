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

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bkmonitor.data_migrate import (
    apply_auto_increment_from_directory,
    disable_models_in_directory,
    export_auto_increment_to_directory,
    export_biz_data_to_directory,
    import_biz_data_from_directory,
    replace_tenant_id_in_directory,
    restore_disabled_models_in_directory,
    sanitize_cluster_info_in_directory,
)


class Command(BaseCommand):
    help = "按目录结构导入导出监控业务迁移数据"

    def add_arguments(self, parser):
        parser.formatter_class = argparse.RawTextHelpFormatter
        parser.epilog = (
            "调用示例:\n"
            "  导出业务和全局数据:\n"
            "    python manage.py data_migrate export --directory /tmp/output --bk-biz-ids 2 3 0\n"
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
            "  恢复自增游标:\n"
            "    python manage.py data_migrate apply-sequences --directory /tmp/bkmonitor-data-migrate-20260307120000\n"
            "\n"
            "  按业务替换 bk_tenant_id:\n"
            '    python manage.py data_migrate replace-tenant-id --directory /tmp/bkmonitor-data-migrate-20260307120000 --biz-tenant-id-map \'{"*":"tenant-a","2":"tenant-b"}\'\n'
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
                "apply-sequences",
                "replace-tenant-id",
                "sanitize-cluster-info",
                "disable-models",
                "restore-disabled-models",
            ],
            help="执行导出、导入、恢复游标或 handler 处理",
        )
        parser.add_argument("--directory", required=True, help="导出 zip 输出目录，或导入目录")
        parser.add_argument(
            "--bk-biz-ids",
            nargs="+",
            type=int,
            help="业务 ID 列表，0 代表全局数据；export/import 动作可用",
        )
        parser.add_argument("--format", default="json", help="导出文件格式，默认 json；仅 export 动作需要")
        parser.add_argument("--indent", type=int, default=2, help="导出文件缩进，默认 2；仅 export 动作需要")
        parser.add_argument(
            "--disable-atomic",
            action="store_true",
            help="导入时关闭按单文件事务处理；仅 import 动作需要",
        )
        parser.add_argument(
            "--biz-tenant-id-map",
            help='租户替换映射 JSON，形如 \'{"*":"tenant-a","2":"tenant-b"}\'；仅 replace-tenant-id 动作需要',
        )
        parser.add_argument(
            "--models",
            nargs="+",
            help="需要关闭的模型列表，形如 monitor_web.CollectConfigMeta；仅 disable-models 动作需要",
        )

    def handle(self, *args, **options):
        action = options["action"]
        handlers = {
            "export": self._handle_export,
            "import": self._handle_import,
            "apply-sequences": self._handle_apply_sequences,
            "replace-tenant-id": self._handle_replace_tenant_id,
            "sanitize-cluster-info": self._handle_sanitize_cluster_info,
            "disable-models": self._handle_disable_models,
            "restore-disabled-models": self._handle_restore_disabled_models,
        }
        handlers[action](options)

    def _handle_export(self, options):
        bk_biz_ids = options.get("bk_biz_ids") or []
        if not bk_biz_ids:
            raise CommandError("export 动作必须提供 --bk-biz-ids")

        output_directory = Path(options["directory"])
        output_directory.mkdir(parents=True, exist_ok=True)
        archive_name = f"bkmonitor-data-migrate-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        with tempfile.TemporaryDirectory(prefix="bkmonitor-data-migrate-") as temp_directory:
            export_directory = Path(temp_directory) / archive_name
            export_biz_data_to_directory(
                directory_path=export_directory,
                bk_biz_ids=bk_biz_ids,
                format=options["format"],
                indent=options["indent"],
            )
            export_auto_increment_to_directory(export_directory)
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
        directory = options["directory"]
        try:
            import_biz_data_from_directory(
                directory_path=directory,
                bk_biz_ids=options.get("bk_biz_ids"),
                atomic=not options["disable_atomic"],
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"import completed: {directory}"))

    def _handle_apply_sequences(self, options):
        directory = options["directory"]
        apply_auto_increment_from_directory(
            directory_path=directory,
        )
        self.stdout.write(self.style.SUCCESS(f"apply sequences completed: {directory}"))

    def _handle_replace_tenant_id(self, options):
        directory = options["directory"]
        biz_tenant_id_map = self._load_biz_tenant_id_map(options.get("biz_tenant_id_map"))
        replace_tenant_id_in_directory(
            directory_path=directory,
            biz_tenant_id_map=biz_tenant_id_map,
        )
        self.stdout.write(self.style.SUCCESS(f"replace tenant id completed: {directory}"))

    def _handle_sanitize_cluster_info(self, options):
        directory = options["directory"]
        sanitize_cluster_info_in_directory(
            directory_path=directory,
        )
        self.stdout.write(self.style.SUCCESS(f"sanitize cluster info completed: {directory}"))

    def _handle_disable_models(self, options):
        directory = options["directory"]
        model_labels = options.get("models") or []
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
        directory = options["directory"]
        try:
            restore_disabled_models_in_directory(
                directory_path=directory,
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"restore disabled models completed: {directory}"))

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
