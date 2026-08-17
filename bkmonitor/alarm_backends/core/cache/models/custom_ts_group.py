"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from alarm_backends.core.cache.base import CacheManager
from core.drf_resource import api
from core.errors.api import BKAPIError

if TYPE_CHECKING:
    from metadata.models import TimeSeriesGroup


class CustomTSGroupCacheManager(CacheManager):
    """
    自定义指标分组缓存[无过期时间]
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".ts_group{bk_data_id}"

    @classmethod
    def format_key(cls, bk_data_id: int) -> str:
        return cls.CACHE_KEY_TEMPLATE.format(bk_data_id=bk_data_id)

    @staticmethod
    def get_default_protocol(ts_group: "TimeSeriesGroup") -> str:
        """获取 monitor_web 中不存在自定义指标记录时的默认协议。"""
        return "prometheus" if ts_group.is_cmdb_relation_builtin() else "json"

    @classmethod
    def query_protocol(cls, ts_group: "TimeSeriesGroup") -> str:
        """通过专用接口查询单个自定义指标协议。"""
        protocol_infos = api.monitor.query_custom_time_series_protocols(
            bk_tenant_id=ts_group.bk_tenant_id,
            bk_data_ids=[ts_group.bk_data_id],
        )
        if not protocol_infos:
            return cls.get_default_protocol(ts_group)
        return protocol_infos[0]["protocol"]

    @classmethod
    def query_protocol_from_detail(cls, ts_group: "TimeSeriesGroup") -> str:
        """兼容新接口不可用时通过原详情接口查询协议。"""
        ts_info = api.metadata.custom_time_series_detail(
            bk_tenant_id=ts_group.bk_tenant_id,
            time_series_group_id=ts_group.time_series_group_id,
            bk_biz_id=ts_group.bk_biz_id,
            model_only=True,
            empty_if_not_found=True,
        )
        if not ts_info:
            return cls.get_default_protocol(ts_group)
        return ts_info["protocol"]

    @classmethod
    def get(cls, bk_data_id) -> str | None:
        """
        根据配置ID获取采集配置
        """
        protocol = cls.cache.get(cls.format_key(bk_data_id))
        if not protocol:
            try:
                from metadata.models import TimeSeriesGroup

                ts_group = TimeSeriesGroup.objects.get(bk_data_id=bk_data_id)
            except TimeSeriesGroup.DoesNotExist:
                return None

            try:
                protocol = cls.query_protocol(ts_group)
            except BKAPIError:
                try:
                    protocol = cls.query_protocol_from_detail(ts_group)
                except BKAPIError:
                    return "json"

            cls.set(bk_data_id, protocol)

        return protocol

    @classmethod
    def set(cls, bk_data_id: int, protocol: str) -> None:
        cls.cache.set(cls.format_key(bk_data_id), protocol)

    @classmethod
    def refresh(cls) -> None:
        """按租户批量刷新全部自定义指标协议缓存。"""
        from metadata.models import TimeSeriesGroup

        ts_groups = list(
            TimeSeriesGroup.objects.filter(is_delete=False).only(
                "bk_data_id",
                "bk_biz_id",
                "bk_tenant_id",
                "time_series_group_id",
                "time_series_group_name",
            )
        )
        tenant_groups: dict[str, list[TimeSeriesGroup]] = defaultdict(list)
        for ts_group in ts_groups:
            tenant_groups[ts_group.bk_tenant_id].append(ts_group)

        pipeline = cls.cache.pipeline()
        refreshed_count = 0
        failed_tenants: list[str] = []
        for bk_tenant_id, groups in tenant_groups.items():
            try:
                protocol_infos = api.monitor.query_custom_time_series_protocols(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=0,
                    bk_data_ids=[],
                )
            except BKAPIError:
                failed_tenants.append(bk_tenant_id)
                cls.logger.exception(
                    "refresh custom time series protocols failed, bk_tenant_id: %s",
                    bk_tenant_id,
                )
                continue

            protocol_mapping = {info["bk_data_id"]: info["protocol"] for info in protocol_infos}
            for ts_group in groups:
                protocol = protocol_mapping.get(ts_group.bk_data_id, cls.get_default_protocol(ts_group))
                pipeline.set(cls.format_key(ts_group.bk_data_id), protocol)
                refreshed_count += 1

        pipeline.execute()

        cls.logger.info(
            "refresh custom time series protocols finished, amount: %s, failed_tenants: %s",
            refreshed_count,
            failed_tenants,
        )


def main():
    CustomTSGroupCacheManager.refresh()
