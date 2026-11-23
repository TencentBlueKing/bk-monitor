# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import ipaddress
import socket
from copy import deepcopy

from django.utils.translation import gettext_lazy as _
from elasticsearch import Elasticsearch as Elasticsearch
from elasticsearch import exceptions as ElasticsearchExceptions
from elasticsearch5 import Elasticsearch as Elasticsearch5
from elasticsearch5 import exceptions as Elasticsearch5Exceptions
from elasticsearch6 import Elasticsearch as Elasticsearch6
from elasticsearch6 import exceptions as Elasticsearch6Exceptions

from apps.log_esquery.exceptions import (
    EsClientAuthenticatorException,
    EsClientHostPortException,
    EsClientSocketException,
)

# date_histogram 的 interval 参数在 7.2 起被 fixed_interval/calendar_interval 取代，8.0 起移除
ES_NEW_SYNTAX_MIN_VERSION = (7, 2)
# calendar_interval 只接受单个单位，5m/30s 这类倍数只能用 fixed_interval
CALENDAR_INTERVALS = frozenset(
    {"1m", "1h", "1d", "1w", "1M", "1q", "1y"} | {"minute", "hour", "day", "week", "month", "quarter", "year"}
)


def parse_es_version(version: str | None) -> tuple[int, ...] | None:
    """解析 ES 版本号为主/次/修订版本整数元组，无法解析时返回 None。"""
    if not version:
        return None
    parts = []
    for segment in str(version).strip().split(".")[:3]:
        segment = segment.split("-", 1)[0]
        if not segment.isdigit():
            return None
        parts.append(int(segment))
    return tuple(parts) or None


def is_es_version_gte(version: str | None, target: tuple[int, ...], default: bool = False) -> bool:
    """判断 ES 版本是否不低于 target，版本未知时返回 default。"""
    parsed = parse_es_version(version)
    if parsed is None:
        return default
    width = max(len(parsed), len(target))
    padded_version = parsed + (0,) * (width - len(parsed))
    padded_target = target + (0,) * (width - len(target))
    return padded_version >= padded_target


def build_date_histogram_interval_params(interval: str, es_version: str | None = None) -> dict[str, str]:
    """按 ES 版本与窗口语义构造 date_histogram 间隔参数。"""
    # 版本未知时保持旧语法，避免老集群查询失败；interval 在 7.x 仅告警不报错
    if not is_es_version_gte(es_version, ES_NEW_SYNTAX_MIN_VERSION):
        return {"interval": interval}
    if interval in CALENDAR_INTERVALS:
        return {"calendar_interval": interval}
    return {"fixed_interval": interval}


def adapt_es_query_body(body: dict, es_version: str | None) -> dict:
    """使用实际连接版本转换聚合语法，避免多集群查询共用可变请求。"""
    body = deepcopy(body)

    def adapt_aggs(aggs):
        if not isinstance(aggs, dict):
            return
        for agg in aggs.values():
            if not isinstance(agg, dict):
                continue
            histogram = agg.get("date_histogram")
            if isinstance(histogram, dict):
                if "interval" in histogram and is_es_version_gte(es_version, ES_NEW_SYNTAX_MIN_VERSION):
                    histogram.update(build_date_histogram_interval_params(histogram.pop("interval"), es_version))
                elif not is_es_version_gte(es_version, ES_NEW_SYNTAX_MIN_VERSION):
                    for key in ("fixed_interval", "calendar_interval"):
                        if key in histogram:
                            histogram["interval"] = histogram.pop(key)
            terms = agg.get("terms")
            if isinstance(terms, dict):
                order = terms.get("order")
                orders = order if isinstance(order, list) else [order]
                old_key, new_key = ("_term", "_key") if is_es_version_gte(es_version, (6, 0)) else ("_key", "_term")
                for item in orders:
                    if isinstance(item, dict) and old_key in item:
                        item[new_key] = item.pop(old_key)
            adapt_aggs(agg.get("aggs"))
            adapt_aggs(agg.get("aggregations"))

    adapt_aggs(body.get("aggs"))
    adapt_aggs(body.get("aggregations"))
    return body


def get_es_client(
    *,
    version: str,
    hosts: list,
    username: str,
    password: str,
    port: int,
    sniffer_timeout=600,
    verify_certs=False,
    **kwargs,
) -> Elasticsearch:
    # 根据版本加载客户端
    if version and version.startswith("5."):
        es_client = Elasticsearch5
    elif version and version.startswith("6."):
        es_client = Elasticsearch6
    else:
        # 7.x/8.x/9.x 统一复用 7.17 客户端，响应在业务层按版本适配
        es_client = Elasticsearch

    # 由于IPV6地址需要加[], 所以需要对hosts进行处理
    new_hosts = []
    for host in hosts:
        try:
            # 尝试将主机名解析为 IP 地址
            ip = ipaddress.ip_address(host)
            # 如果是 IPv6 地址，返回带方括号的格式
            if isinstance(ip, ipaddress.IPv6Address):
                host = f"[{host}]"
        except ValueError:
            # 如果不是有效的 IP 地址，返回原始主机名
            pass
        new_hosts.append(host)
    hosts = new_hosts

    http_auth = (username, password) if password else None
    return es_client(
        hosts, http_auth=http_auth, port=port, sniffer_timeout=sniffer_timeout, verify_certs=verify_certs, **kwargs
    )


def es_socket_ping(host: str, port: int):
    """
    ES ping by socket
    """
    if not host or not port:
        raise EsClientHostPortException()

    es_address: tuple = (host, port)
    try:
        # 先尝试ipv4
        cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cs.settimeout(2)
        status: int = cs.connect_ex(es_address)
    except socket.gaierror:  # ip协议不匹配时, 会抛出gaierror
        # ipv4失败，尝试ipv6
        cs = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        cs.settimeout(2)
        status: int = cs.connect_ex(es_address)
    except Exception as e:  # pylint: disable=broad-except
        raise EsClientSocketException(
            EsClientSocketException.MESSAGE.format(error=_("IP or PORT can not be reached, %s").format(e=e))
        )

    if status != 0:
        raise EsClientSocketException(EsClientSocketException.MESSAGE.format(error=_("IP or PORT can not be reached")))
    cs.close()


def es_client_ping(es_client):
    try:
        result = es_client.transport.perform_request("HEAD", "/", params=None)
    except (
        ElasticsearchExceptions.AuthenticationException,
        Elasticsearch5Exceptions.AuthenticationException,
        Elasticsearch6Exceptions.AuthenticationException,
    ):
        raise EsClientAuthenticatorException()
    except Exception as error:
        raise EsClientSocketException(EsClientSocketException.MESSAGE.format(error=error))
    if not result:
        raise EsClientSocketException(EsClientSocketException.MESSAGE.format(error=_("ES is not alive")))

    return result
