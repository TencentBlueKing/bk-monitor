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
import logging
import os

import redis
from django.conf import settings

from utils.redis_client import RedisClient

logger = logging.getLogger("metadata")


class RedisTools:
    metadata_redis_client = None

    @property
    def client(self) -> RedisClient:
        client = self.metadata_redis_client
        # 创建client失败时，重试一下
        if client is None:
            client = setup_client()
        return client

    @classmethod
    def push_and_publish_spaces(cls, key: str, channel: str, space: list):
        """推送 redis 并且发布空间变更"""
        cls.push_space_to_redis(key, space)
        cls.publish(channel, space)

    @classmethod
    def push_space_to_redis(cls, key: str, space: list) -> int | None:
        """推送空间到 redis"""
        if not space:
            return
        return cls().client.sadd(key, *space)

    @classmethod
    def publish(cls, channel: str, msg_list: list[str]):
        """当数据变动时，发布数据"""
        logger.info("publish: channel->[%s],publish msg_list->[%s]", channel, msg_list)
        try:
            for msg in msg_list:
                cls().client.publish(channel, msg)
        except Exception as e:  # pylint: disable=broad-except
            logging.error("publish: publish msg into channel->[%s] for ->[%s], error->[%s]", channel, msg_list, e)
            raise Exception(f"publish msg error, {e}")
        return

    @classmethod
    def hset_to_redis(cls, key: str, field: str, value: str):
        """哈希方式推送表数据"""
        return cls().client.hset(key, field, value)

    @classmethod
    def hmset_to_redis(cls, key: str, field_value: dict[str, str]) -> bool:
        """推送表数据到 redis"""
        logger.info("hmset_to_redis: key->[%s], field_value->[%s]", key, field_value)
        return cls().client.hmset(key, field_value)

    @classmethod
    def sadd(cls, key: str, value: list) -> int | None:
        if not value:
            return
        return cls().client.sadd(key, *value)

    @classmethod
    def is_member_exist(cls, key: str) -> bool:
        """判断数据是否存在"""
        if cls().client.smembers(key):
            return True
        return False

    @classmethod
    def hdel(cls, key: str, fields: list):
        """删除指定的 field"""
        if not fields:
            return
        return cls().client.hdel(key, *fields)

    @classmethod
    def hget(cls, key: str, field: str) -> bytes | None:
        return cls().client.hget(key, field)

    @classmethod
    def hmget(cls, key: str, fields: list) -> list:
        if not fields:
            return []
        return cls().client.hmget(key, *fields)

    @classmethod
    def hgetall(cls, key: str) -> dict:
        """批量获取数据"""
        return cls().client.hgetall(key)

    @classmethod
    def srem(cls, key: str, value: list) -> int:
        if not value:
            return 0
        return cls().client.srem(key, *value)

    @classmethod
    def smembers(cls, key: str) -> set:
        return cls().client.smembers(key)

    @classmethod
    def get_list(cls, key: str) -> list:
        data = cls().client.get(key)
        if not data:
            return []
        return json.loads(data.decode("utf-8"))

    @classmethod
    def set(cls, key: str, value: str) -> bool:
        return cls().client.set(key, value)

    @classmethod
    def delete(cls, key: str) -> int:
        return cls().client.delete(key)


def setup_client():
    RedisTools.metadata_redis_client = RedisClient.from_envs(
        prefix=os.environ.get("METADATA_REDIS_CONFIG_PREFIX", "BK_MONITOR_TRANSFER")
    )


def bkbase_redis_client():
    """
    获取bkbase_redis链接
    """

    # 初始化Redis链接信息
    bkbase_redis_host = settings.BKBASE_REDIS_HOST
    bkbase_redis_port = settings.BKBASE_REDIS_PORT
    bkbase_redis_pwd = settings.BKBASE_REDIS_PASSWORD

    # 检查bkbase redis配置是否存在
    if not bkbase_redis_host or not bkbase_redis_port:
        return None

    configs = {
        "host": bkbase_redis_host,
        "port": bkbase_redis_port,
        "password": bkbase_redis_pwd,
    }
    bkbase_redis = redis.StrictRedis(**configs)
    return bkbase_redis


# 兼容redis 初始化异常问题，避免引用时报错
try:
    setup_client()
except Exception:
    pass
