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
import logging
from typing import Any, Dict, List, Optional, Union

import requests
from django.conf import settings
from elasticsearch import Elasticsearch as Elasticsearch
from elasticsearch5 import Elasticsearch as Elasticsearch5
from elasticsearch6 import Elasticsearch as Elasticsearch6
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_ES_TIMEOUT = 10

logger = logging.getLogger("metadata")


def get_value_if_not_none(value, default):
    if value is None:
        return default
    return value


def compose_es_hosts(host: str, port: int) -> List:
    """组装 es 需要的 host
    NOTE：兼容 IPV6， 格式组装为 [host]:port
    """
    if not host.startswith("["):
        host = "[" + host
    if not host.endswith("]"):
        host += "]"
    return [f"{host}:{port}"]


def get_client_by_datasource_info(datasource_info: Dict[str, Any]):
    is_ssl_verify: bool = datasource_info.get("is_ssl_verify") or False
    connection_info = {
        "hosts": compose_es_hosts(datasource_info["domain_name"], datasource_info["port"]),
        "verify_certs": is_ssl_verify,
        "use_ssl": is_ssl_verify,
    }

    # 如果需要身份验证
    username: Optional[str] = datasource_info["auth_info"].get("username")
    password: Optional[str] = datasource_info["auth_info"].get("password")
    if username is not None and password is not None:
        connection_info["http_auth"] = (username, password)

    schema = datasource_info.get("schema") or ""
    if schema == "https":
        connection_info["scheme"] = schema

    # 根据版本加载客户端
    elastic_client = Elasticsearch
    version = datasource_info.get("version") or ""
    if version.startswith("5."):
        elastic_client = Elasticsearch5
    elif version.startswith("6."):
        elastic_client = Elasticsearch6

    # 获取超时时间
    timeout_config = settings.METADATA_REQUEST_ES_TIMEOUT
    timeout = timeout_config.get(datasource_info["domain_name"])
    if not timeout:
        timeout = timeout_config.get("default") or DEFAULT_ES_TIMEOUT
    # 全局的请求超时时间
    # Refer：https://elasticsearch-py.readthedocs.io/en/v7.12.0/api.html?highlight=timeout#timeout
    es_client = elastic_client(**connection_info, timeout=timeout)
    return es_client


def get_client(cluster):
    from metadata.models import ClusterInfo

    cluster_info = cluster
    if isinstance(cluster, int):
        cluster_info = ClusterInfo.objects.get(cluster_id=cluster)

    datasource_info = {
        "port": cluster_info.port,
        "schema": cluster_info.schema,
        "version": cluster_info.version,
        "domain_name": cluster_info.domain_name,
        "is_ssl_verify": cluster_info.is_ssl_verify,
        "auth_info": {"password": cluster_info.password, "username": cluster_info.username},
    }
    return get_client_by_datasource_info(datasource_info)


def get_cluster_disk_size(es_client, kind="total", bytes="b"):
    allocations = es_client.cat.allocation(format="json", bytes=bytes, params={"request_timeout": 10})
    return sum([int(get_value_if_not_none(node.get(f"disk.{kind}"), 0)) for node in allocations])


def es_retry_session(
    es_client: Union[Elasticsearch, Elasticsearch5, Elasticsearch6], retry_num: int, backoff_factor: float, **kwargs
) -> Union[Elasticsearch, Elasticsearch5, Elasticsearch6]:
    # 创建一个 Retry 对象，设置重试次数、延迟时间等参数
    # 等待[0.2s, 0.4s, 0.8s]
    retry_strategy = Retry(total=retry_num, backoff_factor=backoff_factor, **kwargs)

    # 创建一个 HTTPAdapter 对象，并将重试策略应用于该对象
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 使用 Elasticsearch 对象的 transport 属性来获取 Transport 对象
    transport = es_client.transport

    # 将自定义的 Session 对象添加到 Transport 对象的 session 属性中
    transport.session = session

    return es_client
