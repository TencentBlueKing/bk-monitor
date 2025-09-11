"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import cast

from api.cmdb.define import Business
from constants.common import DEFAULT_TENANT_ID

from .base import CMDBCacheManager


class BusinessManager(CMDBCacheManager):
    """
    CMDB 业务缓存
    """

    cache_type = "business"

    @classmethod
    def get(cls, bk_biz_id: int | str, **kwargs) -> Business | None:
        result: str | None = cast(str | None, cls.cache.hget(cls.get_cache_key(DEFAULT_TENANT_ID), str(bk_biz_id)))
        if not result:
            return None

        business: dict = json.loads(result)
        # 兼容旧数据，补充租户ID字段
        if not business.get("bk_tenant_id"):
            business["bk_tenant_id"] = DEFAULT_TENANT_ID

        return Business(**business)

    @classmethod
    def keys(cls) -> list[int]:
        """
        获取业务ID列表
        """
        result: list[str] = cast(list[str], cls.cache.hkeys(cls.get_cache_key(DEFAULT_TENANT_ID)))
        return [int(key) for key in result]

    @classmethod
    def all(cls) -> list[Business]:
        """
        获取全部业务
        """
        result = cast(dict[str, str], cls.cache.hgetall(cls.get_cache_key(DEFAULT_TENANT_ID)))
        return [Business(**json.loads(value)) for value in result.values() if value]
