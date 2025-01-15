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
import copy
import json
from typing import List, Tuple

import mock
import pytest
from mockredis import MockRedis

from api.bcs_cluster_manager.default import FetchClustersResource
from api.cmdb.default import GetHostByIP
from api.cmdb.define import Host
from api.kubernetes.default import FetchK8sNodeListByClusterResource
from metadata.models.bcs import BCSClusterInfo


@pytest.fixture
def patch_redis_tools(mocker):
    client = MockRedis()

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

    def mock_sadd_redis(key, val):
        return client.sadd(key, *val)

    def mock_srem_redis(key, val):
        return client.srem(key, *val)

    def mock_smembers(key):
        return client.smembers(key)

    def mock_set(key, val):
        client.redis[key] = val

    def mock_get_list(key):
        data = client.get(key)
        if not data:
            return []
        return json.loads(data)

    def mock_delete(key):
        client.delete(key)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", side_effect=mock_hset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hgetall", side_effect=mock_hgetall_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hget", side_effect=mock_hget_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hdel", side_effect=mock_hdel_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.publish", side_effect=mock_publish)
    mocker.patch("metadata.utils.redis_tools.RedisTools.sadd", side_effect=mock_sadd_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.srem", side_effect=mock_srem_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.smembers", side_effect=mock_smembers)
    mocker.patch("metadata.utils.redis_tools.RedisTools.set", side_effect=mock_set)
    mocker.patch("metadata.utils.redis_tools.RedisTools.get_list", side_effect=mock_get_list)
    mocker.patch("metadata.utils.redis_tools.RedisTools.delete", side_effect=mock_delete)


MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS = [
    {
        "clusterID": "BCS-K8S-00000",
        "clusterName": "蓝鲸社区版7.0",
        "projectID": "1",
        "businessID": "2",
        "environment": "prod",
        "status": "RUNNING",
        "createTime": "2022-05-15T21:43:32+08:00",
        "updateTime": "2022-05-15T21:43:32+08:00",
    }
]

MOCK_K8S_NODE_LIST_BY_CLUSTER = [
    [
        {
            "bcs_cluster_id": "BCS-K8S-00000",
            "node_ip": "127.0.0.1",
        }
    ],
    [
        {
            "bcs_cluster_id": "BCS-K8S-00001",
            "node_ip": "127.0.0.2",
        }
    ],
]

MOCK_CMDB_GET_HOST_BY_IP = [
    [
        Host(
            {
                "bk_biz_id": 2,
                "bk_host_innerip": "127.0.0.1",
                "ip": "127.0.0.1",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
            }
        )
    ],
    [
        Host(
            {
                "bk_biz_id": 2,
                "bk_host_innerip": "127.0.0.2",
                "ip": "127.0.0.2",
                "bk_host_id": 2,
                "bk_cloud_id": 1,
            }
        )
    ],
]


def pytest_configure():
    # 在初始化的时候，就需要对外部的gse zookeeper依赖进行mock，防止migration失败
    mock.patch("metadata.models.DataSource.refresh_gse_config", return_value=True)

    mock.patch("metadata.models.DataSource.create_mq", return_value=True)


@pytest.fixture
def add_bcs_cluster_info():
    BCSClusterInfo.objects.all().delete()

    BCSClusterInfo.objects.create(
        **{
            "cluster_id": "BCS-K8S-00000",
            "bcs_api_cluster_id": "BCS-K8S-00000",
            "bk_biz_id": 2,
            "project_id": "1",
            "status": "running",
            "domain_name": "domain_name_1",
            "port": 8000,
            "server_address_path": "clusters",
            "api_key_type": "authorization",
            "api_key_content": "",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": True,
            "cert_content": None,
            "K8sMetricDataID": 1,
            "CustomMetricDataID": 2,
            "K8sEventDataID": 3,
            "CustomEventDataID": 4,
            "SystemLogDataID": 0,
            "CustomLogDataID": 0,
            "creator": "admin",
            "last_modify_user": "",
        }
    )

    BCSClusterInfo.objects.create(
        **{
            "cluster_id": "BCS-K8S-00001",
            "bcs_api_cluster_id": "BCS-K8S-00001",
            "bk_biz_id": 2,
            "project_id": "2",
            "status": "running",
            "domain_name": "domain_name_2",
            "port": 8000,
            "server_address_path": "clusters",
            "api_key_type": "authorization",
            "api_key_content": "",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": True,
            "cert_content": None,
            "K8sMetricDataID": 5,
            "CustomMetricDataID": 6,
            "K8sEventDataID": 7,
            "CustomEventDataID": 8,
            "SystemLogDataID": 0,
            "CustomLogDataID": 0,
            "creator": "admin",
            "last_modify_user": "",
        }
    )
    yield
    BCSClusterInfo.objects.all().delete()


@pytest.fixture
def monkeypatch_cluster_management_fetch_clusters(monkeypatch):
    """返回集群列表 ."""
    monkeypatch.setattr(
        FetchClustersResource, "perform_request", lambda self, params: MOCK_BCS_CLUSTER_MANAGER_FETCH_CLUSTERS
    )


@pytest.fixture
def monkeypatch_k8s_node_list_by_cluster(monkeypatch):
    """返回一个集群的node信息 ."""
    monkeypatch.setattr(
        FetchK8sNodeListByClusterResource, "bulk_request", lambda self, params, **kwargs: MOCK_K8S_NODE_LIST_BY_CLUSTER
    )


@pytest.fixture
def monkeypatch_cmdb_get_info_by_ip(monkeypatch):
    """根据IP查询主机信息 ."""
    monkeypatch.setattr(GetHostByIP, "bulk_request", lambda self, params: MOCK_CMDB_GET_HOST_BY_IP)


class HashConsulMocker(object):
    result_list = {}

    def put(self, key, value):
        self.result_list.update({key: value})

    def delete(self, key, recurse=None):
        # 增加递归处理
        if recurse is True:
            deepped_result_list = copy.deepcopy(self.result_list)
            for k in deepped_result_list:
                if k.startswith(key):
                    self.result_list.pop(k)
        else:
            self.result_list.pop(key, None)

    def list(self, key: str) -> List:
        """返回格式
        (xxx, [{Key: xxx, Value: xxx}])
        """
        val = []
        for k in self.result_list:
            if k.startswith(key):
                val.append({"Key": k})

        return ("297766103", val if val else None)

    def get(self, key: str) -> Tuple:
        val = self.result_list.get(key)
        return ("297766103", {"Key": key, "Value": val} if val else None)
