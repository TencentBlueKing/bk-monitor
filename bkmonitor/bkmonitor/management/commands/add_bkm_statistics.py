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
from django.core.management import BaseCommand

from constants.common import DEFAULT_TENANT_ID
from metadata.models import TimeSeriesGroup


class Command(BaseCommand):
    def handle(self, **kwargs):
        if settings.ROLE != "api":
            print("try with: ./bin/api_manage.sh add_bkm_statistics")
            return
        from monitor_web.models import CustomTSTable

        tsg = TimeSeriesGroup.objects.get(bk_data_id=1100013)
        _, created = CustomTSTable.objects.get_or_create(
            time_series_group_id=tsg.time_series_group_id,
            defaults=dict(
                bk_tenant_id=DEFAULT_TENANT_ID,
                bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
                scenario="application_check",
                name="bkm_statistics",
                bk_data_id=1100013,
                table_id="bkm_statistics.base",
                is_platform=True,
                data_label="bkm_statistics",
                protocol="json",
                desc="监控运营数据",
            ),
        )
        print(f"bkm_statistics {'created' if created else 'already exist, do nothing.'}")
