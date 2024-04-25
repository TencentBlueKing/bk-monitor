# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import abc
import datetime
import logging
from typing import Type

from django.utils import timezone

from apm.core.handlers.profile.query import ProfileQueryBuilder
from apm.models import ProfileDataSource

logger = logging.getLogger("apm")


class Discover(abc.ABC):
    MAX_COUNT = 100000

    @classmethod
    def get_name(cls):
        raise NotImplementedError

    def __init__(self, datasource):
        self.datasource = datasource
        self.bk_biz_id = datasource.bk_biz_id
        self.app_name = datasource.app_name
        self.retention = datasource.retention
        self.result_table_id = datasource.result_table_id

    def discover(self, start_time, end_time):
        raise NotImplementedError

    def get_builder(self):
        return ProfileQueryBuilder.from_table(self.result_table_id, self.bk_biz_id, self.app_name)

    def clear_if_overflow(self, model):
        count = model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).count()
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            delete_pks = model.objects.order_by("updated_at").values_list("pk", flat=True)[:delete_count]
            model.objects.filter(pk__in=list(delete_pks)).delete()

    def clear_expired(self, model):
        # clean expired topo data based on expiration
        boundary = datetime.datetime.now() - datetime.timedelta(self.retention)
        filter_params = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name, "updated_at__lte": boundary}

        model.objects.filter(**filter_params).delete()


class DiscoverContainers:
    _DISCOVERS = {}

    @classmethod
    def register(cls, discover: Type[Discover]):
        if cls._DISCOVERS.get(discover.get_name()):
            raise ValueError
        cls._DISCOVERS[discover.get_name()] = discover

    @classmethod
    def all_discovers(cls):
        return cls._DISCOVERS


class DiscoverHandler:
    # 根据最近10分钟数据进行分析
    TIME_DELTA = 10

    def __init__(self, bk_biz_id: int, app_name: str):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.datasource = ProfileDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not self.datasource:
            raise ValueError(f"{app_name}({bk_biz_id}) profile datasource not found")

    def discover(self):
        end_time = timezone.now()
        start_time = end_time - datetime.timedelta(minutes=self.TIME_DELTA)

        for name, i in DiscoverContainers.all_discovers().items():
            i(self.datasource).discover(int(start_time.timestamp() * 1000), int(end_time.timestamp() * 1000))
            logger.info(f"[DiscoverHandler] {name} finished")
