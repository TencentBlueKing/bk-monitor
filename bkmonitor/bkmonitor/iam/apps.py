"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


class IAMConfig(AppConfig):
    name = "bkmonitor.iam"
    label = "bkmonitor_iam"
    verbose_name = "IAM"

    def ready(self):
        from bkmonitor.iam.model_sync import migrate_iam_models
        from bkmonitor.iam.mode import get_mode_provider

        get_mode_provider()
        post_migrate.connect(
            migrate_iam_models,
            sender=apps.get_app_config("bkmonitor"),
            dispatch_uid="bkmonitor iam models",
            weak=False,
        )
