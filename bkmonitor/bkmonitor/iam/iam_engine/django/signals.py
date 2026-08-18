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
# Django signals — 供 semi_auto 迁移模式使用
#
# semi_auto: Django post_migrate 信号触发；破坏性变更由 MIGRATION.allow_destructive
# 显式控制（与 CLI 的 --allow-destructive 语义完全对齐），默认 False 时 DELETE 会被 skip。
# 此模块为将来扩展预留；当前实现走 apps.py 内联。
# ---------------------------------------------------------------------------
