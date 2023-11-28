"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

# use cache to avoid read file every time
# make unittest faster
_CACHE = {}


def read_profile(name: str = "simple", category: str = "") -> dict:
    """read trace case by name"""
    if (name, category) in _CACHE:
        return _CACHE[(name, category)]

    cases_prefix = "packages/apm_web/tests/profile/cases"
    if category:
        cases_prefix += f"/{category}"

    with open(f"{cases_prefix}/{name}.json", "r") as f:
        trace_list = json.loads(f.read())

    _CACHE[(name, category)] = trace_list
    return trace_list
