"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger("fta_action.run")

EVENT_CONTEXT_KEY = "${_event_context}"
POSITIVE_ID = re.compile(r"[1-9][0-9]{0,23}")


def _positive_id(value):
    if type(value) is int and 0 < value < 10**24:
        value = str(value)
    return value if isinstance(value, str) and POSITIVE_ID.fullmatch(value) else None


def attach_action_group_reference(inputs, action, action_context):
    """Attach the action group reference while preserving the existing callback representation."""
    constants = inputs.get("constants")
    if action_context is None or not isinstance(constants, dict) or "scope_value" in inputs:
        return

    raw_context = constants.get(EVENT_CONTEXT_KEY)
    try:
        context = json.loads(raw_context) if isinstance(raw_context, str) else raw_context
    except (ValueError, RecursionError):
        return
    if not isinstance(context, dict):
        return

    event, strategy = context.get("event"), context.get("strategy")
    if not isinstance(event, dict) or not isinstance(strategy, dict):
        return

    biz_id = _positive_id(action.bk_biz_id)
    strategy_id = _positive_id(action.strategy_id)
    alert_id = _positive_id(event.get("event_id"))
    action_id = _positive_id(action.id)
    if (
        not (biz_id and strategy_id and alert_id and action_id)
        or _positive_id(inputs.get("bk_biz_id")) != biz_id
        or _positive_id(context.get("bk_biz_id")) != biz_id
        or _positive_id(strategy.get("id")) != strategy_id
        or not isinstance(action.alerts, list)
        or alert_id not in map(_positive_id, action.alerts)
        or not isinstance(action.create_time, datetime)
    ):
        return

    try:
        created_ts = int(action.create_time.timestamp())
        if not 1_000_000_000 <= created_ts < 10_000_000_000:
            return
        converge_config = action.get_strategy_converge_config()
        if not converge_config or not converge_config.get("is_enabled"):
            return
        group_id = _positive_id(action_context.action_instance.converge_id)
        if not group_id:
            return
        context = {
            **context,
            "monitor_action_group_ref": {
                "schema_version": 1,
                "action_created_ts": created_ts,
                "action_id": action_id,
                "group_id": group_id,
                "alert_id": alert_id,
            },
        }
        inputs["constants"] = {
            **constants,
            EVENT_CONTEXT_KEY: json.dumps(context) if isinstance(raw_context, str) else context,
        }
    except Exception as error:  # noqa: BLE001
        # The reference is optional. A lookup failure must not prevent dispatch.
        logger.warning("Action %s could not attach its convergence reference (%s)", action_id, type(error).__name__)
