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

import collections.abc
from typing import Dict


def nested_update(d, u, overwrite=False):
    """
    字典嵌套更新
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = nested_update(d.get(k, {}), v, overwrite)
        else:
            if overwrite or k not in d:
                d[k] = v
    return d


def nested_diff(d: Dict, s: Dict) -> Dict:
    """
    字典差异提取
    """
    diff = {}

    for k, v in d.items():
        sv = s.get(k)
        if isinstance(v, dict):
            if not isinstance(v, dict):
                diff[k] = v
            else:
                sub_diff = nested_diff(v, sv)
                if sub_diff:
                    diff[k] = v
        elif v != sv:
            diff[k] = v

    return diff
