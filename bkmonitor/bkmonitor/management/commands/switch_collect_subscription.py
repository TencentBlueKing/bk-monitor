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
from django.conf import settings
from django.core.management import BaseCommand
from monitor_web.models import CollectConfigMeta

from core.drf_resource import api


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            default="enable",
        )

    def handle(self, **kwargs):
        action = kwargs["action"]
        if settings.ROLE not in ["api", "web"]:
            print(f"try with: ./bin/api_manage.sh switch_collect_subscription --action={action}")
            return

        subscription_ids = CollectConfigMeta.objects.filter(
            cache_data__contains='"status": "STARTED"', is_deleted=False
        ).values_list("deployment_config__subscription_id", flat=1)

        for subscription_id in subscription_ids:
            try:
                api.node_man.switch_subscription(subscription_id=subscription_id, action=action)
                print(f"switch subscription({subscription_id}) {action} success")
            except Exception as e:
                print(f"switch subscription({subscription_id}) {action} failed: {e}")
