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
import logging

import pytz
from apm.constants import ApmCacheConfig
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.core.discover.instance_data import BaseInstanceData

logger = logging.getLogger("apm")


class CachedDiscoverMixin(ABC):
    """
    缓存操作 Mixin 类
    为 Discover 类提供基于 Redis 的缓存管理功能

    使用此 Mixin 的子类需要:
    1. 实现抽象方法: _get_cache_type(), _to_instance_key(), _build_instance_data()
    2. 提供属性: model (Django Model), MAX_COUNT (最大数量), application (应用信息)
    3. 提供属性: bk_biz_id, app_name
    """

    # ========== 子类必须实现的抽象方法 ==========

    @classmethod
    @abstractmethod
    def _get_cache_type(cls) -> str:
        """
        获取缓存类型
        子类需要重写此方法，返回 ApmCacheType 中定义的缓存类型
        :return: 缓存类型（如 ApmCacheType.HOST）
        """
        raise NotImplementedError("Subclass must implement get_cache_type()")

    @classmethod
    @abstractmethod
    def _to_instance_key(cls, instance: BaseInstanceData) -> str:
        """
        从实例数据对象生成唯一的 key
        子类需要重写此方法，直接从 instance 对象中提取所需字段并生成 key
        :param instance: 实例数据对象
        :return: 实例 key
        """
        raise NotImplementedError("Subclass must implement to_instance_key()")

    @staticmethod
    @abstractmethod
    def _build_instance_data(instance_obj) -> BaseInstanceData:
        """
        构建实例数据对象的辅助方法
        子类需要重写此方法，定义如何从数据库对象或字典构建标准实例数据对象
        :param instance_obj: 数据库对象或字典
        :return: BaseInstanceData 的子类实例
        """
        raise NotImplementedError("Subclass must implement _build_instance_data()")

    # ========== 通用缓存操作方法 ==========

    @staticmethod
    def _get_attr_value(obj, attr_name):
        """
        统一的属性获取方法
        支持从 ORM 对象或字典中获取属性值
        :param obj: ORM 对象或字典
        :param attr_name: 属性名称
        :return: 属性值
        """
        if hasattr(obj, attr_name):
            return getattr(obj, attr_name)
        return obj.get(attr_name) if isinstance(obj, dict) else None

    @classmethod
    def _process_duplicate_records(
        cls, db_instances, delete_duplicates: bool = False, keep_last: bool = False
    ) -> dict[str, BaseInstanceData]:
        """
        处理重复数据的通用方法
        :param db_instances: 数据库查询结果（QuerySet 或列表）
        :param delete_duplicates: 是否删除重复记录，默认为 False
        :param keep_last: 是否保留最后一条记录（ID 最大），False 则保留第一条（ID 最小），默认为 False
        :return: 去重后的字典映射，key 为实例 key，value 为 BaseInstanceData 实例
        """
        exists_mapping = {}
        for instance in db_instances:
            # 构建实例数据对象
            instance_data = cls._build_instance_data(instance)
            # 获取唯一键
            key = cls._to_instance_key(instance_data)
            if key not in exists_mapping:
                exists_mapping[key] = []
            exists_mapping[key].append(instance_data)

        # 处理重复数据并构建最终结果
        res = {}
        need_delete_ids = []

        for key, records in exists_mapping.items():
            records.sort(key=lambda x: x.id)
            keep_record = records[-1] if keep_last else records[0]

            # 收集需要删除的重复记录ID（仅在 delete_duplicates=True 时）
            if len(records) > 1 and delete_duplicates:
                if keep_last:
                    need_delete_ids.extend([r.id for r in records[:-1]])
                else:
                    need_delete_ids.extend([r.id for r in records[1:]])

            # 保留的记录
            res[key] = keep_record

        # 执行数据库删除操作
        if need_delete_ids:
            # 注意：这里需要子类提供 model 属性
            cls.model.objects.filter(id__in=need_delete_ids).delete()
            logger.info(f"[{cls.__name__}] Deleted {len(need_delete_ids)} duplicate records: {need_delete_ids}")

        return res

    def handle_cache_refresh_after_create(
        self,
        existing_instances: list[BaseInstanceData],
        created_db_instances: list,
        updated_instances: list[BaseInstanceData],
    ):
        """
        处理创建实例后的缓存刷新逻辑
        这是一个通用方法，用于在 bulk_create 之后更新缓存

        :param existing_instances: 已存在的实例数据列表 (从数据库查询得到)
        :param created_db_instances: 新创建的数据库对象列表 (bulk_create 返回的对象)
        :param updated_instances: 需要更新的实例数据列表
        """
        cache_data = self._query_cache_data()

        # 将新创建的数据库对象转换为数据类对象
        created_instance_data: list[BaseInstanceData] = []
        create_instance_keys = set()
        if created_db_instances:
            created_instance_data = [self._build_instance_data(db_obj) for db_obj in created_db_instances]
            _, create_instance_keys = self._to_id_and_key(created_instance_data)

        # 合并已存在的和新创建的实例数据
        all_instance_data: list[BaseInstanceData] = existing_instances + created_instance_data

        # 计算需要删除的实例（过期或超量）
        delete_instance_keys = self._clear_data(cache_data, all_instance_data)

        # 计算需要更新的实例 keys
        _, update_instance_keys = self._to_id_and_key(updated_instances)

        # 刷新缓存
        self._refresh_cache_data(
            old_cache_data=cache_data,
            create_instance_keys=create_instance_keys,
            update_instance_keys=update_instance_keys,
            delete_instance_keys=delete_instance_keys,
        )
        logger.info(
            f"update_instance_keys: {update_instance_keys}, "
            f"create_instance_keys: {create_instance_keys}, "
            f"delete_instance_keys: {delete_instance_keys}"
        )

    @classmethod
    def _to_id_and_key(cls, instances: list[BaseInstanceData]) -> tuple[set, set]:
        """
        将实例列表转换为 id 集合和 key 集合
        :param instances: 实例列表
        :return: (ids, keys)
        """
        ids, keys = set(), set()
        for inst in instances:
            inst_id = inst.id
            inst_key = cls._to_instance_key(inst)
            keys.add(inst_key)
            ids.add(inst_id)
        return ids, keys

    @classmethod
    def _merge_data(cls, instances: list[BaseInstanceData], cache_data: dict) -> list[BaseInstanceData]:
        """
        合并实例数据和缓存数据，使用缓存中的 updated_at 时间戳
        :param instances: 实例数据列表
        :param cache_data: 缓存数据 {key: timestamp}
        :return: 合并后的数据
        """
        merge_data = []
        for inst in instances:
            key = cls._to_instance_key(inst)
            if key in cache_data:
                inst.updated_at = datetime.datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(inst)
        return merge_data

    def _instance_clear_if_overflow(self, instances: list[BaseInstanceData]) -> tuple[list, list]:
        """
        数据量超过 MAX_COUNT 时,清除最旧的数据
        :param instances: 实例数据
        :return: (删除的数据, 保留的数据)
        """
        overflow_delete_data = []
        count = len(instances)
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            # 按照 updated_at 排序,从小到大
            # 将 None 值视为最新时间(使用 datetime.max),优先保留新创建的实例
            instances.sort(key=lambda item: item.updated_at or datetime.datetime.max.replace(tzinfo=pytz.UTC))
            overflow_delete_data = instances[:delete_count]
            remain_instance_data = instances[delete_count:]
        else:
            remain_instance_data = instances
        return overflow_delete_data, remain_instance_data

    def _instance_clear_expired(self, instances: list[BaseInstanceData]) -> tuple[list, list]:
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
            updated_at = instance.updated_at
            # 跳过 updated_at 为 None 的实例(新创建的实例),将其保留
            if updated_at is None:
                remain_instance_data.append(instance)
            elif updated_at <= boundary:
                expired_delete_data.append(instance)
            else:
                remain_instance_data.append(instance)
        return expired_delete_data, remain_instance_data

    def _query_cache_data(self) -> dict:
        """
        查询缓存数据
        :return: cache_data
        """
        cache_key = ApmCacheHandler.get_cache_key(self._get_cache_type(), self.bk_biz_id, self.app_name)
        return ApmCacheHandler().get_cache_data(cache_key)

    def _clear_data(self, cache_data: dict, instance_data: list[BaseInstanceData]) -> set:
        """
        数据清除(过期 + 超量)
        :param cache_data: 缓存数据
        :param instance_data: mysql 数据
        :return: 需要删除的 instance keys
        """
        merge_data = self._merge_data(instance_data, cache_data)
        # 过期数据
        expired_delete_data, remain_instance_data = self._instance_clear_expired(merge_data)
        # 超量数据
        overflow_delete_data, remain_instance_data = self._instance_clear_if_overflow(remain_instance_data)
        delete_data = expired_delete_data + overflow_delete_data

        delete_ids, delete_keys = self._to_id_and_key(delete_data)
        if delete_ids:
            self.model.objects.filter(pk__in=delete_ids).delete()

        return delete_keys

    def _refresh_cache_data(
        self,
        old_cache_data: dict,
        create_instance_keys: set,
        update_instance_keys: set,
        delete_instance_keys: set,
    ):
        """刷新 Redis 缓存数据"""
        now = int(time.time())

        # 先过滤要删除的 keys，再添加新的/更新的
        cache_data = {key: val for key, val in old_cache_data.items() if key not in delete_instance_keys}
        cache_data.update({key: now for key in create_instance_keys | update_instance_keys})

        cache_key = ApmCacheHandler.get_cache_key(self._get_cache_type(), self.bk_biz_id, self.app_name)
        cache_expire = ApmCacheConfig.get_expire_time(self._get_cache_type())
        ApmCacheHandler().refresh_data(cache_key, cache_data, cache_expire)
