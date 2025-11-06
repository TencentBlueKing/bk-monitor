"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
from unittest import mock
from unittest.mock import PropertyMock

import fakeredis
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
    mock.patch(
        "metadata.utils.redis_tools.RedisTools.client",
        new_callable=PropertyMock,
        return_value=fakeredis.FakeRedis(decode_responses=False),
    ).start()

    # 预先设置所有必需的 Redis 和 RabbitMQ 配置，避免导入时缺少设置
    import django.conf

    redis_conf = {"host": "localhost", "port": 6379, "db": 9, "password": ""}
    redis_log_conf = {"host": "localhost", "port": 6379, "db": 7, "password": ""}
    redis_cache_conf = {"host": "localhost", "port": 6379, "db": 8, "password": ""}
    redis_service_conf = {"host": "localhost", "port": 6379, "db": 10, "password": "", "socket_timeout": 10}

    # 在 settings 对象上设置属性
    try:
        # 如果 settings 已经初始化，直接设置
        if hasattr(django.conf, "settings") and django.conf.settings._wrapped:
            setattr(django.conf.settings, "REDIS_CELERY_CONF", redis_conf)
            setattr(django.conf.settings, "REDIS_QUEUE_CONF", redis_conf)
            setattr(django.conf.settings, "REDIS_SERVICE_CONF", redis_service_conf)
            setattr(django.conf.settings, "REDIS_CACHE_CONF", redis_cache_conf)
            setattr(django.conf.settings, "REDIS_LOG_CONF", redis_log_conf)
            # RabbitMQ 配置
            setattr(django.conf.settings, "RABBITMQ_HOST", "localhost")
            setattr(django.conf.settings, "RABBITMQ_PORT", 5672)
            setattr(django.conf.settings, "RABBITMQ_VHOST", "bk_monitorv3")
            setattr(django.conf.settings, "RABBITMQ_USER", "guest")
            setattr(django.conf.settings, "RABBITMQ_PASS", "guest")
            setattr(django.conf.settings, "CELERY_WORKERS", 4)
            setattr(django.conf.settings, "CACHE_BACKEND_TYPE", "RedisCache")
    except Exception:
        pass

    # Monkey patch 迁移操作，跳过有问题的字段修改
    from django.db.migrations.operations.fields import AlterField

    original_database_forwards = AlterField.database_forwards

    def patched_database_forwards(self, app_label, schema_editor, from_state, to_state):
        # 跳过会导致索引键长度问题的字段修改
        if app_label == "apm_web" and self.model_name == "apmmetaconfig" and self.name == "level_key":
            # 跳过实际数据库操作，只更新状态
            return
        return original_database_forwards(self, app_label, schema_editor, from_state, to_state)

    AlterField.database_forwards = patched_database_forwards


def pytest_sessionstart(session):
    """在 Django 设置完成后进行额外的 mock"""
    # Mock alarm_backends redis，此时 Django 设置应该已经完成
    try:
        mock.patch(
            "alarm_backends.core.storage.redis.redis.Redis", return_value=fakeredis.FakeRedis(decode_responses=True)
        ).start()
    except (AttributeError, ImportError):
        pass

    # 确保所有 Redis 和 RabbitMQ 配置都已设置
    from django.conf import settings

    try:
        redis_conf = {"host": "localhost", "port": 6379, "db": 9, "password": ""}
        redis_log_conf = {"host": "localhost", "port": 6379, "db": 7, "password": ""}
        redis_cache_conf = {"host": "localhost", "port": 6379, "db": 8, "password": ""}
        redis_service_conf = {"host": "localhost", "port": 6379, "db": 10, "password": "", "socket_timeout": 10}

        if not hasattr(settings, "REDIS_CELERY_CONF"):
            setattr(settings, "REDIS_CELERY_CONF", redis_conf)
        if not hasattr(settings, "REDIS_QUEUE_CONF"):
            setattr(settings, "REDIS_QUEUE_CONF", redis_conf)
        if not hasattr(settings, "REDIS_SERVICE_CONF"):
            setattr(settings, "REDIS_SERVICE_CONF", redis_service_conf)
        if not hasattr(settings, "REDIS_CACHE_CONF"):
            setattr(settings, "REDIS_CACHE_CONF", redis_cache_conf)
        if not hasattr(settings, "REDIS_LOG_CONF"):
            setattr(settings, "REDIS_LOG_CONF", redis_log_conf)
        # RabbitMQ 配置
        if not hasattr(settings, "RABBITMQ_HOST"):
            setattr(settings, "RABBITMQ_HOST", "localhost")
        if not hasattr(settings, "RABBITMQ_PORT"):
            setattr(settings, "RABBITMQ_PORT", 5672)
        if not hasattr(settings, "RABBITMQ_VHOST"):
            setattr(settings, "RABBITMQ_VHOST", "bk_monitorv3")
        if not hasattr(settings, "RABBITMQ_USER"):
            setattr(settings, "RABBITMQ_USER", "guest")
        if not hasattr(settings, "RABBITMQ_PASS"):
            setattr(settings, "RABBITMQ_PASS", "guest")
        if not hasattr(settings, "CELERY_WORKERS"):
            setattr(settings, "CELERY_WORKERS", 4)
        if not hasattr(settings, "CACHE_BACKEND_TYPE"):
            setattr(settings, "CACHE_BACKEND_TYPE", "RedisCache")
    except Exception:
        pass


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


class HashConsulMocker:
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

    def list(self, key: str) -> list:
        """返回格式
        (xxx, [{Key: xxx, Value: xxx}])
        """
        val = []
        for k in self.result_list:
            if k.startswith(key):
                val.append({"Key": k})

        return ("297766103", val if val else None)

    def get(self, key: str) -> tuple:
        val = self.result_list.get(key)
        return ("297766103", {"Key": key, "Value": val} if val else None)


@pytest.fixture(
    autouse=True,
)
def enable_db_access(db):
    pass
