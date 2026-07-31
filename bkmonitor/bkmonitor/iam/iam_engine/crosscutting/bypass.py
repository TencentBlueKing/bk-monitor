"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# BypassRule —— 鉴权豁免规则
#
# ProviderRouter 在调用 CompositionPolicy 之前先跑所有 BypassRule；
# 任一规则命中（should_bypass 返回 True）则直接放行，不走任何 Provider。
#
# 典型场景：
#   - 开发/调试环境全量跳过鉴权
#   - 超级管理员账号豁免
#   - 特定 API Token 的临时分享请求
#   - 特定 tenant / action 的阶段性豁免
#
# 扩展：
#   使用方继承 BypassRule 实现自定义豁免逻辑，注册到 ProviderRouter 即可。
#   BypassRule 只依赖 core.types.AuthRequest，不依赖 Django 或任何 Provider。
# ---------------------------------------------------------------------------

from abc import ABC, abstractmethod

from bkmonitor.iam.iam_engine.core.types import AuthRequest


class BypassRule(ABC):
    """鉴权豁免规则抽象。

    决定某次鉴权请求是否应绕过权限检查直接放行。
    返回 True 表示该请求被豁免，直接放行不经过 Provider。

    子类必须实现 should_bypass。
    """

    @abstractmethod
    def should_bypass(self, request: AuthRequest) -> bool:
        """判断是否豁免该请求。返回 True 直接放行。"""
        ...


# ---------------------------------------------------------------------------
# 内置豁免规则
# ---------------------------------------------------------------------------


class SettingsSkipRule(BypassRule):
    """开发/调试环境全量跳过鉴权。

    检查 ``django.conf.settings.SKIP_IAM_PERMISSION_CHECK``；
    该值为 True 时所有鉴权请求直接放行。

    仅开发环境使用，生产环境禁止开启。
    Django import 延迟到 should_bypass 内部，模块导入时不强依赖 Django。
    """

    def should_bypass(self, request: AuthRequest) -> bool:  # noqa: ARG002
        from django.conf import settings

        return bool(getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False))


class SubjectBypassRule(BypassRule):
    """特定主体豁免鉴权。

    用法::

        SubjectBypassRule(subject_ids={"admin", "monitor_bot"})

    options:
        subject_ids: set[str] —— 豁免的主体 ID 集合
    """

    def __init__(self, subject_ids: set[str] | None = None) -> None:
        self._subject_ids: frozenset[str] = frozenset(subject_ids or set())

    def should_bypass(self, request: AuthRequest) -> bool:
        return request.subject.id in self._subject_ids
