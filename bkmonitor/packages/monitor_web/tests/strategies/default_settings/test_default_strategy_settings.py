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

from monitor_web.strategies.default_settings import default_strategy_settings
from monitor_web.strategies.default_settings.k8s.v1 import DEFAULT_K8S_STRATEGIES as DEFAULT_K8S_STRATEGIES_V1
from monitor_web.strategies.default_settings.k8s.v2 import DEFAULT_K8S_STRATEGIES as DEFAULT_K8S_STRATEGIES_V2


def test_get_k8s_strategies():
    strategies_list = default_strategy_settings.DEFAULT_K8S_STRATEGIES_LIST
    assert strategies_list[0]["version"] == "v1"
    module = strategies_list[0]["module"]
    assert module.DEFAULT_K8S_STRATEGIES == DEFAULT_K8S_STRATEGIES_V1

    assert strategies_list[1]["version"] == "v2"
    module = strategies_list[1]["module"]
    assert module.DEFAULT_K8S_STRATEGIES == DEFAULT_K8S_STRATEGIES_V2
