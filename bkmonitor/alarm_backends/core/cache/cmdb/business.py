"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.storage.redis import Cache
from api.cmdb.define import Business
from constants.common import DEFAULT_TENANT_ID


class BusinessManager:
    """
    CMDB 业务缓存
    """

    cache_key = f"{CacheManager.CACHE_KEY_PREFIX}.cmdb.business"
    cache = Cache("cache-cmdb")

    @classmethod
    def get(cls, bk_biz_id: int) -> Business | None:
        result: str | None = cls.cache.hget(cls.cache_key, str(bk_biz_id))
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
        return [int(key) for key in cls.cache.hkeys(cls.cache_key)]

    @classmethod
    def all(cls) -> list[Business]:
        """
        获取全部业务
        """
        result = cls.cache.hgetall(cls.cache_key)
        return [Business(**json.loads(value)) for value in result.values() if value]
