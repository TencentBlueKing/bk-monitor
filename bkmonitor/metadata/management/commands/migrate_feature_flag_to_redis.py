# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand, CommandError

from metadata.feature_flag import FeatureFlagRedisSync, FeatureFlagSourceMissingError


class Command(BaseCommand):
    """将既有 Consul Feature Flag 快照一次性写入 Redis。"""

    help = "将 Consul 中的 Feature Flag 快照一次性写入 Redis"

    def handle(self, *args, **options):
        try:
            snapshot = FeatureFlagRedisSync.sync_from_consul()
        except FeatureFlagSourceMissingError as error:
            raise CommandError(str(error)) from error
        except Exception as error:
            raise CommandError(f"feature flag migration failed: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                "feature flag migration command completed: "
                f"{len(snapshot)} flags were written to Redis; "
                "repeated invocations are skipped"
            )
        )
