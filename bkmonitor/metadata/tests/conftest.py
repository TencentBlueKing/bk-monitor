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
from kubernetes.dynamic.exceptions import NotFoundError, ResourceNotFoundError
from metadata.models.bcs import BCSClusterInfo
from kubernetes import client as k8s_client
from metadata import config


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
    mock.patch(
        "alarm_backends.core.storage.redis.redis.Redis", return_value=fakeredis.FakeRedis(decode_responses=True)
    ).start()


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


@pytest.fixture(
    autouse=True,
)
def enable_db_access(db):
    pass


def singleton(cls):
    """单例模式装饰器"""
    # 使用字典存储类的实例，保证每个类有独立的实例存储
    instances = {}

    def get_instance(*args, **kwargs):
        # 如果类实例不存在，则创建新实例
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        # 返回已存在的实例
        return instances[cls]

    return get_instance


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


@singleton
class MockHashConsul:
    """
    HashConsul的模拟类，用于单元测试中替代真实的Consul客户端
    避免在测试过程中发起真实的网络请求
    """

    def __init__(self, host="127.0.0.1", port=8500, scheme="http", verify=None, default_force=False):
        """
        初始化模拟的HashConsul

        :param host: consul agent IP地址
        :param port: consul agent 端口
        :param scheme: consul agent协议
        :param verify: SSL 验证
        :param default_force: 默认是否需要强制更新
        """
        # 存储consul agent连接信息，但不会实际使用
        self.host = host
        self.port = port
        self.scheme = scheme
        self.verify = verify

        # 是否强行写入
        self.default_force = default_force

        # 模拟存储键值对的数据结构
        self._kv_store = {}

        # 记录方法调用历史，便于测试验证
        self._call_history = []

    def delete(self, key, recurse=None):
        """
        模拟删除指定kv

        :param key: 要删除的键
        :param recurse: 是否递归删除
        """
        # 记录调用历史
        self._call_history.append({"method": "delete", "key": key, "recurse": recurse})

        # 执行删除操作
        if recurse:
            # 删除所有以key为前缀的键
            keys_to_delete = [k for k in self._kv_store.keys() if k.startswith(key)]
            for k in keys_to_delete:
                del self._kv_store[k]
        else:
            # 删除单个键
            if key in self._kv_store:
                del self._kv_store[key]

        # 模拟日志记录
        print(f"key->[{key}] has been deleted")

    def get(self, key):
        """
        模拟获取指定kv

        :param key: 要获取的键
        :return: 模拟的Consul响应格式 (index, value)
        """
        # 记录调用历史
        self._call_history.append({"method": "get", "key": key})

        # 返回模拟的Consul响应格式
        if key in self._kv_store:
            return (1, self._kv_store[key])
        else:
            return (1, None)

    def list(self, key):
        """
        模拟列出指定前缀的所有键值对

        :param key: 键前缀
        :return: 模拟的Consul响应格式 (index, values)
        """
        # 记录调用历史
        self._call_history.append({"method": "list", "key": key})

        # 查找所有以指定前缀开头的键
        result = []
        for k, v in self._kv_store.items():
            if k.startswith(key):
                result.append(v)

        return (1, result if result else None)

    def put(self, key, value, is_force_update=False, bk_data_id=None, *args, **kwargs):
        """
        模拟更新Consul键值对配置

        :param key: Consul键路径
        :param value: 配置内容
        :param is_force_update: 强制更新标志
        :param bk_data_id: 可选数据源ID
        :return: True表示更新成功
        """
        # 记录调用历史
        self._call_history.append(
            {"method": "put", "key": key, "value": value, "is_force_update": is_force_update, "bk_data_id": bk_data_id}
        )

        # 模拟HashConsul的逻辑
        import json
        from metadata.utils import hash_util

        # 强制更新模式处理
        if self.default_force or is_force_update:
            print(f"key->[{key}] now is force update, will update consul.")
            self._kv_store[key] = {"Key": key, "Value": json.dumps(value)}
            return True

        # 获取当前存储的值
        old_value = self._kv_store.get(key, None)
        if old_value is None:
            print("old_value is missing, will refresh consul.")
            self._kv_store[key] = {"Key": key, "Value": json.dumps(value)}
            return True

        # 配置变更检测
        old_hash = hash_util.object_md5(json.loads(old_value["Value"]))
        new_hash = hash_util.object_md5(value)

        if old_hash == new_hash:
            print(f"new value hash->[{new_hash}] is same as the one on consul, nothing will updated.")
            return True

        # 执行配置更新
        if bk_data_id is not None:
            print(
                "data_id->[%s] need update, new value hash->[%s] is different from the old hash->[%s]",
                bk_data_id,
                new_hash,
                old_hash,
            )
        else:
            print("new value hash->[%s] is different from the old hash->[%s], will updated it", new_hash, old_hash)

        self._kv_store[key] = {"Key": key, "Value": json.dumps(value)}
        return True

    def get_call_history(self):
        """
        获取方法调用历史记录，用于测试验证

        :return: 调用历史列表
        """
        return self._call_history.copy()

    def clear_call_history(self):
        """
        清空方法调用历史记录
        """
        self._call_history.clear()

    def set_kv_store(self, kv_store):
        """
        设置模拟的键值存储，用于测试初始化特定状态

        :param kv_store: 键值存储字典
        """
        self._kv_store = kv_store


class _MockResourceDescriptor:
    """测试用资源描述符，模拟动态客户端返回的资源对象"""

    def __init__(self, api_version: str, kind: str):
        self.api_version = api_version
        self.kind = kind


class _MockResources:
    """测试用 resources 入口，提供 get() 获取资源描述符"""

    def __init__(self, d_client: "MockDynamicClient"):
        self._client = d_client

    def get(self, api_version: str, kind: str):
        # 如果CRD未定义，模拟ResourceNotFoundError
        if not self._client._is_crd_defined(api_version, kind):
            raise ResourceNotFoundError(f"CRD {api_version}/{kind} not found")
        return _MockResourceDescriptor(api_version=api_version, kind=kind)


class _Exception:
    def __init__(self, e):
        self.status = "Failure"
        self.reason = e
        self.body = ""
        self.headers = ""


@singleton
class MockDynamicClient:
    """
    测试用动态客户端模拟对象（对齐 ensure_data_id_resource 与 init_resource 期望行为）

    特性：
    - 接收 k8s_client.ApiClient 对象（与真实 DynamicClient 保持一致）
    - 支持 resources.get()、get()、create()、replace() 方法
    - 模拟 NotFoundError（资源不存在）与 ResourceNotFoundError（CRD未定义）
    - 模拟 resourceVersion 约束：replace 需携带与当前一致的 resourceVersion，成功后自增
    - 支持根据 make_config 产物预置资源，便于直接对齐 init_resource 的配置内容

    使用示例（单元测试中可直接替换被测代码中的 DynamicClient）：
        from bkmonitor.metadata.models.bcs.utils import MockDynamicClient
        from kubernetes import client as k8s_client

        # 创建模拟客户端（传入 ApiClient 对象）
        api_client = k8s_client.ApiClient()
        d_client = MockDynamicClient(api_client)

        # 预置CRD开关
        d_client.set_crd_defined(
            api_version=f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
            kind=config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND,
            defined=True
        )

        # 通过 make_config 产物预置资源
        expected = cluster_info.make_config(register_info, usage=usage, is_fed_cluster=False)
        resource = d_client.resources.get(
            api_version=f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
            kind=config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND,
        )
        d_client.create(resource, body=expected)

        # 测试时可 monkeypatch：
        # monkeypatch.setattr(dynamic_client, "DynamicClient", MockDynamicClient)
    """

    def __init__(
        self,
        api_client: k8s_client.ApiClient,
        crd_defined: dict[tuple[str, str], bool] | None = None,
        initial_resources: dict[str, dict[str, dict]] | None = None,
    ):
        # 保存 api_client 引用（虽然模拟场景不使用，但保持接口一致）
        self.api_client = api_client

        # 已定义CRD集合：(api_version, kind) -> bool
        default_key = (
            f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
            config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND,
        )
        self._crd_defined: dict[tuple[str, str], bool] = {default_key: True}
        if crd_defined:
            self._crd_defined.update(crd_defined)

        # 存储资源：kind -> { name -> body(dict) }
        self._store: dict[str, dict[str, dict]] = initial_resources.copy() if initial_resources else {}
        self.resources = _MockResources(self)

    def _is_crd_defined(self, api_version: str, kind: str) -> bool:
        return self._crd_defined.get((api_version, kind), False)

    def set_crd_defined(self, api_version: str, kind: str, defined: bool = True):
        """测试中动态切换CRD是否已定义"""
        self._crd_defined[(api_version, kind)] = defined

    def seed_resources_from_configs(self, configs: list[dict]):
        """根据 make_config 产物批量预置资源"""
        for body in configs or []:
            kind = body.get("kind")
            name = (body.get("metadata") or {}).get("name")
            if not kind or not name:
                continue
            kind_store = self._store.setdefault(kind, {})
            body_copy = json.loads(json.dumps(body))
            # 初始resourceVersion设为"1"
            body_copy.setdefault("metadata", {})
            body_copy["metadata"]["resourceVersion"] = body_copy["metadata"].get("resourceVersion") or "1"
            kind_store[name] = body_copy

    def get(self, resource: _MockResourceDescriptor, name: str) -> dict:
        # CRD未定义
        if not self._is_crd_defined(resource.api_version, resource.kind):
            raise ResourceNotFoundError(_Exception(f"CRD {resource.api_version}/{resource.kind} not found"))
        # 资源不存在
        kind_store = self._store.get(resource.kind, {})
        if name not in kind_store:
            raise NotFoundError(_Exception(f"resource {name} not found for kind {resource.kind}"))
        # 返回副本，避免外部修改影响内部状态
        return json.loads(json.dumps(kind_store[name]))

    def create(self, resource: _MockResourceDescriptor, body: dict) -> dict:
        if not self._is_crd_defined(resource.api_version, resource.kind):
            raise ResourceNotFoundError(_Exception(f"CRD {resource.api_version}/{resource.kind} not found"))
        name = (body.get("metadata") or {}).get("name")
        if not name:
            raise ValueError("body.metadata.name is required")
        kind_store = self._store.setdefault(resource.kind, {})
        if name in kind_store:
            raise ValueError(f"resource {name} already exists for kind {resource.kind}")
        body_copy = json.loads(json.dumps(body))
        body_copy.setdefault("metadata", {})
        body_copy["metadata"]["resourceVersion"] = body_copy["metadata"].get("resourceVersion") or "1"
        kind_store[name] = body_copy
        return json.loads(json.dumps(body_copy))

    def replace(self, resource: _MockResourceDescriptor, body: dict) -> dict:
        if not self._is_crd_defined(resource.api_version, resource.kind):
            raise ResourceNotFoundError(_Exception(f"CRD {resource.api_version}/{resource.kind} not found"))
        name = (body.get("metadata") or {}).get("name")
        if not name:
            raise ValueError("body.metadata.name is required")
        kind_store = self._store.setdefault(resource.kind, {})
        if name not in kind_store:
            raise NotFoundError(_Exception(f"resource {name} not found for kind {resource.kind}"))

        current = kind_store[name]
        current_rv = (current.get("metadata") or {}).get("resourceVersion") or "1"
        incoming_rv = (body.get("metadata") or {}).get("resourceVersion")

        # 对齐 Kubernetes 行为：replace 必须带匹配的 resourceVersion
        if incoming_rv is None or str(incoming_rv) != str(current_rv):
            raise ValueError(f"resourceVersion conflict: incoming={incoming_rv}, current={current_rv}")

        # 成功后自增 resourceVersion
        new_body = json.loads(json.dumps(body))
        new_body.setdefault("metadata", {})
        try:
            new_body["metadata"]["resourceVersion"] = str(int(current_rv) + 1)
        except Exception:
            new_body["metadata"]["resourceVersion"] = "1"

        kind_store[name] = new_body
        return json.loads(json.dumps(new_body))
