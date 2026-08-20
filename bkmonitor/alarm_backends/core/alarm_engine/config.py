"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable, Mapping

from alarm_backends.core.alarm_engine.contract import ContractValidationError
from alarm_backends.core.alarm_engine.encoder import decode_json_document


def shadow_flag(value) -> bool:
    """Resolve one Shadow switch fail-closed.

    Deployments inject settings through the environment, where every value is a
    string. A plain truthiness check would let "false" open the bypass, so only a
    real boolean or the exact literal "true" enables it.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def shadow_kafka_config(value) -> dict:
    """Resolve a Shadow producer config that may arrive as a JSON document string."""

    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        payload = value.strip()
        if not payload:
            return {}
        try:
            return decode_json_document(payload)
        except ContractValidationError:
            return {}
    return {}


def shadow_topics(value) -> tuple[str, ...]:
    """Resolve a Shadow topic allowlist that may arrive as a comma-separated string.

    Any non-string member makes the whole allowlist empty, because a partially
    understood allowlist must not be treated as an isolation boundary.
    """

    if isinstance(value, str):
        candidates: Iterable = value.split(",")
    elif isinstance(value, Iterable):
        candidates = value
    else:
        return ()
    topics = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            return ()
        topic = candidate.strip()
        if topic:
            topics.add(topic)
    return tuple(sorted(topics))
