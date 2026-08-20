"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import pytest

from alarm_backends.service.preparation.aiops import processor as processor_module
from alarm_backends.service.preparation.aiops.processor import TsDependPreparationProcess
from constants.aiops import SDKDetectStatus


def make_strategy(query_record):
    item = SimpleNamespace(query_configs=[{}], query_record=query_record)
    return SimpleNamespace(id=1001, bk_tenant_id="default", items=[item])


def make_record():
    return {"_time_": 1, "_result_": 10, "bk_target_ip": "127.0.0.1"}


def test_init_api_failure_is_propagated_from_batch_worker():
    process = TsDependPreparationProcess()
    strategy = make_strategy(lambda _start, _end: [make_record()])

    def failing_init_api(**_kwargs):
        raise RuntimeError("init api failed")

    with pytest.raises(RuntimeError, match="init api failed"):
        process.init_depend_data_by_records(
            strategy=strategy,
            init_depend_api_func=failing_init_api,
            strategy_records=[make_record()],
            processed_dimensions=set(),
        )


def test_batch_worker_failure_is_propagated_from_time_range_worker(monkeypatch):
    process = TsDependPreparationProcess()
    strategy = make_strategy(lambda _start, _end: [make_record()])
    monkeypatch.setattr(processor_module, "check_lock_updated", lambda *_args, **_kwargs: False)

    def failing_batch_worker(**_kwargs):
        raise RuntimeError("batch worker failed")

    monkeypatch.setattr(process, "init_depend_data_by_records", failing_batch_worker)

    with pytest.raises(RuntimeError, match="batch worker failed"):
        process.init_depend_data(
            strategy=strategy,
            init_depend_api_func=lambda **_kwargs: None,
            start_time=0,
            end_time=60,
            processed_dimensions=set(),
        )


def test_prefetch_failure_is_propagated_from_time_range_worker(monkeypatch):
    process = TsDependPreparationProcess()
    strategy = make_strategy(lambda _start, _end: [make_record()])
    monkeypatch.setattr(processor_module, "check_lock_updated", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(process, "init_depend_data_by_records", lambda **_kwargs: None)

    def failing_prefetch(**_kwargs):
        raise RuntimeError("prefetch failed")

    monkeypatch.setattr(process, "prefetch_item_records", failing_prefetch)

    with pytest.raises(RuntimeError, match="prefetch failed"):
        process.init_depend_data(
            strategy=strategy,
            init_depend_api_func=lambda **_kwargs: None,
            start_time=0,
            end_time=600,
            processed_dimensions=set(),
        )


def test_failed_initialization_does_not_mark_strategy_ready(monkeypatch):
    intelligent_detect = {"use_sdk": True, "status": SDKDetectStatus.PREPARING}
    strategy = SimpleNamespace(config={"items": [{"query_configs": [{"intelligent_detect": intelligent_detect}]}]})

    @contextmanager
    def fake_service_lock(*_args, **_kwargs):
        yield

    monkeypatch.setattr(processor_module, "Strategy", lambda _strategy_id: strategy)
    monkeypatch.setattr(processor_module, "refresh_service_lock", fake_service_lock)
    update_query_config = mock.Mock()
    monkeypatch.setattr(processor_module, "update_strategy_query_config", update_query_config)

    process = TsDependPreparationProcess()
    process.refresh_strategy_depend_data = mock.Mock(side_effect=RuntimeError("initialization failed"))

    with pytest.raises(RuntimeError, match="initialization failed"):
        process.process(strategy_id=1001)

    assert intelligent_detect["status"] == SDKDetectStatus.PREPARING
    update_query_config.assert_not_called()
