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
# iam_v3 — IAM v3 (ABAC) Provider 实现
#
# 依赖 iam_engine 框架，将 V3Client SDK 客户端封装为新框架的 Provider：
#   - config.py      — Provider 配置契约（V3Options / V3Credentials / V3SystemInfo）
#   - provider.py    — V3PermissionProvider
#   codec 在 adapters/v3/codec.py —— V3NameCodec（业务 action_id ↔ V3 平台 action_id 映射）
#
# Phase 1 范围：鉴权（is_allowed / batch_* / get_apply_url）、
# 最小 migration 支持（空实现）、health_check。
# ---------------------------------------------------------------------------

#: Provider 标识 —— v3 包内唯一入口，所有引用 ``"v3"`` 的地方统一使用此常量。
PROVIDER_NAME: str = "v3"
