"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from metadata.models import TimeSeriesGroup, TimeSeriesMetric, TimeSeriesScope

"""
example:
python manage.py import_time_series_migration --input=/app/code/bkte_101002.json --group-mapping='{"7499_119955_Role":"25196","7499_120442_Team":"25197"}'
"""


class Command(BaseCommand):
    help = "导入时序分组迁移数据到新平台"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            type=str,
            default="bkte_101002.json",
            help="导入文件路径，默认 bkte_101002.json",
        )
        parser.add_argument(
            "--group-mapping",
            type=str,
            required=True,
            help='新平台 group_name 到 group_id 的映射，JSON 格式，例如：{"group_a": 2001}',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        input_path = Path(options["input"])
        if not input_path.exists():
            raise CommandError(f"input file not found: {input_path}")

        target_group_mapping = self._parse_group_mapping(options["group_mapping"])
        import_data = self._load_import_data(input_path)
        total_scope_created = 0
        total_scope_updated = 0
        total_metric_created = 0
        total_metric_updated = 0

        for group_data in import_data["groups"]:
            source_group_id = group_data["source_group_id"]
            group_name = group_data["group_name"]
            target_group_id = target_group_mapping.get(group_name)
            if target_group_id is None:
                raise CommandError(f"target group_id not found for group_name={group_name}")
            try:
                target_group = TimeSeriesGroup.objects.get(time_series_group_id=target_group_id)
            except TimeSeriesGroup.DoesNotExist:
                raise CommandError(f"target group not found, group_id={target_group_id}, group_name={group_name}")

            scope_name_to_id, scope_created, scope_updated = self._import_scopes(
                target_group_id=target_group_id,
                scopes=group_data.get("scopes", []),
            )
            metric_created, metric_updated = self._import_metrics(
                target_group_id=target_group_id,
                target_table_id=target_group.table_id,
                metrics=group_data.get("metrics", []),
                scope_name_to_id=scope_name_to_id,
            )
            total_scope_created += scope_created
            total_scope_updated += scope_updated
            total_metric_created += metric_created
            total_metric_updated += metric_updated

            self.stdout.write(
                self.style.SUCCESS(
                    f"import group success: source_group_id={source_group_id}, group_name={group_name}, "
                    f"target_group_id={target_group_id}, scope_created={scope_created}, scope_updated={scope_updated}, "
                    f"metric_created={metric_created}, metric_updated={metric_updated}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"import finished: scope_created={total_scope_created}, scope_updated={total_scope_updated}, "
                f"metric_created={total_metric_created}, metric_updated={total_metric_updated}"
            )
        )

    def _parse_group_mapping(self, raw_mapping: str) -> dict[str, int]:
        try:
            data = json.loads(raw_mapping)
        except json.JSONDecodeError as error:
            raise CommandError(f"invalid group_mapping json: {error}")

        if not isinstance(data, dict) or not data:
            raise CommandError("group_mapping must be a non-empty json object")

        parsed_mapping = {}
        for group_name, group_id in data.items():
            if not isinstance(group_name, str) or not group_name:
                raise CommandError(f"invalid group_name: {group_name}")
            try:
                parsed_group_id = int(group_id)
            except (TypeError, ValueError):
                raise CommandError(f"invalid group_id for group_name={group_name}: {group_id}")
            parsed_mapping[group_name] = parsed_group_id
        return parsed_mapping

    def _load_import_data(self, input_path: Path) -> dict:
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise CommandError(f"invalid import file json: {error}")

        if not isinstance(data, dict):
            raise CommandError("import data must be a json object")
        if not isinstance(data.get("groups"), list):
            raise CommandError("import data missing groups list")
        return data

    def _import_scopes(self, target_group_id: int, scopes: list[dict]) -> dict[str, int]:
        scope_name_to_id = {}
        created_count = 0
        updated_count = 0

        for scope_data in scopes:
            scope_name = scope_data["scope_name"]
            defaults = {
                "dimension_config": scope_data.get("dimension_config") or {},
                "auto_rules": scope_data.get("auto_rules") or [],
                "create_from": scope_data.get("create_from") or TimeSeriesScope.CREATE_FROM_DATA,
            }
            scope, created = TimeSeriesScope.objects.update_or_create(
                group_id=target_group_id,
                scope_name=scope_name,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
            scope_name_to_id[scope.scope_name] = scope.id

        return scope_name_to_id, created_count, updated_count

    def _import_metrics(
        self,
        target_group_id: int,
        target_table_id: str,
        metrics: list[dict],
        scope_name_to_id: dict[str, int],
    ) -> int:
        created_count = 0
        updated_count = 0

        for metric_data in metrics:
            scope_name = metric_data.get("scope_name")
            source_scope_id = metric_data.get("source_scope_id")
            if scope_name is None:
                new_scope_id = source_scope_id if source_scope_id in (None, TimeSeriesMetric.DISABLE_SCOPE_ID) else None
                if source_scope_id not in (None, TimeSeriesMetric.DISABLE_SCOPE_ID):
                    raise CommandError(
                        f"scope_name missing for metric, field_name={metric_data['field_name']}, "
                        f"source_scope_id={source_scope_id}"
                    )
            else:
                new_scope_id = scope_name_to_id.get(scope_name)
                if new_scope_id is None:
                    raise CommandError(
                        f"target scope_id not found, group_id={target_group_id}, "
                        f"field_name={metric_data['field_name']}, scope_name={scope_name}"
                    )

            defaults = {
                "scope_id": new_scope_id,
                "table_id": f"{target_table_id.split('.')[0]}.{metric_data['field_name']}",
                "tag_list": metric_data.get("tag_list") or [],
                "field_config": metric_data.get("field_config") or {},
                "label": metric_data.get("label") or "",
                "is_active": bool(metric_data.get("is_active", True)),
                "last_index": metric_data.get("last_index") or 0,
            }
            _, created = TimeSeriesMetric.objects.update_or_create(
                group_id=target_group_id,
                field_scope=metric_data["field_scope"],
                field_name=metric_data["field_name"],
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count
