"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef, ResourceTypeDef, RoleDef


class Command(BaseCommand):
    help = "导出本地 schema 为目标配置 JSON（供人工审查或 CI 对比）。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", default=None, help="Provider 名称用于 system 信息")
        parser.add_argument("--output", default=None, help="输出 JSON 文件路径")

    def handle(self, **options):
        fw = get_framework()

        def _action(a: ActionDef):
            return {"id": a.id, "name": a.name, "resource_type": a.resource_type, "parents": list(a.parents)}

        def _resource_type(r: ResourceTypeDef):
            return {"id": r.id, "name": r.name, "ancestor_types": list(r.ancestor_types)}

        def _role(r: RoleDef):
            return {"id": r.id, "name": r.name, "actions": list(r.actions)}

        config = {
            "actions": [_action(a) for a in fw.schema.all_actions()],
            "resource_types": [_resource_type(r) for r in fw.schema.all_resource_types()],
            "roles": [_role(r) for r in fw.schema.all_roles()],
        }

        output = options.get("output")
        if output:
            with open(output, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.stdout.write(f"Config written to {output}")
        else:
            self.stdout.write(json.dumps(config, indent=2, ensure_ascii=False))
