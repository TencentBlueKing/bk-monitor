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
# IAM v4 资源回调模块
#
# auth.py  — IAM v4 Basic Auth 认证
# views.py — IAMV4ResourceCallbackView（v4 回调端点）
#
# 通用基础设施在 iam_engine/callback/：
#   registry.py — 全局 handler 注册表 + register_* 装饰器
#   service.py  — CallbackService（codec 感知分发）
#
# 业务 handler 实现位于 iam/adapters/v4/callbacks.py，
# 由 V4PermissionProvider 在初始化时通过 callback_module 配置自动导入。
# 业务在 URLconf 中自行挂载 IAMV4ResourceCallbackView。
# ---------------------------------------------------------------------------
