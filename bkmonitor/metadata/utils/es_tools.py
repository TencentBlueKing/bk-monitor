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
from typing import List

from elasticsearch import Elasticsearch as Elasticsearch
from elasticsearch5 import Elasticsearch as Elasticsearch5
from elasticsearch6 import Elasticsearch as Elasticsearch6


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


def get_client(cluster):
    from metadata.models import ClusterInfo

    cluster_info = cluster
    if not isinstance(cluster, ClusterInfo):
        cluster_info = ClusterInfo.objects.get(cluster_id=cluster)

    connection_info = {
        "hosts": compose_es_hosts(cluster_info.domain_name, cluster_info.port),
        "verify_certs": cluster_info.is_ssl_verify,
        "use_ssl": cluster_info.is_ssl_verify,
    }

    # 如果需要身份验证
    if cluster_info.username is not None and cluster_info.password is not None:
        connection_info["http_auth"] = (cluster_info.username, cluster_info.password)

    if cluster_info.schema == "https":
        connection_info["scheme"] = cluster_info.schema

    # 根据版本加载客户端
    elastic_client = Elasticsearch
    if cluster_info.version.startswith("5."):
        elastic_client = Elasticsearch5
    elif cluster_info.version.startswith("6."):
        elastic_client = Elasticsearch6
    es_client = elastic_client(**connection_info)
    return es_client


def get_cluster_disk_size(es_client, kind="total", bytes="b"):
    allocations = es_client.cat.allocation(format="json", bytes=bytes, params={"request_timeout": 10})
    return sum([int(get_value_if_not_none(node.get(f"disk.{kind}"), 0)) for node in allocations])
