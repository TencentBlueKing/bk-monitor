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
import os

import yaml

K8S_METRICS = []
K8S_EVENTS = []


def get_built_in_k8s_metrics():
    # 增加全局变量缓存
    global K8S_METRICS
    if K8S_METRICS:
        return K8S_METRICS
    metrics = []
    # 获取metadata/data/k8s_metrics配置目录下的容器内置指标
    BASE_DIR = os.path.abspath(os.getcwd())
    g = os.walk(os.path.join(BASE_DIR, "metadata/data/k8s_metrics"))
    for path, _, file_list in g:
        file_list = [file for file in file_list if file.split(".")[-1] == "yaml"]
        for file_name in file_list:
            with open(os.path.join(path, file_name), "r") as f:
                metrics.extend(yaml.safe_load(f.read()))
    K8S_METRICS = metrics
    return metrics


# TODO: 先和内置指标放一块，后面再拆分
def get_built_in_k8s_events():
    """获取内置的 k8s 事件"""
    global K8S_EVENTS
    if K8S_EVENTS:
        return K8S_EVENTS
    # 读取文件中的内容
    events = []
    BASE_DIR = os.path.abspath(os.getcwd())
    file_name = os.path.join(BASE_DIR, "metadata/data/k8s_events.json")
    with open(file_name, "r") as f:
        events.extend(json.loads(f.read()))

    # 返回数据
    K8S_EVENTS = events
    return events
