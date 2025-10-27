"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand

from bkmonitor.models import AlgorithmChoiceConfig
from core.drf_resource import api


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **options):
        def get_algorithm_mame(snake_str):
            """获取算法名称"""
            return "".join(word.capitalize() for word in snake_str.split("_"))

        def get_detail_info(plan_id):
            """获取AIOPS方案详情"""
            del_keys = [
                "created_by",
                "updated_by",
                "created_at",
                "updated_at",
                "plan_id",
                "refer",
                "deletable_msg",
                "deletable",
            ]
            detail_data = api.bkdata.get_scene_service_plan(plan_id=plan_id)
            parameter = []
            for i in detail_data["variable_info"]["parameter"]:
                for key in del_keys:
                    del i[key]
                parameter.append(i)
            variable = {"parameter": parameter}
            return variable, detail_data

        try:
            scenes = [
                item
                for item in api.bkdata.list_scene_service()
                if item["status"] == "active"
            ]
        except:
            # 如果无法获取AIOPS场景信息，则跳过
            return

        many_versions_plan = {}
        add_plan_list = []
        for scene_info in scenes:
            plans = api.bkdata.list_scene_service_plans(
                scene_id=scene_info["scene_id"], detail=1
            )
            for plan_info in plans:
                if not plan_info["is_visible"]:
                    continue
                # 更新id为最新的，防止重复
                config = AlgorithmChoiceConfig.objects.filter(
                    name=plan_info["plan_name"]
                ).first()
                if config:
                    config.id = plan_info["plan_id"]
                    config.save()

                # 如果当前方案是多版本，后续处理
                if plan_info["plan_name"] in many_versions_plan.keys():
                    continue

                # 多个版本的后续处理
                plans = [
                    item
                    for item in plans
                    if item["plan_name"] == plan_info["plan_name"]
                ]
                if len(plans) > 1:
                    many_versions_plan[plan_info["plan_name"]] = plans
                    continue

                else:
                    variable_info, plan = get_detail_info(plan_info["plan_id"])
                    plan_document = plan.get("plan_document", {})
                    data = {
                        "id": plan_info["plan_id"],
                        "alias": plan_info["plan_alias"],
                        "name": plan_info["plan_name"],
                        "document": plan_info["plan_document"],
                        "description": plan_document.get("instroduction", ""),
                        "instruction": plan_document.get("content", ""),
                        "is_default": plan_info["is_default"],
                        "version_no": plan["version_no"],
                        "is_new_version": True,
                        "variable_info": variable_info,
                        "ts_freq": plan_info["ts_freq"],
                        "algorithm": get_algorithm_mame(plan_info["plan_name"]),
                        "config": {},
                    }
                    add_plan_list.append(AlgorithmChoiceConfig(**data))
        for plan_name in many_versions_plan:
            plan_list = many_versions_plan[plan_name]
            plan_list.sort(key=lambda x: x["version_no"], reverse=True)
            for index, plan_info in enumerate(plan_list):
                variable_info, plan = get_detail_info(plan_info["plan_id"])
                plan_document = plan.get("plan_document", {})
                data = {
                    "id": plan_info["plan_id"],
                    "alias": plan_info["plan_alias"],
                    "name": plan_info["plan_name"],
                    "document": plan_info["plan_document"],
                    "description": plan_document.get("instroduction", ""),
                    "instruction": plan_document.get("content", ""),
                    "is_default": plan_info["is_default"],
                    "version_no": plan["version_no"],
                    "is_new_version": index == 0,
                    "variable_info": variable_info,
                    "ts_freq": plan_info["ts_freq"],
                    "algorithm": get_algorithm_mame(plan_info["plan_name"]),
                    "config": {},
                }
                add_plan_list.append(AlgorithmChoiceConfig(**data))
        AlgorithmChoiceConfig.objects.bulk_create(add_plan_list)