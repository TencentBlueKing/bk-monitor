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

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager
from api.cmdb.define import Business
from core.drf_resource import api


class BusinessManager(CMDBCacheManager):
    """
    CMDB 业务缓存
    """

    type = "biz"
    CACHE_KEY = "{prefix}.cmdb.business".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)
    ObjectClass = Business

    @classmethod
    def key_to_internal_value(cls, bk_biz_id):
        return str(bk_biz_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        """
        取出key时进行转化
        """
        return int(origin_key)

    @classmethod
    def get(cls, bk_biz_id):
        """
        :param bk_biz_id: 获取业务ID
        :rtype: Business
        """
        return super(BusinessManager, cls).get(bk_biz_id)

    @classmethod
    def refresh(cls):
        """
        刷新业务数据
        """
        cls.logger.info("refresh CMDB Business data started.")

        business_list = api.cmdb.get_business(all=True)  # type: list[Business]
        pipeline = cls.cache.pipeline()
        for business in business_list:
            pipeline.hset(cls.CACHE_KEY, cls.key_to_internal_value(business.bk_biz_id), cls.serialize(business))

        pipeline.expire(cls.CACHE_KEY, cls.CACHE_TIMEOUT)
        pipeline.execute()

        # 差值比对需要删除的业务
        new_keys = [cls.key_to_internal_value(business.bk_biz_id) for business in business_list]
        old_keys = cls.cache.hkeys(cls.CACHE_KEY)
        deleted_keys = set(old_keys) - set(new_keys)
        pipeline = cls.cache.pipeline()
        for key in deleted_keys:
            pipeline.hdel(cls.CACHE_KEY, key)

        pipeline.expire(cls.CACHE_KEY, cls.CACHE_TIMEOUT)
        pipeline.execute()

        cls.logger.info(
            "refresh CMDB Business data finished, amount: updated: {}, removed: {}".format(
                len(new_keys), len(deleted_keys)
            )
        )


def main():
    if "business" in settings.DISABLE_ALARM_CMDB_CACHE_REFRESH:
        return
    BusinessManager.refresh()
