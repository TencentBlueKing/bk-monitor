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

models = {"ClusterInfo": None}


def get_environ(name, is_list=False):
    """
    获取环境变量的值，可能返回一个单独的值或一个数组（多个值）
    :param name: 变量名
    :param is_list: 是否遍历多个值返回数组
    :return: string | list
    """
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


def init_es_storage_info(apps, *args, **kwargs):
    """增加ES存储集群的初始化数据"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ClusterInfo = models["ClusterInfo"]

    es_host = os.environ.get("BK_MONITOR_ES7_HOST", "")
    es_port = int(os.environ.get("BK_MONITOR_ES7_REST_PORT", 0))
    es_username = os.environ.get("BK_MONITOR_ES7_USER", "")
    es_password = os.environ.get("BK_MONITOR_ES7_PASSWORD", "")

    # 创建集群信息
    ClusterInfo.objects.create(
        cluster_name="es_cluster1",
        cluster_type="elasticsearch",
        # 域名和端口屏蔽
        domain_name=es_host,
        port=es_port,
        description="init es cluster",
        is_default_cluster=True,
        # 用户名及密码配置
        username=es_username,
        password=es_password,
        # 注意：此处写死了是5.4的版本，后续如果有ES升级，需要调整
        # 更新版本到7.2（2024-07-30）
        version="7.2",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0035_auto_20190924_1732"),
    ]

    operations = [migrations.RunPython(init_es_storage_info)]
