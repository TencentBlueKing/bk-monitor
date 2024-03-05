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
import logging
import time
from typing import Optional

from bkmonitor.utils import consul
from metadata import config
from metadata.utils import hash_util

CONSUL_INFLUXDB_VERSION_PATH = "%s/influxdb_info/version/" % config.CONSUL_PATH

logger = logging.getLogger("metadata")


def refresh_router_version():
    """
    更新consul指定路径下的版本
    :return: True | raise Exception
    """

    client = consul.BKConsul()
    client.kv.put(key=CONSUL_INFLUXDB_VERSION_PATH, value=str(time.time()))
    logger.info("refresh influxdb version in consul success.")


class HashConsul(object):
    """
    哈希consul工具
    工具在写入consul前，将会先匹配consul上的数据是否与当次写入数据一致
    如果一致，该更新将会被忽略（如果允许），否则才会将配置写入consul
    从而降低consul的刷新频率
    """

    def __init__(self, host="127.0.0.1", port=8500, scheme="http", verify=None, default_force=False):
        """
        初始化
        :param host: consul agent IP地址
        :param port: consul agent 端口
        :param scheme: consul agent协议
        :param verify: SSL 验证
        :param default_force: 默认是否需要强制更新
        """
        # consul agent connect info
        self.host = host
        self.port = port
        self.scheme = scheme
        self.verify = verify

        # 是否强行写
        self.default_force = default_force

    def delete(self, key, recurse=None):
        """
        删除指定kv
        """
        consul_client = consul.BKConsul(host=self.host, port=self.port, scheme=self.scheme, verify=self.verify)
        consul_client.kv.delete(key, recurse)
        logger.info("key->[%s] has been deleted", key)

    def get(self, key):
        """
        获取指定kv
        """
        consul_client = consul.BKConsul(host=self.host, port=self.port, scheme=self.scheme, verify=self.verify)
        return consul_client.kv.get(key)

    def list(self, key):
        consul_client = consul.BKConsul(host=self.host, port=self.port, scheme=self.scheme, verify=self.verify)
        return consul_client.kv.get(key, recurse=True)

    def put(self, key, value, is_force_update=False, bk_data_id: Optional[int] = None, *args, **kwargs):
        """
        KV数据更新, 如果更新成功或者内容无更新，则返回True
        如果更新失败，则返回False
        :param key: 键值
        :param value: 内容，期待传入的是字典或者数组
        :param is_force_update: 是否需要强行更新
        :return: True | False
        """
        consul_client = consul.BKConsul(host=self.host, port=self.port, scheme=self.scheme, verify=self.verify)

        # 0. 是否有强行刷新的要求
        if self.default_force or is_force_update:
            logger.debug("key->[{}] now is force update, will update consul.".format(key))
            return consul_client.kv.put(key=key, value=json.dumps(value), *args, **kwargs)

        # 1. 先获取consul上的配置内容，计算对应的哈希值
        old_value = consul_client.kv.get(key)[1]
        if old_value is None:
            logger.info("old_value is missing, will refresh consul.")
            return consul_client.kv.put(key=key, value=json.dumps(value), *args, **kwargs)

        # 2. 判断本地的更暖心内容及其哈希值
        old_hash = hash_util.object_md5(json.loads(old_value["Value"]))
        new_hash = hash_util.object_md5(value)

        # 3. 判断哈希值是否存在更新，如果没有，直接返回
        if old_hash == new_hash:
            logger.debug("new value hash->[{}] is same as the one on consul, nothing will updated.".format(new_hash))
            return True

        # 4. 否则，更新内容；如果存在数据源，则记录数据源 ID
        if bk_data_id is not None:
            logger.info(
                "data_id->[%s] need update, new value hash->[%s] is different from the old hash->[%s]",
                bk_data_id,
                new_hash,
                old_hash,
            )
        else:
            logger.info(
                "new value hash->[%s] is different from the old hash->[%s], will updated it", new_hash, old_hash
            )
        return consul_client.kv.put(key=key, value=json.dumps(value), *args, **kwargs)
