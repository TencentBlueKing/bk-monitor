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
import os

from django.db import migrations

logger = logging.getLogger("metadata")

models = {
    "InfluxDBClusterInfo": None,
    "InfluxDBHostInfo": None,
}


# 判断这个环境是否已经升级，环境变量都含有了模块前缀
is_module_prefix = True if os.environ.get("INFLUXDB_IP0", None) is None else False


def get_environ(name, is_list=False):
    """
    获取环境变量的值，可能返回一个单独的值或一个数组（多个值）
    :param name: 变量名
    :param is_list: 是否遍历多个值返回数组
    :return: string | list
    """
    name = "{}_{}".format("BKMONITOR", name) if is_module_prefix else name
    # 如果是需要单个值，直接返回
    if not is_list:
        return os.environ.get(name)
    # 如果需要多个值，则从0开始进行遍历
    index = 0
    result = []
    while True:
        current_name = "{}{}".format(name, index)
        current_value = os.environ.get(current_name)
        # 如果当前的这个遍历已经获取不到值了，则直接退出
        if current_value is None:
            break
        result.append(current_value)
        index += 1
    return result


def init_influxdb_backend_info(apps, *args, **kwargs):
    """追加influxdb backend的初始化数据"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    InfluxDBClusterInfo = models["InfluxDBClusterInfo"]
    InfluxDBHostInfo = models["InfluxDBHostInfo"]

    # 获取用户名和密码
    username = get_environ("INFLUXDB_USER")
    password = get_environ("INFLUXDB_PASS")
    # 获取所有主机的信息
    port = get_environ("INFLUXDB_PORT")
    host_list = get_environ("INFLUXDB_IP", is_list=True)

    for index, ip in enumerate(host_list):
        host_name = "INFLUXDB_HOST{}".format(index)

        # 创建集群信息
        InfluxDBClusterInfo.objects.create(host_name=host_name, cluster_name="default")
        # 创建具体的机器信息
        InfluxDBHostInfo.objects.create(
            host_name=host_name,
            domain_name=ip,
            port=port,
            username=username if username is not None else "",
            password=password if password is not None else "",
            description="influxdb host for default cluster.",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0031_fix_kafka_label_config"),
    ]

    operations = [migrations.RunPython(init_influxdb_backend_info)]
