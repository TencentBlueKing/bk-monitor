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
# iam_engine.callback — IAM 资源回调基础设施
#
# 提供与 IAM 版本无关的通用回调机制：
#   registry.py — 全局 handler 注册表 + register_* 装饰器
#   service.py  — CallbackService（codec 感知的 dispatch 层）
#
# 各 Provider 版本（v3/v4/...）各自实现 HTTP 协议层（View + Auth），
# 共用本模块的注册表 + CallbackService。
# ---------------------------------------------------------------------------
