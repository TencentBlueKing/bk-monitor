"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import struct
import threading
from collections.abc import Mapping
from functools import lru_cache

from alarm_backends.core.alarmd.encoder import decode_json_document, encode_json_document

DEFAULT_DELIVERY_TIMEOUT_MS = 3000
PARTITION_HASH_VERSION = "trigger-input-partition-v1"
PRODUCER_SCOPE_TRIGGER_REFERENCE = "trigger_reference"


class KafkaPublishReceipt:
    """Track delivery callbacks for one stage on a process-shared producer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending_messages = 0
        self._acknowledged_records = 0
        self._delivery_errors = []
        self.enqueue_error = None

    def reserve(self, record_count: int):
        state = {"pending": True}
        with self._lock:
            self._pending_messages += 1

        def on_delivery(error, _message):
            with self._lock:
                if not state["pending"]:
                    return
                state["pending"] = False
                self._pending_messages -= 1
                if error is None:
                    self._acknowledged_records += record_count
                else:
                    self._delivery_errors.append(error)

        def cancel():
            with self._lock:
                if state["pending"]:
                    state["pending"] = False
                    self._pending_messages -= 1

        return on_delivery, cancel

    def fail_enqueue(self, error: Exception) -> None:
        with self._lock:
            if self.enqueue_error is None:
                self.enqueue_error = error

    @property
    def pending_messages(self) -> int:
        with self._lock:
            return self._pending_messages

    @property
    def acknowledged_records(self) -> int:
        with self._lock:
            return self._acknowledged_records

    @property
    def first_delivery_error(self):
        with self._lock:
            return self._delivery_errors[0] if self._delivery_errors else None


def _build_kafka_producer(producer_config: Mapping, *, producer_factory=None, producer_scope: str):
    if producer_factory is not None:
        return producer_factory(dict(producer_config))
    config_json = encode_json_document(dict(producer_config)).decode("utf-8")
    return _get_cached_default_kafka_producer(producer_scope, config_json)


@lru_cache(maxsize=8)
def _get_cached_default_kafka_producer(_producer_scope: str, config_json: str):
    from confluent_kafka import Producer

    return Producer(decode_json_document(config_json))


def trigger_partition_key(document: Mapping) -> bytes:
    ref = document["strategy_ref"]
    fields = (
        PARTITION_HASH_VERSION,
        document["tenant_id"],
        document["purpose"],
        ref["strategy_id"],
        ref["item_id"],
    )
    payload = bytearray()
    for field in fields:
        encoded = field.encode("utf-8")
        payload.extend(struct.pack(">I", len(encoded)))
        payload.extend(encoded)
    return hashlib.sha256(payload).digest()
