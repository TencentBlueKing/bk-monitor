"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
from threading import Lock

from iam_engine.model.client import V4ModelClient

# Only protects entry creation. Network calls use separate locks per query.
_request_cache_lock = Lock()


class V4Client(V4ModelClient):
    """Reuse validated read decisions within one Monitor HTTP request."""

    def __init__(self, options, *, request_getter=None, read_action_ids=(), **kwargs):
        super().__init__(options, **kwargs)
        self._request_getter = request_getter
        self._read_action_ids = frozenset(read_action_ids)

    def _read_once(self, method, query, parameters):
        request = self._request_getter() if self._request_getter else None
        if request is None or parameters["action_id"] not in self._read_action_ids:
            return query(**parameters)

        parameters = copy.deepcopy(parameters)
        # Factory clients may differ across Permission instances in one request.
        # Include their complete immutable options and gateway identity instead.
        key = (self.options, self.username, self.bk_tenant_id, method, json.dumps(parameters, sort_keys=True))
        with _request_cache_lock:
            cache = getattr(request, "_iam_v4_read_cache", None)
            if cache is None:
                cache = {}
                request._iam_v4_read_cache = cache
            if key not in cache:
                cache[key] = (Lock(), [])
            lock, values = cache[key]

        with lock:
            if not values:
                # Cache only after the client validates the complete response.
                # False and empty scope are valid; exceptions remain retryable.
                values.append(copy.deepcopy(query(**parameters)))
            return copy.deepcopy(values[0])

    def direct_auth(self, *, subject, action_id, resource=None):
        return self._read_once(
            "direct_auth",
            super().direct_auth,
            {"subject": subject, "action_id": action_id, "resource": resource},
        )

    def direct_auth_by_resources(self, *, subject, action_id, resources):
        return self._read_once(
            "direct_auth_by_resources",
            super().direct_auth_by_resources,
            {"subject": subject, "action_id": action_id, "resources": resources},
        )

    def list_authorized_resource(self, *, subject, action_id, resource_type="space"):
        return self._read_once(
            "list_authorized_resource",
            super().list_authorized_resource,
            {"subject": subject, "action_id": action_id, "resource_type": resource_type},
        )


__all__ = ["V4Client"]
