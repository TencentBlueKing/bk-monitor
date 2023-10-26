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

from django.db import models
from monitor_web.models import OperateRecordModelBase

from bkmonitor.utils.db import JsonField


class QueryHistory(OperateRecordModelBase):
    """
    数据检索收藏记录
    """

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    type = models.CharField("类型", default="time_series", max_length=32)
    name = models.CharField("名称", max_length=64)
    config = JsonField("查询配置")
    # 0为私有分组，null为未分组
    group_id = models.IntegerField("分组ID", default=None, null=True)
    public = models.BooleanField("是否公开", default=True)

    class Meta:
        verbose_name = "数据检索收藏记录"
        verbose_name_plural = verbose_name


class FavoriteGroup(OperateRecordModelBase):
    """
    数据检索收藏组
    """

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    type = models.CharField("类型", default="metric", max_length=32)
    name = models.CharField("名称", max_length=64)
    order = models.JSONField("排序配置", default=list)

    class Meta:
        verbose_name = "数据检索收藏组"
        verbose_name_plural = verbose_name

    @property
    def group_order(self) -> list:
        return self.get_group_order(self.bk_biz_id, self.type)

    @group_order.setter
    def group_order(self, order: list):
        self.set_group_order(self.bk_biz_id, self.type, order)

    @classmethod
    def get_group_order(cls, bk_biz_id: int, query_type: str) -> list:
        """
        获取组间排序
        """
        from monitor.models import ApplicationConfig

        order_record = ApplicationConfig.objects.filter(
            cc_biz_id=bk_biz_id,
            key=f"{query_type}_favorite_group_order",
        ).first()

        if order_record:
            return order_record.value
        return []

    @classmethod
    def set_group_order(cls, bk_biz_id: int, query_type: str, order: list):
        """
        设置组间排序
        """
        from monitor.models import ApplicationConfig

        ApplicationConfig.objects.update_or_create(
            cc_biz_id=bk_biz_id,
            key=f"{query_type}_favorite_group_order",
            defaults={"value": order},
        )
