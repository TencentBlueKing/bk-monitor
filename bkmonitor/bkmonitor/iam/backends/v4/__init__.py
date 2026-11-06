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
# iam_v4 — IAM v4 (RBAC) Provider 实现
#
# 依赖 iam_engine 框架，提供完整的 v4 鉴权接入：
#   - client.py      — IAM v4 APIGW HTTP 客户端
#   - provider.py    — V4PermissionProvider
#   - callback_client.py — 产品凭据适配；回调分发与 Token 在公共层
# 模型同步由 iam.model_sync 从产品模型派生期望值，调用 iam_engine.model 公共收敛服务。
# ---------------------------------------------------------------------------

#: Provider 标识 —— v4 包内唯一入口，所有引用 ``"v4"`` 的地方统一使用此常量。
PROVIDER_NAME: str = "v4"
