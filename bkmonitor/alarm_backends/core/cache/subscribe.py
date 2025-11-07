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

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.assign import AssignCacheManager
from bkmonitor.models.strategy import NoticeSubscribe
from bkmonitor.utils import extended_json
from bkmonitor.utils.local import local
from alarm_backends.core.cache.cmdb.business import BusinessManager
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id

setattr(local, "subscribe_cache", {})


class SubscribeCacheManager(CacheManager):
    """
    订阅缓存管理器

    业务下的订阅用户列表：monitor.cache.subscribe.biz_{bk_biz_id} -> [username, ...]
    用户在某业务下的订阅规则列表：monitor.cache.subscribe.user_{bk_biz_id}_{username} -> [rule, ...]
    """

    # 缓存 Key 模板
    BIZ_USERS_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".subscribe.biz_{bk_biz_id}"
    USER_RULES_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".subscribe.user_{bk_biz_id}_{username}"

    @classmethod
    def clear(cls):
        return local.subscribe_cache.clear()

    @classmethod
    def _local_get(cls, cache_key):
        return local.subscribe_cache.get(cache_key)

    @classmethod
    def _local_set(cls, cache_key, value):
        local.subscribe_cache[cache_key] = value
        return value

    @classmethod
    def get_users_by_biz(cls, bk_biz_id):
        """
        按业务获取订阅用户列表
        :param bk_biz_id: 业务ID
        """
        cache_key = cls.BIZ_USERS_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id)
        value = cls._local_get(cache_key)
        if value is not None:
            return value

        cached = cls.cache.get(cache_key)
        if cached:
            users = extended_json.loads(cached)
        else:
            users = []
        return cls._local_set(cache_key, users)

    @classmethod
    def get_rules_by_user(cls, bk_biz_id, username):
        """
        按业务与用户获取订阅规则列表
        :param bk_biz_id: 业务ID
        :param username: 用户名
        """
        cache_key = cls.USER_RULES_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, username=username)
        value = cls._local_get(cache_key)
        if value is not None:
            return value

        cached = cls.cache.get(cache_key)
        if cached:
            rules = extended_json.loads(cached)
        else:
            rules = []
        return cls._local_set(cache_key, rules)

    @classmethod
    def _parse_rule(cls, bk_tenant_id: str, sub: NoticeSubscribe) -> dict:
        """处理订阅记录为缓存规则结构，按分派实时匹配使用"""
        conditions = []
        for condition in sub.conditions or []:
            # 动态分组转换，将动态分组转换成主机列表
            conditions.append(AssignCacheManager.parse_dynamic_group(bk_tenant_id, condition))

        return {
            "id": sub.id,
            "priority": sub.priority,
            "user_type": sub.user_type,
            "notice_ways": list(sub.notice_ways or []),
            "conditions": conditions,
        }

    @classmethod
    def refresh(cls):
        """
        刷新订阅缓存
        仅缓存 is_enable = True 的订阅
        """
        # 获取所有业务列表
        biz_list = BusinessManager.all()
        biz_id_list = [biz.bk_biz_id for biz in biz_list]

        # 查询启用的订阅
        qs = NoticeSubscribe.objects.filter(is_enable=True)

        # 按业务聚合用户、按用户聚合规则
        biz_to_users: dict[int, set[str]] = defaultdict(set)
        user_rules: dict[tuple[int, str], list[dict]] = defaultdict(list)

        for sub in qs.order_by("bk_biz_id", "username", "-priority", "id").iterator(chunk_size=1000):
            biz_to_users[sub.bk_biz_id].add(sub.username)
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(sub.bk_biz_id)
            user_rules[(sub.bk_biz_id, sub.username)].append(cls._parse_rule(bk_tenant_id, sub))

        pipeline = cls.cache.pipeline()

        # 基于旧缓存与新结果对比，按业务精确清理并重建用户规则键，再更新业务-用户列表
        for bk_biz_id in biz_id_list:
            new_users = sorted(biz_to_users.get(bk_biz_id, set()))
            old_users = set(cls.get_users_by_biz(bk_biz_id))

            # 1 删除多余用户的规则键
            stale_users = old_users.difference(new_users)
            for username in stale_users:
                pipeline.delete(cls.USER_RULES_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, username=username))

            # 2 对现有用户的规则键执行“先删后写”的整键重建
            for username in new_users:
                cache_key = cls.USER_RULES_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id, username=username)
                pipeline.delete(cache_key)
                pipeline.set(cache_key, extended_json.dumps(user_rules[(bk_biz_id, username)]), cls.CACHE_TIMEOUT)

            # 3 更新业务-用户列表键
            biz_users_key = cls.BIZ_USERS_CACHE_KEY_TEMPLATE.format(bk_biz_id=bk_biz_id)
            if new_users:
                pipeline.set(biz_users_key, extended_json.dumps(new_users), cls.CACHE_TIMEOUT)
            else:
                pipeline.delete(biz_users_key)

        pipeline.execute()


def main():
    SubscribeCacheManager.refresh()
