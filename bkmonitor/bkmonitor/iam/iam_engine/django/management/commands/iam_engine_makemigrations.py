"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# iam_makemigrations — 对比当前 schema 与上次 snapshot，自动生成迁移文件
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
import textwrap
from datetime import datetime

from django.core.management.base import BaseCommand

from ....django.facade import get_framework
from ....migration.diff import diff_snapshots
from ....migration.loader import MigrationLoader


class Command(BaseCommand):
    help = "对比当前 definitions schema 与上次迁移快照，生成新的迁移文件。"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="迁移描述名（如 add_incident_actions）")
        parser.add_argument(
            "--directory",
            default=None,
            help="迁移文件目录（默认从 IAM_FRAMEWORK.MIGRATION.directory 读取）",
        )
        parser.add_argument("--dry-run", action="store_true", help="只打印将要生成的内容，不写文件")

    def handle(self, **options):
        fw = get_framework()
        name = options["name"]
        dry_run = options["dry_run"]

        # 确定迁移目录
        directory = options["directory"]
        if not directory:
            from django.conf import settings

            raw = getattr(settings, "IAM_FRAMEWORK", {})
            directory = raw.get("MIGRATION", {}).get("directory", "")
        if not directory:
            self.stderr.write("No migration directory configured (MIGRATION.DIRECTORY).")
            return

        if not os.path.isdir(directory):
            os.makedirs(directory)
            self.stdout.write(f"Created migration directory: {directory}")

        # 加载已有迁移，找到最新的 target_snapshot
        loader = MigrationLoader(directory)
        existing = loader.load_all()
        if existing:
            last_migration = sorted(existing.values(), key=lambda m: m.name)[-1]
            previous_snapshot = last_migration.target_snapshot
            last_number = int(last_migration.name[:4])
        else:
            previous_snapshot = {}
            last_number = 0

        # 当前 schema 快照
        current_snapshot = fw.schema.to_snapshot()

        # Diff
        changes = diff_snapshots(current_snapshot, previous_snapshot)
        if not changes:
            self.stdout.write(self.style.SUCCESS("No changes detected. Nothing to migrate."))
            return

        create_count = sum(1 for c in changes if c.change_type.value == "create")
        update_count = sum(1 for c in changes if c.change_type.value == "update")
        delete_count = sum(1 for c in changes if c.change_type.value == "delete")
        self.stdout.write(f"Changes: +{create_count} ~{update_count} -{delete_count}")

        # 生成迁移文件
        new_number = last_number + 1
        migration_name = f"{new_number:04d}_{name}"

        # 依赖
        if existing:
            sorted_existing = sorted(existing.values(), key=lambda m: m.name)
            dependencies = [sorted_existing[-1].name]
        else:
            dependencies = []

        content = _render_migration(migration_name, dependencies, changes, current_snapshot)

        if dry_run:
            self.stdout.write(f"\n--- {migration_name}.py (dry-run) ---")
            self.stdout.write(content)
            return

        filepath = os.path.join(directory, f"{migration_name}.py")
        with open(filepath, "w") as f:
            f.write(content)
        self.stdout.write(self.style.SUCCESS(f"Created: {filepath}"))


def _render_migration(
    migration_name: str,
    dependencies: list[str],
    changes: list,
    snapshot: dict,
) -> str:
    """生成迁移文件源码。"""
    import json

    from ....schema.diff import Change

    def _change_repr(c) -> str:
        return (
            f"Change(kind=EntityKind.{c.kind.name}, "
            f"change_type=ChangeType.{c.change_type.name}, "
            f"entity_id={c.entity_id!r}, before={c.before!r}, "
            f"after={c.after!r}, reason={c.reason!r}, "
            f"destructive={c.destructive!r})"
        )

    deps_repr = repr(dependencies)
    ops_lines = ",\n".join(f"        {_change_repr(c)}" for c in changes)
    ops_repr = f"[\n{ops_lines},\n    ]"
    snapshot_repr = json.dumps(snapshot, indent=4, ensure_ascii=False, sort_keys=True)
    import_path = Change.__module__

    header = f'"""\n迁移: {migration_name}\n生成时间: {datetime.now().isoformat()}\n"""'
    imports = textwrap.dedent(f"""\
    import json

    from {import_path} import Change, ChangeType, EntityKind
    """)

    body = textwrap.dedent(f"""\
    dependencies: list[str] = {deps_repr}

    operations: list[Change] = {ops_repr}

    target_snapshot: dict = json.loads({snapshot_repr!r})
    """)

    return f"{header}\n\n{imports}\n\n{body}"
