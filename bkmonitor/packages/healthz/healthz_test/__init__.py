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
"""
为 cc, bk_data, job 提供测试用例
"""


import os

import yaml
from django.conf import settings

# 需要测试的组件
component_to_test = ["job", "cc", "bk_data", "nodeman", "gse", "metadata"]


def load_yaml_by_name_and_env(name):
    """
    通过当前的组件名称和环境，填充对应的全局测试用例配置
    :param name: 组件名称
    """
    filename = "{name}.yml".format(name=name)
    test_cases_name = "{name}_test_cases".format(name=name)
    try:
        with open(os.path.join(settings.BASE_DIR, "packages", "healthz", "healthz_test", filename)) as f:
            # 将当前填充的数据填充到global中
            globals()[test_cases_name] = yaml.safe_load(f)
    except (OSError, ValueError):
        globals()[test_cases_name] = {}


# 遍历组件，填充数据
for component in component_to_test:
    load_yaml_by_name_and_env(component)
