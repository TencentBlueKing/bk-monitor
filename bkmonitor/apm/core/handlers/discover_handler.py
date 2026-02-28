"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime

import pytz
from django.utils.translation import gettext_lazy as _

from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.models import HostInstance, TraceDataSource
from core.drf_resource.exceptions import CustomException


class DiscoverHandler:
    @classmethod
    def get_retention_filter_params(cls, bk_biz_id, app_name):
        retention = cls.get_app_retention(bk_biz_id, app_name)
        # 获取过期分界线
        last = datetime.datetime.now() - datetime.timedelta(retention)
        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "updated_at__gte": last,
        }

    @classmethod
    def get_host_instance(cls, bk_biz_id, ip, bk_cloud_id):
        return HostInstance.objects.filter(bk_biz_id=bk_biz_id, ip=ip, bk_cloud_id=bk_cloud_id).first()

    @classmethod
    def get_app_retention(cls, bk_biz_id, app_name):
        trace_datasource: TraceDataSource | None = TraceDataSource.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name
        ).first()
        if not trace_datasource:
            raise CustomException(_("业务下的应用: {} 未开启 Trace").format(app_name))
        return trace_datasource.retention

    @classmethod
    def get_retention_utc_filter_params(cls, bk_biz_id, app_name):
        """
        topo instance 数据中的updated_at字段, 它的时区是UTC, 防止updated_at字段时区不一致导致的报错
        报错信息： TypeError: can‘t subtract offset-naive and offset-aware datetimes
        :param bk_biz_id: 业务ID
        :param app_name: 应用名称
        :return:
        """
        retention = cls.get_app_retention(bk_biz_id, app_name)
        # 获取过期分界线
        last = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(retention)
        return {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "updated_at__gte": last,
        }

    @classmethod
    def batch_merge_cache_updated_time(cls, bk_biz_id, app_name, cache_type, objs, discover_class):
        """
        批量从缓存中获取更新时间，并与数据库的时间合并
        :param bk_biz_id: 业务ID
        :param app_name: 应用名称
        :param cache_type: 缓存类型（来自 ApmCacheType）
        :param objs: 数据库对象列表
        :param discover_class: Discover 类（如 EndpointDiscover, HostDiscover）
        :return: 对象ID到更新时间的映射字典 {obj_id: updated_at}
        """
        # 一次性从 Redis 获取所有缓存数据
        cache_name = ApmCacheHandler.get_cache_key(cache_type, bk_biz_id, app_name)
        cache_data = ApmCacheHandler().get_cache_data(cache_name)

        # 批量处理所有对象
        id_to_updated_at = {}
        for obj in objs:
            instance_data = discover_class.build_instance_data(obj)
            cache_key = discover_class.to_cache_key(instance_data)

            # 获取时间戳，优先使用缓存中的时间，如果缓存中没有则使用数据库的 updated_at
            updated_at = obj.updated_at
            if cache_key in cache_data:
                updated_at = datetime.datetime.fromtimestamp(cache_data[cache_key], tz=pytz.UTC)

            id_to_updated_at[obj.id] = updated_at

        return id_to_updated_at
