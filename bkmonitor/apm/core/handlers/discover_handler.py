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
import datetime
from typing import Optional

import pytz
from django.utils.translation import gettext_lazy as _

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
        trace_datasource: Optional[TraceDataSource] = TraceDataSource.objects.filter(
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
