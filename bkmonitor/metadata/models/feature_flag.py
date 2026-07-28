"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging
import re
import threading
import time
from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.db import connection, models, transaction
from metadata import config
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools
from bkmonitor.utils.db.fields import JsonField

logger = logging.getLogger("metadata")
feature_flag_publication_thread_lock = threading.Lock()


class FeatureFlagQuerySet(models.QuerySet):
    def delete(self):
        """批量删除后只发布一次最新的完整配置快照。"""
        flag_names = list(self.values_list("flag_name", flat=True))
        result = super().delete()
        if flag_names:
            summary = ",".join(flag_names)
            transaction.on_commit(
                lambda: self.model._refresh_external_config(summary, "bulk deleted")
            )
        return result


class FeatureFlag(models.Model):
    """
    特性开关数据库模型
    用于存储特性开关配置信息，包括 variations、targeting、defaultRule 等
    """

    flag_id = models.AutoField("特性开关ID", primary_key=True)
    flag_name = models.CharField("特性开关名称", max_length=128, unique=True, db_index=True)
    description = models.CharField("描述", max_length=512, default="", blank=True)
    config = JsonField("配置信息", default=dict)  # 包含 variations、targeting、defaultRule 等字段
    is_enabled = models.BooleanField("是否启用", default=True, db_index=True)
    creator = models.CharField("创建者", max_length=32, default="system")
    updater = models.CharField("变更人", max_length=32, default="system")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = FeatureFlagQuerySet.as_manager()
    PUBLICATION_LOCK_NAME = "metadata_feature_flag_publication"

    class Meta:
        db_table = "metadata_featureflag"
        verbose_name = "特性开关"
        verbose_name_plural = "特性开关"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.flag_name} ({'启用' if self.is_enabled else '禁用'})"

    def to_config_dict(self) -> dict:
        """
        将数据库记录转换为配置字典格式
        用于写入 Consul/Redis

        :return: 配置字典，包含 variations、targeting、defaultRule 等字段
        """
        return self.config if isinstance(self.config, dict) else {}

    @classmethod
    @contextmanager
    def _publication_lock(cls):
        """在进程内及 MySQL 多进程间串行发布，且不依赖作为同步目标的 Redis。"""
        with feature_flag_publication_thread_lock:
            if connection.vendor != "mysql":
                yield
                return

            with connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, %s)", [cls.PUBLICATION_LOCK_NAME, 60])
                acquired = cursor.fetchone()[0]
                if acquired != 1:
                    raise RuntimeError("timed out acquiring feature flag publication lock")
                try:
                    yield
                finally:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [cls.PUBLICATION_LOCK_NAME])

    @classmethod
    def _refresh_external_config(
        cls,
        flag_name: str,
        action: str,
        raise_on_failure: bool = False,
    ) -> None:
        """事务提交后将数据库快照分别同步到 Consul 和 Redis。"""
        try:
            # 多进程事务回调必须串行：持锁后再读取数据库，保证最后发布的一定是最新已提交快照。
            with cls._publication_lock():
                feature_flags = {}
                for feature_flag in cls.objects.filter(is_enabled=True):
                    config_dict = feature_flag.to_config_dict()
                    if config_dict:
                        feature_flags[feature_flag.flag_name] = config_dict

                failed_backends = []
                for backend, refresher in (
                    ("consul", FeatureFlagConfig.refresh_consul_feature_flag_config),
                    ("redis", FeatureFlagConfig.refresh_redis_feature_flag_config),
                ):
                    try:
                        refresher(feature_flags)
                    except Exception:  # pylint: disable=broad-except
                        failed_backends.append(backend)
                        logger.exception(
                            "refresh feature flag config to %s failed after %s, flag_name->[%s]",
                            backend,
                            action,
                            flag_name,
                        )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "acquire feature flag publication lock failed after %s, flag_name->[%s]",
                action,
                flag_name,
            )
            if raise_on_failure:
                raise
            return

        if failed_backends:
            logger.error(
                "feature flag [%s] %s but config refresh failed for backends->[%s]",
                flag_name,
                action,
                ",".join(failed_backends),
            )
            if raise_on_failure:
                raise RuntimeError(
                    f"refresh feature flag config failed for backends: {','.join(failed_backends)}"
                )
        else:
            logger.info(
                "feature flag [%s] %s and config refreshed to consul and redis",
                flag_name,
                action,
            )

    def save(self, *args, **kwargs):
        """
        重写 save 方法，在保存特性开关配置后自动刷新到 Consul 和 Redis

        功能说明：
        1. 自动设置创建人和变更人字段
        2. 调用父类的 save 方法保存到数据库
        3. 如果特性开关是启用的状态，刷新配置到 Consul 和 Redis
        4. 如果特性开关被禁用，从 Consul 和 Redis 中移除该配置

        使用场景：
        - 管理员在界面上修改特性开关配置后，自动同步到配置中心
        - 确保配置变更能够及时生效

        :param args: 位置参数
        :param kwargs: 关键字参数，支持 operator 参数指定操作人
        """
        # 1. 自动设置创建人和变更人字段
        operator = kwargs.pop("operator", None)
        if operator is None:
            # 尝试从线程本地存储获取当前用户
            try:
                from bkmonitor.utils.user import get_global_user

                operator = get_global_user()
            except Exception:
                pass

        if operator is None:
            operator = "system"

        # 如果是新创建的对象，设置创建人
        if not self.pk:
            if not self.creator or self.creator == "system":
                self.creator = operator

        # 设置变更人
        self.updater = operator
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"updater", "updated_at"}

        # 2. 调用父类的 save 方法
        super().save(*args, **kwargs)

        # 3. 事务提交成功后再发布，避免外部配置中心看到最终回滚的数据。
        flag_name = self.flag_name
        transaction.on_commit(lambda: type(self)._refresh_external_config(flag_name, "saved"))

    def delete(self, *args, **kwargs):
        """
        重写 delete 方法，在删除特性开关后自动刷新配置到 Consul 和 Redis

        功能说明：
        1. 记录要删除的特性开关名称
        2. 调用父类的 delete 方法删除数据库记录
        3. 刷新配置到 Consul 和 Redis（自动排除已删除的配置）

        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        # 1. 记录要删除的特性开关名称
        flag_name = self.flag_name

        # 2. 调用父类的 delete 方法
        super().delete(*args, **kwargs)

        # 3. 事务提交成功后再发布，查询结果会自动排除已删除配置。
        transaction.on_commit(lambda: type(self)._refresh_external_config(flag_name, "deleted"))


class FeatureFlagConfig:
    """
    特性开关配置管理类
    用于管理特性开关配置的读取和写入，支持 Redis 和 Consul 两种存储方式
    参考 storage.py 中 ClusterInfo 的实现方式
    """

    # Consul 配置路径
    CONSUL_PREFIX_PATH = f"{config.MIGRATION_CONSUL_PATH}/unify-query/data/feature_flag"
    CONSUL_VERSION_PATH = f"{config.MIGRATION_CONSUL_PATH}/unify-query/version/feature_flag"

    # Redis 配置路径，参考 Consul 路径结构
    REDIS_PREFIX_KEY = f"{settings.BACKEND_APP_CODE}:unify-query:data:feature_flag"
    REDIS_CHANNEL = f"{REDIS_PREFIX_KEY}:feature_flag_channel"
    # REDIS_VERSION_KEY = f"{config.REDIS_KEY_PREFIX}:unify-query:version:feature_flag"

    @classmethod
    def _write_redis_feature_flags(cls, feature_flags: dict):
        """原子更新聚合配置后通知 UQ 重新加载。"""
        redis_client = RedisTools().client
        if feature_flags:
            redis_client.set(cls.REDIS_PREFIX_KEY, json.dumps(feature_flags))
        else:
            redis_client.delete(cls.REDIS_PREFIX_KEY)
        redis_client.publish(
            cls.REDIS_CHANNEL,
            json.dumps({"feature_flags": sorted(feature_flags), "timestamp": time.time()}),
        )

    @classmethod
    def refresh_consul_feature_flag_config_from_db(cls):
        """
        从数据库读取特性开关配置并刷新到 Consul
        参考 ClusterInfo.refresh_consul_storage_config 方法实现

        功能说明：
        1. 从数据库获取所有启用的特性开关配置（FeatureFlag.objects.filter(is_enabled=True)）
        2. 将所有特性开关配置合并为一个 JSON 对象
        3. 写入到 Consul，路径格式为: {CONSUL_PATH}/unify-query/data/feature_flag

        :return: None
        """
        from metadata.models.feature_flag import FeatureFlag

        hash_consul = consul_tools.HashConsul()

        # 1. 从数据库获取所有启用的特性开关配置
        feature_flag_list = FeatureFlag.objects.filter(is_enabled=True)

        total_count = feature_flag_list.count()
        logger.debug(f"total find->[{total_count}] feature flags to refresh to consul")

        # 2. 构建需要刷新的字典信息，格式为 {flag_name: flag_config}
        feature_flags_dict = {}
        for feature_flag in feature_flag_list:
            config_dict = feature_flag.to_config_dict()
            if config_dict:
                feature_flags_dict[feature_flag.flag_name] = config_dict

        # 3. 如果没有任何配置，清理 Consul 中的旧数据并返回
        if not feature_flags_dict:
            logger.warning("no enabled feature flags found in database, clean consul and skip refresh")
            # 清理 Consul 中的旧数据
            try:
                consul_path = cls.CONSUL_PREFIX_PATH
                hash_consul.delete(consul_path)
                hash_consul.delete(cls.CONSUL_VERSION_PATH)
                logger.debug(f"cleaned consul path->[{consul_path}] and version path")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"failed to clean consul, error->[{e}]")
            return

        # 4. 构建 Consul 路径，格式: {CONSUL_PATH}/unify-query/data/feature_flag
        consul_path = cls.CONSUL_PREFIX_PATH

        # 5. 写入 Consul（所有 flags 存储在一个 key 中）
        hash_consul.put(key=consul_path, value=feature_flags_dict)
        logger.debug(f"consul path->[{consul_path}] is refresh with {len(feature_flags_dict)} feature flags success.")

        # 6. 更新版本时间戳（参考 storage.py 实现）
        hash_consul.put(key=cls.CONSUL_VERSION_PATH, value={"time": time.time()})
        logger.debug(f"consul version path->[{cls.CONSUL_VERSION_PATH}] is refresh with timestamp success.")

        logger.info(f"all feature flag config is refresh to consul success count->[{len(feature_flags_dict)}].")

    @classmethod
    def refresh_redis_feature_flag_config_from_db(cls):
        """
        从数据库读取特性开关配置并刷新到 Redis
        参考 ClusterInfo.refresh_redis_storage_config 方法实现

        功能说明：
        1. 从数据库获取所有启用的特性开关配置（FeatureFlag.objects.filter(is_enabled=True)）
        2. 将所有特性开关配置合并为一个 JSON 对象
        3. 写入到 Redis，key 格式为: {REDIS_PREFIX_KEY}

        :return: None
        """
        from metadata.models.feature_flag import FeatureFlag

        # 1. 从数据库获取所有启用的特性开关配置
        feature_flag_list = FeatureFlag.objects.filter(is_enabled=True)

        total_count = feature_flag_list.count()
        logger.debug(f"total find->[{total_count}] feature flags to refresh to redis")

        # 2. 构建需要刷新的字典信息，格式为 {flag_name: flag_config}
        feature_flags_dict = {}
        for feature_flag in feature_flag_list:
            config_dict = feature_flag.to_config_dict()
            if config_dict:
                feature_flags_dict[feature_flag.flag_name] = config_dict

        # 3. 如果没有任何配置，清理 Redis 中的旧数据并返回
        if not feature_flags_dict:
            logger.warning("no enabled feature flags found in database, clean redis and skip refresh")
            try:
                cls._write_redis_feature_flags({})
                logger.debug(f"cleaned redis key->[{cls.REDIS_PREFIX_KEY}]")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"failed to clean redis, error->[{e}]")
            return

        # 4. 构建 Redis key，格式: {REDIS_PREFIX_KEY}
        redis_key = cls.REDIS_PREFIX_KEY

        # 5. 将配置信息序列化为 JSON 字符串并写入 Redis（所有 flags 存储在一个 key 中）
        cls._write_redis_feature_flags(feature_flags_dict)
        logger.debug(f"redis key->[{redis_key}] is refresh with {len(feature_flags_dict)} feature flags success.")

        logger.info(f"all feature flag config is refresh to redis success count->[{len(feature_flags_dict)}].")

    @classmethod
    def refresh_consul_feature_flag_config(cls, feature_flags: dict):
        """
        刷新特性开关配置到 Consul，参考 refresh_consul_storage_config 方法实现

        功能说明：
        1. 将所有特性开关配置合并为一个 JSON 对象
        2. 写入到 Consul，路径格式为: {CONSUL_PATH}/unify-query/data/feature_flag
        3. 支持复杂的特性开关格式，包含 variations、targeting、defaultRule

        Consul 存储格式：
        - Key: {CONSUL_PATH}/unify-query/data/feature_flag
        - Value: JSON 字典，包含所有特性开关配置，格式如下：
          {
            "must-vm-query": {
              "variations": {
                "Default": false,
                "true": true,
                "false": false
              },
              "targeting": [{
                "query": "tableID in [\"table_id_1\", \"table_id_2\"]",
                "percentage": {
                  "true": 100,
                  "false": 0
                }
              }],
              "defaultRule": {
                "variation": "Default"
              }
            },
            "range-vm-query": {
              ...
            }
          }

        :param feature_flags: 特性开关配置字典，格式为 {flag_name: flag_config}
                            flag_config 包含 variations、targeting、defaultRule 等字段
        :return: None
        """
        # 从 settings 读取 Consul 配置，如果没有则使用默认值
        consul_host = getattr(settings, "CONSUL_CLIENT_HOST", "127.0.0.1")
        consul_port = getattr(settings, "CONSUL_CLIENT_PORT", 8500)
        hash_consul = consul_tools.HashConsul(host=consul_host, port=consul_port)

        # 1. 将所有特性开关配置合并为一个 JSON 对象
        # 直接使用传入的 feature_flags 字典，它已经包含了所有 flag 的配置
        config_value = feature_flags

        # 2. 构建 Consul 路径，格式: {CONSUL_PATH}/unify-query/data/feature_flag
        consul_path = cls.CONSUL_PREFIX_PATH

        # 3. 写入 Consul（所有 flags 存储在一个 key 中）
        hash_consul.put(key=consul_path, value=config_value)
        logger.debug(f"consul path->[{consul_path}] is refresh with {len(feature_flags)} feature flags success.")

        # 4. 更新版本时间戳（参考 storage.py 实现）
        hash_consul.put(key=cls.CONSUL_VERSION_PATH, value={"time": time.time()})
        logger.debug(f"consul version path->[{cls.CONSUL_VERSION_PATH}] is refresh with timestamp success.")

        logger.info(f"all feature flag config is refresh to consul success count->[{len(feature_flags)}].")

    @classmethod
    def refresh_redis_feature_flag_config(cls, feature_flags: dict):
        """
        刷新特性开关配置到 Redis，参考 refresh_redis_storage_config 方法实现

        功能说明：
        1. 将所有特性开关配置合并为一个 JSON 对象
        2. 写入到 Redis，key 格式为: {REDIS_PREFIX_KEY}
        3. 支持复杂的特性开关格式，包含 variations、targeting、defaultRule

        Redis 存储格式：
        - Key: {REDIS_PREFIX_KEY}
        - Value: JSON 字符串，包含所有特性开关配置，格式如下：
          {
            "must-vm-query": {
              "variations": {
                "Default": false,
                "true": true,
                "false": false
              },
              "targeting": [{
                "query": "tableID in [\"table_id_1\", \"table_id_2\"]",
                "percentage": {
                  "true": 100,
                  "false": 0
                }
              }],
              "defaultRule": {
                "variation": "Default"
              }
            },
            "range-vm-query": {
              ...
            }
          }

        :param feature_flags: 特性开关配置字典，格式为 {flag_name: flag_config}
                            flag_config 包含 variations、targeting、defaultRule 等字段
        :return: None
        """
        cls._write_redis_feature_flags(feature_flags)
        logger.debug(f"redis key->[{cls.REDIS_PREFIX_KEY}] is refresh with {len(feature_flags)} feature flags success.")

        logger.info(f"all feature flag config is refresh to redis success count->[{len(feature_flags)}].")

    @classmethod
    def get_all_consul_feature_flag_config(cls, raise_on_error: bool = False) -> dict | None:
        """
        从 Consul 读取所有特性开关配置

        功能说明：
        1. 从 Consul 读取所有特性开关配置（单个 key）
        2. 返回包含所有 flags 的配置字典

        Consul 路径格式：
        - Key: {CONSUL_PATH}/unify-query/data/feature_flag

        返回值格式：
        {
            "must-vm-query": {
                "variations": {...},
                "targeting": [...],
                "defaultRule": {...}
            },
            "range-vm-query": {
                ...
            }
        }

        :return: 包含所有 flags 的配置字典，如果不存在或读取失败则返回 None
        """
        # 从 settings 读取 Consul 配置，如果没有则使用默认值
        consul_host = getattr(settings, "CONSUL_CLIENT_HOST", "127.0.0.1")
        consul_port = getattr(settings, "CONSUL_CLIENT_PORT", 8500)
        hash_consul = consul_tools.HashConsul(host=consul_host, port=consul_port)

        # 构建 Consul 路径（所有 flags 存储在一个 key 中）
        consul_path = cls.CONSUL_PREFIX_PATH

        try:
            # 从 Consul 读取配置数据
            index, consul_data = hash_consul.get(consul_path)

            if consul_data and consul_data.get("Value"):
                # 获取 Value 字段（可能是 bytes 或字符串）
                value_str = consul_data["Value"]

                # 如果 Value 是 bytes，需要先解码为字符串
                if isinstance(value_str, bytes):
                    value_str = value_str.decode("utf-8")

                # 如果 Value 是字符串，需要解析 JSON
                if isinstance(value_str, str):
                    return json.loads(value_str)
                # 如果已经是字典，直接返回
                elif isinstance(value_str, dict):
                    return value_str

            # 如果 Consul 中没有该 key，返回 None
            return None

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"get all consul feature flag config error, error->[{e}]")
            if raise_on_error:
                raise
            return None

    @classmethod
    def get_consul_feature_flag_config(cls, flag_name: str, raise_on_error: bool = False) -> dict | None:
        """
        从 Consul 读取特性开关配置，参考 Consul 的 get 方法实现

        功能说明：
        1. 从 Consul 读取所有特性开关配置（单个 key）
        2. 从配置中提取指定 flag_name 的配置
        3. 解析并返回配置字典
        4. 如果配置不存在或读取失败，返回 None

        Consul 路径格式：
        - Key: {CONSUL_PATH}/unify-query/data/feature_flag

        返回值格式：
        {
            "variations": {
              "Default": <default_value>,
              "true": <true_value>,
              "false": <false_value>
            },
            "targeting": [{
              "query": "tableID in [\"table_id_1\", \"table_id_2\"]",
              "percentage": {
                "true": 100,
                "false": 0
              }
            }],
            "defaultRule": {
              "variation": "Default"
            }
          }

        使用场景：
        - 查询模块需要获取特性开关配置时，从 Consul 读取
        - 如果 Consul 中没有配置，可以回退到从数据库或 Redis 读取

        :param flag_name: 特性开关名称
        :return: 配置字典，如果不存在或读取失败则返回 None
        """
        # 从 settings 读取 Consul 配置，如果没有则使用默认值
        consul_host = getattr(settings, "CONSUL_CLIENT_HOST", "127.0.0.1")
        consul_port = getattr(settings, "CONSUL_CLIENT_PORT", 8500)
        hash_consul = consul_tools.HashConsul(host=consul_host, port=consul_port)

        # 构建 Consul 路径（所有 flags 存储在一个 key 中）
        consul_path = cls.CONSUL_PREFIX_PATH

        try:
            # 从 Consul 读取配置数据
            # Consul 返回格式: (index, value_dict)，其中 value_dict["Value"] 是 JSON 字符串
            index, consul_data = hash_consul.get(consul_path)

            if consul_data and consul_data.get("Value"):
                # 获取 Value 字段（可能是 bytes 或字符串）
                value_str = consul_data["Value"]

                # 如果 Value 是 bytes，需要先解码为字符串
                if isinstance(value_str, bytes):
                    value_str = value_str.decode("utf-8")

                # 如果 Value 是字符串，需要解析 JSON
                if isinstance(value_str, str):
                    all_flags = json.loads(value_str)
                # 如果已经是字典，直接使用
                elif isinstance(value_str, dict):
                    all_flags = value_str
                else:
                    return None

                # 从所有 flags 中提取指定 flag_name 的配置
                if isinstance(all_flags, dict) and flag_name in all_flags:
                    return all_flags[flag_name]

            # 如果 Consul 中没有该 key 或 flag_name 不存在，返回 None
            return None

        except Exception as e:  # pylint: disable=broad-except
            # 捕获所有异常，避免因为 Consul 连接问题或数据格式问题导致程序崩溃
            logger.error(f"get consul feature flag config error, flag_name->[{flag_name}], error->[{e}]")
            if raise_on_error:
                raise
            return None

    @classmethod
    def get_all_redis_feature_flag_config(cls, raise_on_error: bool = False) -> dict | None:
        """
        从 Redis 读取所有特性开关配置

        功能说明：
        1. 从 Redis 读取所有特性开关配置（单个 key）
        2. 返回包含所有 flags 的配置字典

        Redis key 格式：
        - Key: {REDIS_PREFIX_KEY}

        返回值格式：
        {
            "must-vm-query": {
                "variations": {...},
                "targeting": [...],
                "defaultRule": {...}
            },
            "range-vm-query": {
                ...
            }
        }

        :return: 包含所有 flags 的配置字典，如果不存在或读取失败则返回 None
        """
        # 构建 Redis key（所有 flags 存储在一个 key 中）
        redis_key = cls.REDIS_PREFIX_KEY

        try:
            # 从 Redis 读取配置数据
            data = RedisTools().client.get(redis_key)

            if data:
                # 如果数据是 bytes 类型，需要先解码为字符串
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # 将 JSON 字符串解析为 Python 字典（包含所有 flags）
                return json.loads(data)

            # 如果 Redis 中没有该 key，返回 None
            return None

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"get all redis feature flag config error, error->[{e}]")
            if raise_on_error:
                raise
            return None

    @classmethod
    def get_redis_feature_flag_config(cls, flag_name: str, raise_on_error: bool = False) -> dict | None:
        """
        从 Redis 读取特性开关配置，参考 get_redis_storage_config 方法实现

        功能说明：
        1. 从 Redis 读取所有特性开关配置（单个 key）
        2. 从配置中提取指定 flag_name 的配置
        3. 解析 JSON 字符串并返回配置字典
        4. 如果配置不存在或读取失败，返回 None

        Redis key 格式：
        - Key: {REDIS_PREFIX_KEY}
        - Value: JSON 字符串，包含所有特性开关配置

        返回值格式：
        {
            "variations": {
              "Default": <default_value>,
              "true": <true_value>,
              "false": <false_value>
            },
            "targeting": [{
              "query": "tableID in [\"table_id_1\", \"table_id_2\"]",
              "percentage": {
                "true": 100,
                "false": 0
              }
            }],
            "defaultRule": {
              "variation": "Default"
            }
        }

        使用场景：
        - 查询模块需要获取特性开关配置时，优先从 Redis 读取（性能更好）
        - 如果 Redis 中没有配置，可以回退到从数据库或 Consul 读取

        :param flag_name: 特性开关名称
        :return: 配置字典，如果不存在或读取失败则返回 None
        """
        # 构建 Redis key（所有 flags 存储在一个 key 中）
        redis_key = cls.REDIS_PREFIX_KEY

        try:
            # 从 Redis 读取配置数据
            # Redis 返回的数据可能是 bytes 类型，需要转换为字符串
            data = RedisTools().client.get(redis_key)

            if data:
                # 如果数据是 bytes 类型，需要先解码为字符串
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # 将 JSON 字符串解析为 Python 字典（包含所有 flags）
                all_flags = json.loads(data)

                # 从所有 flags 中提取指定 flag_name 的配置
                if isinstance(all_flags, dict) and flag_name in all_flags:
                    return all_flags[flag_name]

            # 如果 Redis 中没有该 key 或 flag_name 不存在，返回 None
            return None

        except Exception as e:  # pylint: disable=broad-except
            # 捕获所有异常，避免因为 Redis 连接问题或数据格式问题导致程序崩溃
            logger.error(f"get redis feature flag config error, flag_name->[{flag_name}], error->[{e}]")
            if raise_on_error:
                raise
            return None

    @classmethod
    def get_feature_flag_config(cls, flag_name: str, prefer_redis: bool = False) -> dict | None:
        """
        获取特性开关配置，优先从 Consul 读取，如果不存在则从 Redis 读取

        功能说明：
        1. 根据 prefer_redis 参数决定优先读取顺序
        2. 如果 prefer_redis=False（默认），先尝试从 Consul 读取，失败则从 Redis 读取
        3. 如果 prefer_redis=True，先尝试从 Redis 读取，失败则从 Consul 读取
        4. 如果两者都失败，返回 None

        Consul 优先策略优势：
        - Consul 作为配置中心，配置更新更及时
        - 支持分布式配置管理和版本控制
        - 与存储集群配置保持一致的读取策略

        :param flag_name: 特性开关名称
        :param prefer_redis: 是否优先从 Redis 读取，默认 False（优先从 Consul 读取）
        :return: 配置字典，如果不存在或读取失败则返回 None
        """
        primary = cls.get_redis_feature_flag_config if prefer_redis else cls.get_consul_feature_flag_config
        fallback = cls.get_consul_feature_flag_config if prefer_redis else cls.get_redis_feature_flag_config
        try:
            # 主后端成功返回 None 代表权威地“不存在”，不能用另一后端的旧值复活配置。
            return primary(flag_name, raise_on_error=True)
        except Exception:  # pylint: disable=broad-except
            return fallback(flag_name)

    @classmethod
    def get_feature_flag_config_prefer_consul(cls, flag_name: str) -> dict | None:
        """
        获取特性开关配置，明确优先从 Consul 读取

        功能说明：
        1. 优先从 Consul 读取配置（作为配置中心，更新更及时）
        2. 如果 Consul 读取失败或不存在，回退到 Redis 读取
        3. 如果两者都失败，返回 None

        使用场景：
        - 需要确保配置实时性的场景
        - 配置更新后需要立即生效的场景
        - 与存储集群配置保持一致的读取策略

        :param flag_name: 特性开关名称
        :return: 配置字典，如果不存在或读取失败则返回 None
        """
        return cls.get_feature_flag_config(flag_name, prefer_redis=False)

    @classmethod
    def get_feature_flag_config_prefer_redis(cls, flag_name: str) -> dict | None:
        """
        获取特性开关配置，明确优先从 Redis 读取

        功能说明：
        1. 优先从 Redis 读取配置（性能更好，延迟更低）
        2. 如果 Redis 读取失败或不存在，回退到 Consul 读取
        3. 如果两者都失败，返回 None

        使用场景：
        - 对性能要求较高的场景
        - 配置更新不频繁的场景
        - 可以容忍配置延迟生效的场景

        :param flag_name: 特性开关名称
        :return: 配置字典，如果不存在或读取失败则返回 None
        """
        return cls.get_feature_flag_config(flag_name, prefer_redis=True)

    @classmethod
    def get_all_feature_flag_config(cls, prefer_redis: bool = False) -> dict | None:
        """
        获取所有特性开关配置，优先从 Consul 读取，如果不存在则从 Redis 读取

        功能说明：
        1. 根据 prefer_redis 参数决定优先读取顺序
        2. 如果 prefer_redis=False（默认），先尝试从 Consul 读取，失败则从 Redis 读取
        3. 如果 prefer_redis=True，先尝试从 Redis 读取，失败则从 Consul 读取
        4. 如果两者都失败，返回 None

        :param prefer_redis: 是否优先从 Redis 读取，默认 False（优先从 Consul 读取）
        :return: 包含所有特性开关配置的字典，如果不存在或读取失败则返回 None
        """
        primary = cls.get_all_redis_feature_flag_config if prefer_redis else cls.get_all_consul_feature_flag_config
        fallback = cls.get_all_consul_feature_flag_config if prefer_redis else cls.get_all_redis_feature_flag_config
        try:
            return primary(raise_on_error=True)
        except Exception:  # pylint: disable=broad-except
            return fallback()

    @classmethod
    def get_all_feature_flag_config_prefer_consul(cls) -> dict | None:
        """
        获取所有特性开关配置，明确优先从 Consul 读取

        功能说明：
        1. 优先从 Consul 读取所有配置（作为配置中心，更新更及时）
        2. 如果 Consul 读取失败或不存在，回退到 Redis 读取
        3. 如果两者都失败，返回 None

        :return: 包含所有特性开关配置的字典，如果不存在或读取失败则返回 None
        """
        return cls.get_all_feature_flag_config(prefer_redis=False)

    @classmethod
    def get_all_feature_flag_config_prefer_redis(cls) -> dict | None:
        """
        获取所有特性开关配置，明确优先从 Redis 读取

        功能说明：
        1. 优先从 Redis 读取所有配置（性能更好，延迟更低）
        2. 如果 Redis 读取失败或不存在，回退到 Consul 读取
        3. 如果两者都失败，返回 None

        :return: 包含所有特性开关配置的字典，如果不存在或读取失败则返回 None
        """
        return cls.get_all_feature_flag_config(prefer_redis=True)

    @staticmethod
    def _select_percentage_variation(
        flag_name: str,
        evaluation_key: str,
        percentage: dict,
        variations: dict,
    ) -> tuple[bool, Any]:
        """按稳定哈希桶选择百分比分配，保证同一评估 Key 的结果稳定。"""
        digest = hashlib.sha256(f"{flag_name}:{evaluation_key}".encode()).digest()
        bucket = int.from_bytes(digest[:8], byteorder="big") % 10000 / 100
        upper_bound = 0.0

        for variation_name, raw_weight in percentage.items():
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            upper_bound += weight
            if bucket < upper_bound:
                return True, variations.get(variation_name)

        return False, None

    @classmethod
    def get_feature_flag_value(
        cls, flag_name: str, table_id: str | None = None, prefer_redis: bool = True
    ) -> Any | None:
        """
        获取特性开关的值，根据 tableID 匹配 targeting 规则

        功能说明：
        1. 获取特性开关配置
        2. 根据 table_id 匹配 targeting 规则中的 query
        3. 如果匹配到规则，根据 percentage 返回对应的 variation 值
        4. 如果没有匹配到规则，返回 defaultRule 指定的 variation 值

        判断逻辑：
        1. 遍历 targeting 规则，检查 table_id 是否匹配 query 条件
        2. 如果匹配，根据 percentage 分配返回对应的 variation 值
        3. 如果不匹配任何规则，返回 defaultRule.variation 对应的值

        :param flag_name: 特性开关名称
        :param table_id: 结果表 ID（可选），用于匹配 targeting 规则
        :param prefer_redis: 是否优先从 Redis 读取，默认 True
        :return: 特性开关的值，如果配置不存在则返回 None
        """
        config = cls.get_feature_flag_config(flag_name, prefer_redis=prefer_redis)

        # 如果配置不存在，返回 None
        if not config:
            return None

        variations = config.get("variations", {})
        targeting = config.get("targeting", [])
        default_rule = config.get("defaultRule", {})

        # 如果有 table_id，尝试匹配 targeting 规则
        if table_id and targeting:
            for rule in targeting:
                query = rule.get("query", "")
                percentage = rule.get("percentage", {})

                # 简单的 query 解析：支持 "tableID in [\"table_id_1\", \"table_id_2\"]" 格式
                if "tableID in" in query and table_id:
                    # 匹配 tableID in ["table_id_1", "table_id_2"] 格式
                    match = re.search(r"tableID in \[(.*?)\]", query)
                    if match:
                        table_list_str = match.group(1)
                        # 提取引号中的值
                        table_list = [t.strip().strip('"').strip("'") for t in table_list_str.split(",")]

                        # 如果 table_id 在列表中，根据 percentage 返回对应的值
                        if table_id in table_list:
                            selected, variation = cls._select_percentage_variation(
                                flag_name,
                                table_id,
                                percentage,
                                variations,
                            )
                            if selected:
                                return variation

        # 如果没有匹配到规则，返回默认值
        default_variation = default_rule.get("variation", "Default")
        return variations.get(default_variation)

    @classmethod
    def get_consul_feature_flag_version(cls) -> dict | None:
        """
        获取 Consul 中特性开关配置的版本信息

        功能说明：
        1. 从 Consul 读取版本时间戳信息
        2. 返回包含时间戳的字典

        返回值格式：
        {
            "time": 1640995200.123456  # Unix 时间戳
        }

        :return: 版本信息字典，如果不存在则返回 None
        """
        # 从 settings 读取 Consul 配置，如果没有则使用默认值
        consul_host = getattr(settings, "CONSUL_CLIENT_HOST", "127.0.0.1")
        consul_port = getattr(settings, "CONSUL_CLIENT_PORT", 8500)
        hash_consul = consul_tools.HashConsul(host=consul_host, port=consul_port)

        try:
            # 从 Consul 读取版本信息
            index, consul_data = hash_consul.get(cls.CONSUL_VERSION_PATH)

            if consul_data and consul_data.get("Value"):
                # 获取 Value 字段（可能是 bytes 或字符串）
                value_str = consul_data["Value"]

                # 如果 Value 是 bytes，需要先解码为字符串
                if isinstance(value_str, bytes):
                    value_str = value_str.decode("utf-8")

                # 如果 Value 是字符串，需要解析 JSON
                if isinstance(value_str, str):
                    return json.loads(value_str)
                # 如果已经是字典，直接返回
                elif isinstance(value_str, dict):
                    return value_str

            # 如果 Consul 中没有该 key，返回 None
            return None

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"get consul feature flag version error, error->[{e}]")
            return None

    @classmethod
    def is_feature_flag_config_updated(cls, last_check_time: float) -> bool:
        """
        检查特性开关配置是否已更新

        功能说明：
        1. 获取当前 Consul 中的版本时间戳
        2. 与上次检查的时间戳进行比较
        3. 如果当前时间戳大于上次检查时间戳，说明配置已更新

        使用场景：
        - 查询模块可以定期调用此方法检查配置是否需要重新加载
        - 避免频繁从 Consul 读取完整配置，提高性能

        :param last_check_time: 上次检查的时间戳（Unix 时间戳）
        :return: True 表示配置已更新，False 表示未更新或检查失败
        """
        try:
            # 获取当前版本信息
            version_info = cls.get_consul_feature_flag_version()

            if not version_info:
                # 如果获取不到版本信息，保守起见认为配置已更新
                return True

            current_time = version_info.get("time", 0)

            # 如果当前时间戳大于上次检查时间戳，说明配置已更新
            return current_time > last_check_time

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"check feature flag config update error, error->[{e}]")
            # 发生异常时，保守起见认为配置已更新
            return True

    @classmethod
    def force_refresh_feature_flag_config(cls):
        """
        强制刷新特性开关配置到 Consul 和 Redis

        功能说明：
        1. 从数据库读取所有启用的特性开关配置
        2. 同时刷新到 Consul 和 Redis
        3. 更新版本时间戳

        使用场景：
        - 管理员手动触发配置刷新
        - 配置变更后需要立即生效时调用

        :return: None
        """
        FeatureFlag._refresh_external_config(
            flag_name="*",
            action="periodic forced refresh",
            raise_on_failure=True,
        )
