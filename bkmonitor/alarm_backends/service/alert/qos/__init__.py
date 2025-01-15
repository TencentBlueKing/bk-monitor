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
故障发布流程:
新增故障缓存，记录故障影响的模块和目标

failure_publish
"""


class FailureCollection:
    def __init__(
        self,
    ):
        self.collection = {}

    def add(self, tag, cls):
        if tag not in self.collection:
            self.collection[tag] = cls


FC = FailureCollection()


def register_influence(module):
    # 注册功能控制
    def register(cls):
        cls.module = module
        FC.add(module, cls)
        return cls

    return register


class IncidentInfluence:
    module = ""

    def __init__(self):
        self._cache = {}
