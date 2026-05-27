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

from metadata.models import TimeSeriesMetric, TimeSeriesScope

"""
example:
python manage.py export_time_series_migration --output=/app/code/bkte_101002.json --group-mapping='{"10527":"7499_119955_Role","10528":"7499_120442_Team"}'
"""


class Command(BaseCommand):
    help = "导出旧平台指定时序分组下的 scope 和活跃 metric 数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group-mapping",
            type=str,
            required=True,
            help='旧平台 group_id 到 group_name 的映射，JSON 格式，例如：{"1001": "group_a"}',
        )
        parser.add_argument(
            "--output",
            type=str,
            default="bkte_101002.json",
            help="导出文件路径，默认 bkte_101002.json",
        )

    def handle(self, *args, **options):
        group_mapping = self._parse_group_mapping(options["group_mapping"])
        output_path = Path(options["output"])

        export_data = {
            "version": 1,
            "groups": [],
        }

        for source_group_id, source_group_name in group_mapping.items():
            scopes = list(TimeSeriesScope.objects.filter(group_id=source_group_id).order_by("id"))
            metrics = list(
                TimeSeriesMetric.objects.filter(group_id=source_group_id, is_active=True).order_by("field_id")
            )
            scope_id_to_name = {scope.id: scope.scope_name for scope in scopes}

            group_data = {
                "source_group_id": source_group_id,
                "group_name": source_group_name,
                "scopes": [self._serialize_scope(scope) for scope in scopes],
                "metrics": [self._serialize_metric(metric, scope_id_to_name) for metric in metrics],
            }
            export_data["groups"].append(group_data)

            self.stdout.write(
                self.style.SUCCESS(
                    f"export group success: group_id={source_group_id}, group_name={source_group_name}, "
                    f"scope_count={len(scopes)}, metric_count={len(metrics)}"
                )
            )

        output_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"export finished: {output_path}"))

    def _parse_group_mapping(self, raw_mapping: str) -> dict[int, str]:
        try:
            data = json.loads(raw_mapping)
        except json.JSONDecodeError as error:
            raise CommandError(f"invalid group_mapping json: {error}")

        if not isinstance(data, dict) or not data:
            raise CommandError("group_mapping must be a non-empty json object")

        parsed_mapping = {}
        for group_id, group_name in data.items():
            try:
                parsed_group_id = int(group_id)
            except (TypeError, ValueError):
                raise CommandError(f"invalid group_id: {group_id}")

            if not isinstance(group_name, str) or not group_name:
                raise CommandError(f"invalid group_name for group_id={group_id}")

            parsed_mapping[parsed_group_id] = group_name
        return parsed_mapping

    def _serialize_scope(self, scope: TimeSeriesScope) -> dict:
        return {
            "source_scope_id": scope.id,
            "source_group_id": scope.group_id,
            "scope_name": scope.scope_name,
            "dimension_config": scope.dimension_config,
            "auto_rules": scope.auto_rules,
            "create_from": scope.create_from,
        }

    def _serialize_metric(self, metric: TimeSeriesMetric, scope_id_to_name: dict[int, str]) -> dict:
        scope_name = scope_id_to_name.get(metric.scope_id)
        if metric.scope_id not in (None, TimeSeriesMetric.DISABLE_SCOPE_ID) and scope_name is None:
            raise CommandError(
                f"metric scope not found, group_id={metric.group_id}, field_name={metric.field_name}, "
                f"scope_id={metric.scope_id}"
            )

        return {
            "source_field_id": metric.field_id,
            "source_group_id": metric.group_id,
            "source_scope_id": metric.scope_id,
            "scope_name": scope_name,
            "table_id": metric.table_id,
            "field_scope": metric.field_scope,
            "field_name": metric.field_name,
            "tag_list": metric.tag_list,
            "field_config": metric.field_config,
            "label": metric.label,
            "is_active": metric.is_active,
            "last_index": metric.last_index,
        }
