"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# 触发 DynamicCompositionPolicy 向 resolver 注册。放在 __init__ 里而不是让每个
# 调用方各自 import dynamic.py，避免"忘了 import → 注册表里没有 dynamic"的隐性 bug；
# 由于导入代价小、无外部依赖（selectors.django_setting 是延迟加载），这个提前 import 对启动无副作用。
from . import dynamic as _dynamic  # noqa: F401
from .resolver import register_policy_class, resolve_policy_class  # noqa: F401

# 确保 dynamic 已注册
register_policy_class("dynamic", _dynamic.DynamicCompositionPolicy)
