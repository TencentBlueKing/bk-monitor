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
import random

from mockredis import MockRedis


def any_return_model(model):
    def real_model_side_effect(**kwargs):
        return model(**kwargs)

    return real_model_side_effect


RANDOM_CHARACTER_SET = "abcdefghijklmnopqrstuvwxyz0123456789"


def generate_random_string(length=10, chars=RANDOM_CHARACTER_SET):
    """生成随机字符串"""
    rand = random.SystemRandom()
    return "".join(rand.choice(chars) for x in range(length))


def consul_client(*args, **kwargs):
    return CustomConsul()


class CustomConsul:
    def __init__(self):
        self.kv = KVDelete()

    def delete(self, *args, **kwargs):
        return True


class KVDelete:
    def delete(self, *args, **kwargs):
        return True


class MockCache:
    mocker_redis = MockRedis()

    def __init__(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        return self.mocker_redis.set(*args, **kwargs)

    def get(self, *args, **kwargs):
        b_value = self.mocker_redis.get(*args, **kwargs)
        if b_value:
            return b_value.decode()

    def delete(self, *args, **kwargs):
        return self.mocker_redis.delete(*args, **kwargs)
