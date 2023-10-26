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
import json

import pytest
from mockredis import mock_redis_client


@pytest.fixture
def patch_redis_tools(mocker):
    client = mock_redis_client()

    def mock_hset_redis(*args, **kwargs):
        client.hset(*args, **kwargs)

    def mock_hget_redis(*args, **kwargs):
        return client.hget(*args, **kwargs)

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    def mock_hgetall_redis(*args, **kwargs):
        return client.hgetall(*args, **kwargs)

    def mock_publish(*args, **kwargs):
        return client.publish(*args, **kwargs)

    # NOTE: 这里需要把参数指定出来，防止 *["test"] 解析为 ["test"]
    def mock_hdel_redis(key, fields):
        return client.hdel(key, *fields)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", side_effect=mock_hset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hgetall", side_effect=mock_hgetall_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hget", side_effect=mock_hget_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hdel", side_effect=mock_hdel_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.publish", side_effect=mock_publish)


@pytest.fixture
def patch_consul_tool(mocker):
    kv_store = {}

    class MockConsul(object):
        def put(self, key, value):
            kv_store[key] = json.dumps(value)

        def get(self, key):
            return kv_store[key]

        def delete(self, key):
            kv_store.pop(key)

        def list(self, *args, **kwargs):
            d = [123]
            item = []
            for k in list(kv_store.keys()):
                item.append({"Key": k, "Value": bytes('{}', encoding="utf-8")})
            d.append(item)
            return d

    mocker.patch("metadata.utils.consul_tools.HashConsul", side_effect=MockConsul)
