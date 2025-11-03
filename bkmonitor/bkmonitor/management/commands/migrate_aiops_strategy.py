"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from bkmonitor.models import AlgorithmChoiceConfig, AlgorithmModel
from core.drf_resource import api


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **options):
        if settings.IS_MIGRATE_AIOPS_STRATEGY:
            return

        # 1. 获取来源于AIOPS的场景方案，并生成方案ID->方案名称的映射
        aiops_plans_mapping = {}

        try:
            scenes = [item for item in api.bkdata.list_scene_service() if item["status"] == "active"]
        except Exception:
            # 如果无法获取AIOPS场景信息，则跳过
            return

        for scene_info in scenes:
            plans = api.bkdata.list_scene_service_plans(scene_id=scene_info["scene_id"], detail=1)
            for plan_info in plans:
                aiops_plans_mapping[plan_info["plan_id"]] = plan_info["plan_name"]

        # 2. 获取同步到监控的算法方案配置，并生成方案名称->新方案ID的配置
        monitor_plans_mapping = {}
        for config in AlgorithmChoiceConfig.objects.all():
            monitor_plans_mapping[config.name] = config.id

        # 3. 根据方案名称，构建AIOPS方案ID->监控算法配置ID的映射
        ids_mapping = {}
        for plan_id, plan_name in aiops_plans_mapping.items():
            if plan_name in monitor_plans_mapping:
                ids_mapping[plan_id] = monitor_plans_mapping[plan_name]

        # 4. 更新检测算法配置中的方案ID
        for algorithm in AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS):
            if algorithm.config.get("plan_id") in ids_mapping:
                algorithm.config["plan_id"] = ids_mapping[algorithm.config["plan_id"]]
                algorithm.save()

        settings.IS_MIGRATE_AIOPS_STRATEGY = True
