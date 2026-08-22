"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# iam_engine —— 通用 IAM 鉴权框架
#
# 分层：
#   core/         平台无关的数据类型、异常、上下文、能力常量、通用工具
#   schema/       Action/ResourceType/Role/System 的定义、注册表、diff/plan
#   policy/       PolicyExpression AST 及其 Evaluator/Translator
#   provider/     PermissionProvider 抽象、组合策略、Router、装饰器
#   crosscutting/ 横切能力（Bypass 钩子等）
#   builtin/      内置 Provider 实现（v3 / v4）
#   django/       Django 集成层（AppConfig / settings / DRF / management commands）
#
# 模块边界：
#   - core / schema / policy / provider / crosscutting  严禁 import django、v3/v4 SDK
#   - builtin/v4 内可 import v4 SDK/HTTP；builtin/v3 内可 import iam(v3 SDK)
#   - django/ 是唯一可以 import django 的层
# ---------------------------------------------------------------------------

__version__ = "0.1.0"
