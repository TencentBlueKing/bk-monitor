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
import time
from abc import ABC, abstractmethod

import pytz


class CachedDiscoverMixin(ABC):
    """
    缓存操作 Mixin 类
    为 Discover 类提供基于 Redis 的缓存管理功能

    使用此 Mixin 的子类需要:
    1. 实现抽象方法: get_cache_type(), to_instance_key(), extract_instance_key_params()
    2. 提供属性: model (Django Model), MAX_COUNT (最大数量), application (应用信息)
    3. 提供属性: bk_biz_id, app_name
    """

    # ========== 子类必须实现的抽象方法 ==========

    @classmethod
    @abstractmethod
    def get_cache_type(cls) -> str:
        """
        获取缓存类型
        子类需要重写此方法，返回 ApmCacheType 中定义的缓存类型
        :return: 缓存类型（如 ApmCacheType.HOST）
        """
        raise NotImplementedError("Subclass must implement get_cache_type()")

    @classmethod
    @abstractmethod
    def to_instance_key(cls, *args) -> str:
        """
        将实例参数转换为唯一的 key
        子类需要重写此方法
        :param args: 实例的关键参数
        :return: 实例 key
        """
        raise NotImplementedError("Subclass must implement to_instance_key()")

    @classmethod
    @abstractmethod
    def extract_instance_key_params(cls, instance: dict) -> tuple:
        """
        从实例字典中提取用于生成 key 的参数
        子类需要重写此方法
        :param instance: 实例数据字典
        :return: 参数元组
        """
        raise NotImplementedError("Subclass must implement extract_instance_key_params()")

    # ========== 通用缓存操作方法 ==========

    @classmethod
    def to_id_and_key(cls, instances: list) -> tuple[set, set]:
        """
        将实例列表转换为 id 集合和 key 集合
        :param instances: 实例列表
        :return: (ids, keys)
        """
        ids, keys = set(), set()
        for inst in instances:
            inst_id = inst.get("id")
            inst_key = cls.to_instance_key(*cls.extract_instance_key_params(inst))
            keys.add(inst_key)
            ids.add(inst_id)
        return ids, keys

    @classmethod
    def merge_data(cls, instances: list, cache_data: dict) -> list:
        """
        合并实例数据和缓存数据，使用缓存中的 updated_at 时间戳
        :param instances: 实例数据列表
        :param cache_data: 缓存数据 {key: timestamp}
        :return: 合并后的数据
        """
        merge_data = []
        for inst in instances:
            key = cls.to_instance_key(*cls.extract_instance_key_params(inst))
            if key in cache_data:
                inst["updated_at"] = datetime.datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(inst)
        return merge_data

    def instance_clear_if_overflow(self, instances: list) -> tuple[list, list]:
        """
        数据量超过 MAX_COUNT 时，清除最旧的数据
        :param instances: 实例数据
        :return: (删除的数据, 保留的数据)
        """
        overflow_delete_data = []
        count = len(instances)
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            # 按照 updated_at 排序，从小到大
            instances.sort(key=lambda item: item.get("updated_at"))
            overflow_delete_data = instances[:delete_count]
            remain_instance_data = instances[delete_count:]
        else:
            remain_instance_data = instances
        return overflow_delete_data, remain_instance_data

    def instance_clear_expired(self, instances: list) -> tuple[list, list]:
        """
        清除过期数据
        :param instances: 实例数据
        :return: (过期的数据, 保留的数据)
        """
        # mysql 中的 updated_at 时间字段, 它的时区是 UTC, 跟数据库保持一致
        boundary = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(
            days=self.application.trace_datasource.retention
        )
        # 按照时间进行过滤
        expired_delete_data = []
        remain_instance_data = []
        for instance in instances:
            if instance.get("updated_at") <= boundary:
                expired_delete_data.append(instance)
            else:
                remain_instance_data.append(instance)
        return expired_delete_data, remain_instance_data

    def query_cache_and_instance_data(self) -> tuple[dict, list]:
        """
        查询缓存数据和数据库数据
        子类可以重写此方法以适配特定的字段需求
        :return: (cache_data, instance_data)
        """
        from apm.core.handlers.apm_cache_handler import ApmCacheHandler

        # 查询应用下的缓存数据 - 使用容器模式
        cache_key = ApmCacheHandler.get_cache_key(self.get_cache_type(), self.bk_biz_id, self.app_name)
        cache_data = ApmCacheHandler().get_cache_data(cache_key)

        # 查询应用下的实例数据 (子类需要根据实际字段调整)
        filter_params = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name}
        # 默认查询 id 和 updated_at，子类可以重写此方法添加其他字段
        instance_data = list(self.model.objects.filter(**filter_params).values("id", "updated_at"))

        return cache_data, instance_data

    def clear_data(self, cache_data: dict, instance_data: list) -> set:
        """
        数据清除(过期 + 超量)
        :param cache_data: 缓存数据
        :param instance_data: mysql 数据
        :return: 需要删除的 instance keys
        """
        merge_data = self.merge_data(instance_data, cache_data)
        # 过期数据
        expired_delete_data, remain_instance_data = self.instance_clear_expired(merge_data)
        # 超量数据
        overflow_delete_data, remain_instance_data = self.instance_clear_if_overflow(remain_instance_data)
        delete_data = expired_delete_data + overflow_delete_data

        delete_ids, delete_keys = self.to_id_and_key(delete_data)
        if delete_ids:
            self.model.objects.filter(pk__in=delete_ids).delete()

        return delete_keys

    def refresh_cache_data(
        self,
        old_cache_data: dict,
        create_instance_keys: set,
        update_instance_keys: set,
        delete_instance_keys: set,
    ):
        """
        刷新 Redis 缓存数据
        :param old_cache_data: 旧的缓存数据
        :param create_instance_keys: 新创建的 instance keys
        :param update_instance_keys: 更新的 instance keys
        :param delete_instance_keys: 删除的 instance keys
        """
        from apm.constants import ApmCacheConfig
        from apm.core.handlers.apm_cache_handler import ApmCacheHandler

        now = int(time.time())
        old_cache_data.update({i: now for i in (create_instance_keys | update_instance_keys)})
        cache_data = {i: old_cache_data[i] for i in (set(old_cache_data.keys()) - delete_instance_keys)}

        # 使用容器模式
        cache_key = ApmCacheHandler.get_cache_key(self.get_cache_type(), self.bk_biz_id, self.app_name)
        cache_expire = ApmCacheConfig.get_expire_time(self.get_cache_type())
        ApmCacheHandler().refresh_data(cache_key, cache_data, cache_expire)
