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


import functools
import json
import logging
import re
import os
import socket
import subprocess

import dns.resolver
import requests
from django.conf import settings

from bkmonitor.utils import consul
from bkmonitor.utils.supervisor_utils import get_supervisor_client

logger = logging.getLogger("self_monitor")

# kafka采集数目
KAFKA_COLLECT_COUNT = 5
PROMETHEUS_METIC_REGEX = r"(.*){?(.*)}?\s(.*)"
DIMENSION_REGEX = r'(.*)="(.*)"'


def simple_check(func):
    @functools.wraps(func)
    def wrapper(manager, result, min_value=None, max_value=None, **kwargs):
        try:
            value = func(**kwargs)
        except Exception as err:
            raise result.fail(str(err))

        if min_value is not None and value < min_value:
            result.fail("{!r} < {!r}".format(value, min_value), value)
        elif max_value is not None and value > max_value:
            result.fail("{!r} > {!r}".format(value, max_value), value)
        else:
            result.ok(value)

    return wrapper


def generate_function(register, func_doc, func, *func_args, **func_kwargs):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    f = functools.partial(wrapper, *func_args, **func_kwargs)
    f.__doc__ = func_doc
    return register(f)


def check_collector_status(connector_name):
    """
    根据connector name获取对应的组件状态
    :param connector_name:
    :return:
    """
    result_list = []
    # 查看当前集群
    cluster_content = requests.get("http://dataapi.service.consul:10011/databus/list_connector_cluster").content
    cluster_content_dict = json.loads(cluster_content)
    # 获取etl的主机和端口
    if cluster_content_dict["result"]:
        host = None
        port = None
        # 查询etl对应的端口
        for i in cluster_content_dict["data"]:
            if i["cluster_name"] == connector_name:
                host = i["host"]
                port = i["port"]
                break
    else:
        raise Exception("error occurred when querying the connector clusters")
    # 拼接地址获取etl信息
    if host and port:
        address = "http://{host}:{port}/connectors".format(host=host, port=port)
        connector_content = requests.get(address).content
        # 获取集群列表
        connector_content_list = json.loads(connector_content)
        for item in connector_content_list:
            # 每个任务的地址
            item_address = "{address}/{item}/status".format(address=address, item=item)
            item_content = requests.get(item_address).content
            item_content_dict = json.loads(item_content)
            status = item_content_dict["connector"]["state"] == "RUNNING" and all(
                [j["state"] == "RUNNING" for j in item_content_dict["tasks"]]
            )
            # 0表示正常，1表示关注，2表示错误
            if status:
                status = 0
            else:
                status = 2
            result_list.append({"name": item_content_dict["name"], "status": status})
    else:
        raise Exception(
            "error occurred when getting the host and port of {connector_name}".format(connector_name=connector_name)
        )
    return result_list


def get_ip_and_port(name):
    # 获取ip通过consul，但是consul没有记录port，所以端口数据由配置文件提供
    port = settings.SELFMONITOR_PORTS.get(name, "")

    # influxdb的配置应该是改环境变量获取了
    if not port and name == "influxdb":
        port = int(os.environ.get("BK_MONITOR_INFLUXDB_PORT", None))

    if not port:
        raise Exception("get {} port from settings failed".format(name))
    client = consul.BKConsul()
    result = client.catalog.service(name)
    if not result:
        raise Exception("get {} data failed".format(name))
    if len(result) != 2:
        raise Exception("length of {} status not as expected(2),current length:{}".format(name, len(result)))
    result_status_list = result[1]
    ip_port_list = []
    for gse_status in result_status_list:
        ip_port_list.append({"ip": gse_status["Address"], "port": port})
    return ip_port_list


def check_port_status(component_name, ip, port):
    """
    检查对应地址和端口的gse状态是否正常
    :param component_name:
    :param ip:
    :param port:
    :return:
    """
    # 检查对应的ip和端口是否可以连接
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.connect((ip, port))
        return True
    except Exception as e:
        logger.exception("%s, component name: %s, ip: %s, port: %s", str(e), component_name, ip, port)
        return False
    finally:
        test_socket.close()


def check_port_list_status(component_name, ip_port_list):
    # ip地址的正则模式
    ip_pattern = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    result_list = []
    for item in ip_port_list:
        ip = item["ip"]
        port = item["port"]
        # ip不能为空，且满足ip地址的正则匹配
        if ip != "" and ip_pattern.match(ip):
            status = check_port_status(component_name, ip, port)
            if status:
                # 用名称加ip作为唯一的名称
                result_list.append(
                    {"name": "{component_name}: {ip}".format(component_name=component_name, ip=ip), "status": 0}
                )
            else:
                failed_message = "cannot connect to {component_name}: ip: {ip}, port: {port}".format(
                    component_name=component_name, ip=ip, port=port
                )
                result_list.append(
                    {
                        "name": "{component_name}: {ip}".format(component_name=component_name, ip=ip),
                        "status": 2,
                        "message": failed_message,
                    }
                )
        else:
            failed_message = "{ip} is not a valid ip address".format(ip=ip)
            raise Exception(failed_message)
    return result_list


def get_collector_status(component_name, ip_script, port_script):
    """
    检测对应组件的健康状态
    :param component_name:
    :param ip_script:
    :param port_script:
    :return:
    """
    result_list = []
    # 运行对应脚本，获取到对应的ip地址列表文件
    ips_output = subprocess.check_output(["/bin/bash", "-c", ip_script])
    # gse的部署端口
    try:
        component_port = int(subprocess.check_output(["/bin/bash", "-c", port_script]))
    except ValueError:
        failed_message = "Error: can't get port of {component_name}.".format(component_name=component_name)
        raise Exception(failed_message)

    # ip地址的正则模式
    ip_pattern = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    # 读取对应的文件获得ip列表
    for i in ips_output.split():
        line = i.strip()
        # line不能为空，且满足ip地址的正则匹配
        if line != "" and ip_pattern.match(line):
            status = check_port_status(component_name, line, component_port)
            if status:
                # 用名称加ip作为唯一的名称
                result_list.append(
                    {"name": "{component_name}: {ip}".format(component_name=component_name, ip=line), "status": 0}
                )
            else:
                failed_message = "cannot connect to {component_name}: ip: {ip}, port: {port}".format(
                    component_name=component_name, ip=line, port=component_port
                )
                result_list.append(
                    {
                        "name": "{component_name}: {ip}".format(component_name=component_name, ip=line),
                        "status": 2,
                        "message": failed_message,
                    }
                )
        else:
            failed_message = "{ip} is not a valid ip address".format(ip=line)
            raise Exception(failed_message)
    return result_list


def resolve_domain(domain):
    """解析域名得到IP列表"""
    resolve_items = dns.resolver.query(domain, "A")
    return [item.address for item in resolve_items]


def get_process_info_by_group(name):
    client = get_supervisor_client()
    info = client.supervisor.getAllProcessInfo()
    for i in info:
        if i.get("group") == name:
            yield i
