"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import cached_property

from api.cmdb.define import Business
from bkmonitor.models import StatisticsMetric
from core.drf_resource import api
from core.statistics.collector import Collector
from core.statistics.metric import Metric
from core.statistics.storage import Storage


class MySQLStorage(Storage):
    def get(self, metric_names: list[str]) -> list[Metric]:
        metrics = StatisticsMetric.objects.filter(name__in=metric_names)
        return [Metric.loads(metric.data) for metric in metrics]

    def put(self, metrics: list[Metric]):
        for metric in metrics:
            StatisticsMetric.objects.update_or_create(
                name=metric.name,
                defaults={
                    "data": metric.dumps(),
                    "update_time": metric.last_update_time,
                },
            )


class BaseCollector(Collector):
    STORAGE_BACKEND = MySQLStorage

    @cached_property
    def biz_info(self) -> dict[int, Business]:
        """
        获取业务信息
        {bk_biz_id: Business}
        """

        business_dict = {}
        for tenant in self.tenants:
            if tenant["status"] != "enabled":
                continue
            biz_list = api.cmdb.get_business(all=True, bk_tenant_id=tenant["id"])
            business_dict.update({business.bk_biz_id: business for business in biz_list})
        return business_dict

    @cached_property
    def tenants(self) -> list[dict]:
        """
        获取租户列表
        [
            {"id": "system", "name": "蓝鲸运营", "status": "enabled"},
            {"id": "test", "name": "测试租户", "status": "disabled"},
        ]
        """
        return api.bk_login.list_tenant()

    def biz_exists(self, bk_biz_id):
        """
        业务是否存在
        """
        # 特殊处理tsdb中 tag values为 null的情况
        if bk_biz_id == "null":
            return False
        return bool(bk_biz_id) and int(bk_biz_id) in self.biz_info

    def get_biz_name(self, bk_biz_id):
        """
        根据业务ID获取业务名称
        """
        return self.biz_info[int(bk_biz_id)].bk_biz_name if int(bk_biz_id) in self.biz_info else bk_biz_id


class TimeRange:
    FIVE_MIN = 5 * 60
    ONE_DAY = 60 * 24 * 60
    THREE_DAY = 3 * 60 * 24 * 60
    SEVEN_DAY = 7 * 60 * 24 * 60
    FOURTEEN_DAY = 14 * 60 * 24 * 60
    THIRTY_DAY = 30 * 60 * 24 * 60


TIME_RANGE = [
    ("5m", TimeRange.FIVE_MIN),
    ("1d", TimeRange.ONE_DAY),
    ("3d", TimeRange.THREE_DAY),
    ("7d", TimeRange.SEVEN_DAY),
    ("14d", TimeRange.FOURTEEN_DAY),
    ("30d", TimeRange.THIRTY_DAY),
]
