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

from ....django.facade import get_framework
from ....schema.definitions import ActionDef, ResourceTypeDef, RoleDef


class Command(BaseCommand):
    help = "导出本地 schema 为目标配置 JSON（供人工审查或 CI 对比）。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", default=None, help="Provider 名称用于 system 信息")
        parser.add_argument("--output", default=None, help="输出 JSON 文件路径")

    def handle(self, **options):
        fw = get_framework()

        def _action(a: ActionDef) -> dict:
            d: dict = {"id": a.id, "name": a.name, "resource_type": a.resource_type}
            if a.description:
                d["description"] = a.description
            return d

        def _resource_type(r: ResourceTypeDef) -> dict:
            d: dict = {"id": r.id, "name": r.name}
            if r.ancestor:
                d["ancestor"] = r.ancestor
                d["ancestor_chain"] = fw.schema.resolve_ancestor_types(r.id)
            if r.description:
                d["description"] = r.description
            return d

        def _role(r: RoleDef) -> dict:
            return {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "actions": [{"action_id": b.action_id, "resource_type": b.resource_type} for b in r.actions],
            }

        config: dict = {
            "actions": [_action(a) for a in fw.schema.all_actions()],
            "resource_types": [_resource_type(r) for r in fw.schema.all_resource_types()],
            "roles": [_role(r) for r in fw.schema.all_roles()],
        }

        # 系统信息是 per-Provider 的，通过 provider.get_system_info() 获取
        # 返回对象结构由 Provider 自己定义，此处以 duck typing 消费其字段
        def _dump_system(system_obj) -> dict:
            return {
                "id": getattr(system_obj, "id", ""),
                "name": getattr(system_obj, "name", ""),
                "description": getattr(system_obj, "description", ""),
                "clients": list(getattr(system_obj, "clients", ()) or ()),
                "managers": list(getattr(system_obj, "managers", ()) or ()),
                "callback_url": getattr(system_obj, "callback_url", ""),
            }

        provider_name = options.get("provider")
        if provider_name:
            provider = fw.providers.get(provider_name)
            if provider is not None:
                system_info = provider.get_system_info()
                if system_info is not None:
                    config["system"] = _dump_system(system_info)
        else:
            systems = {}
            for p in fw.providers.values():
                system_info = p.get_system_info()
                if system_info is not None:
                    systems[p.name] = _dump_system(system_info)
            if systems:
                config["systems"] = systems

        output = options.get("output")
        if output:
            with open(output, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.stdout.write(f"Config written to {output}")
        else:
            self.stdout.write(json.dumps(config, indent=2, ensure_ascii=False))
