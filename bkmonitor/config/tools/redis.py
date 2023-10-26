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


import os

__all__ = ["get_redis_settings"]

from config.tools.environment import ENVIRONMENT, PAAS_VERSION, ROLE


def get_redis_settings():
    """
    获取Redis配置
    """
    is_dev = ENVIRONMENT == "development"
    host = os.environ.get("REDIS_HOST")
    port = os.getenv("REDIS_PORT")
    password = os.environ.get("REDIS_PASSWORD", "")

    if ROLE in ["worker", "api"]:
        if PAAS_VERSION == "V3" or is_dev:
            mode = "standalone"
        else:
            mode = "sentinel"

        mode = os.environ.get("BK_MONITOR_REDIS_MODE", mode)

        # RedisCache: 单实例 / SentinelRedisCache: 哨兵模式
        cache_backend_type = {"sentinel": "SentinelRedisCache", "standalone": "RedisCache"}.get(
            mode, "SentinelRedisCache"
        )

        if cache_backend_type == "SentinelRedisCache":
            # redis 集群sentinel模式
            host = os.environ.get("BK_MONITOR_REDIS_SENTINEL_HOST", host)
            port = os.environ.get("BK_MONITOR_REDIS_SENTINEL_PORT", port)

            if is_dev:
                host = host or ("127.0.0.1" if ENVIRONMENT == "development" else "redis_sentinel.service.consul")
                port = int(port or 16379)
        else:
            # redis 集群sentinel模式
            host = os.environ.get("BK_MONITOR_REDIS_HOST", host)
            port = os.environ.get("BK_MONITOR_REDIS_PORT", port)

            if is_dev:
                host = host or ("127.0.0.1" if ENVIRONMENT == "development" else "redis.service.consul")
                port = int(port or 6379)

        password = os.environ.get("BK_MONITOR_REDIS_PASSWORD", password)
    else:
        cache_backend_type = "RedisCache"

    master_name = os.environ.get("BK_MONITOR_REDIS_SENTINEL_MASTER_NAME", "mymaster")
    sentinel_password = os.environ.get("BK_MONITOR_REDIS_SENTINEL_PASSWORD", "")
    return cache_backend_type, host, port, password, master_name, sentinel_password


def get_cache_redis_settings(redis_type: str):
    """
    获取Cache Redis配置
    """
    if redis_type == "RedisCache":
        host = os.environ.get("BK_MONITOR_CACHE_REDIS_HOST", "")
        port = os.environ.get("BK_MONITOR_CACHE_REDIS_PORT", "")
    elif redis_type == "SentinelRedisCache":
        host = os.environ.get("BK_MONITOR_CACHE_REDIS_SENTINEL_HOST", "")
        port = os.environ.get("BK_MONITOR_CACHE_REDIS_SENTINEL_PORT", "")
    else:
        raise Exception("redis_type error")

    password = os.environ.get("BK_MONITOR_REDIS_PASSWORD", None)
    master_name = os.environ.get("BK_MONITOR_REDIS_SENTINEL_MASTER_NAME", "")
    sentinel_password = os.environ.get("BK_MONITOR_REDIS_SENTINEL_PASSWORD", None)
    return host, port, password, master_name, sentinel_password
