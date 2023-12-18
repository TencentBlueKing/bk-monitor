# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management import BaseCommand

from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        collect_config_id = kwargs["c"]
        collect_config: CollectConfigMeta = CollectConfigMeta.objects.get(id=collect_config_id)
        loader = DatalinkDefaultAlarmStrategyLoader(collect_config, "system")
        loader.run()

    def add_arguments(self, parser):
        parser.add_argument("-c", type=int, required=True, help="采集配置ID")
