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
# IAM v4 资源回调 handler 注册（业务侧薄封装）
#
# 目录查询实现已收口到 adapters/catalog.py（资源目录），本模块只负责：
#   1. 通过装饰器把 handler 注册进全局回调注册表；
#   2. 把 CallbackService dispatch 的入参原样转发给 catalog。
#
# 契约（由 CallbackService 保证）：
#   handler 内部只处理业务 ID（未加 v4 方言前缀），所有 codec 编解码
#   由 CallbackService.dispatch_* 统一完成。
#   handler 出参每项的 "id" 填业务 ID；dispatch 层会 encode 回 v4 方言。
#   handler 入参（fetch 的 ids、list 的 filter.parent.id）已被 dispatch 层
#   decode 为业务 ID，可直接转发给 catalog。
#
# 注册：
#   本模块 import 时即通过装饰器完成 handler 注册，无需额外调用。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging

from ...iam_engine.callback.registry import register_fetch_instance_info, register_list_instance

from .. import catalog

logger = logging.getLogger(__name__)

# ================================================================
# space — 顶级资源
# ================================================================


@register_list_instance("space")
def _list_space(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("space", filter_data, page)


@register_fetch_instance_info("space")
def _fetch_space(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("space", ids, requires)


# ================================================================
# apm_application
# ================================================================


@register_list_instance("apm_application")
def _list_apm(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("apm_application", filter_data, page)


@register_fetch_instance_info("apm_application")
def _fetch_apm(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("apm_application", ids, requires)


# ================================================================
# grafana_dashboard
# ================================================================


@register_list_instance("grafana_dashboard")
def _list_grafana(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("grafana_dashboard", filter_data, page)


@register_fetch_instance_info("grafana_dashboard")
def _fetch_grafana(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("grafana_dashboard", ids, requires)


# ================================================================
# rum_application
# ================================================================


@register_list_instance("rum_application")
def _list_rum(filter_data: dict, page: dict) -> dict:
    return catalog.list_instances("rum_application", filter_data, page)


@register_fetch_instance_info("rum_application")
def _fetch_rum(ids: list[str], requires: list[str]) -> list[dict]:
    return catalog.fetch_instance_info("rum_application", ids, requires)
