"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest

from alarm_backends.core.cache import strategy as module
from alarm_backends.core.cache.strategy import StrategyCacheManager as Manager


def strategy(strategy_id=1, biz=2, group="new", sdk=False, nodata=False):
    return {
        "id": strategy_id,
        "bk_biz_id": biz,
        "is_enabled": True,
        "items": [
            {
                "id": strategy_id * 10,
                "query_md5": group,
                "no_data_config": {"is_enabled": nodata},
                "query_configs": [
                    {
                        "agg_interval": 60,
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "intelligent_detect": {"use_sdk": sdk},
                    }
                ],
            }
        ],
    }


class Histories(list):
    def exists(self):
        return bool(self)

    def values(self, *fields):
        return [{field: getattr(row, field) for field in fields} for row in self]


@pytest.fixture
def state(monkeypatch):
    cache = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer(), decode_responses=True)
    cache.flushall()
    cache.set(Manager.BK_BIZ_IDS_CACHE_KEY, "[2, 3]")
    monkeypatch.setattr(Manager, "cache", cache)
    for name in ("add_source_identity", "add_target_shield_condition", "add_enabled_cluster_condition"):
        monkeypatch.setattr(Manager, name, Mock())
    monkeypatch.setattr(module.BusinessManager, "keys", lambda: [2, 3])
    monkeypatch.setattr(module.metrics, "report_all", Mock())
    monkeypatch.setattr(module, "sync_aiops_strategy_signal", Mock())
    current = strategy()
    histories = Histories(
        [SimpleNamespace(operate="update", strategy_id=1, content=current, create_time=datetime.fromtimestamp(990))]
    )
    history_filter = Mock(return_value=histories)
    monkeypatch.setattr(module.StrategyHistoryModel.objects, "filter", history_filter)
    model_filter = Mock()
    model_filter.return_value.values_list.return_value = [1]
    monkeypatch.setattr(module.StrategyModel.objects, "filter", model_filter)
    get_strategies = Mock(return_value=[current])
    monkeypatch.setattr(Manager, "get_strategies", get_strategies)
    clock = [1000]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    cache.set(Manager.LAST_UPDATED_CACHE_KEY, 900)
    return SimpleNamespace(
        cache=cache,
        current=current,
        histories=histories,
        history_filter=history_filter,
        model_filter=model_filter,
        get_strategies=get_strategies,
        clock=clock,
    )


def put_group(state, name, ids, biz=2):
    group = {str(sid): [sid * 10] for sid in ids}
    group.update(bk_biz_id=biz, interval_list=[60])
    state.cache.hset(Manager.STRATEGY_GROUP_CACHE_KEY, name, json.dumps(group))


def test_sdk_index_uses_any_item_and_preserves_other_business(state):
    state.current["items"].append(strategy(sdk=True)["items"][0])
    state.get_strategies.return_value += [strategy(2, nodata=True), strategy(3, sdk=False)]
    state.cache.set(Manager.AIOPS_SDK_CACHE_KEY, json.dumps([3, 99]))
    Manager.smart_refresh()
    assert set(Manager.get_aiops_sdk_strategy_ids()) == {1, 99}
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 1000


@pytest.mark.parametrize("failure", ["read", "publish", "signal"])
def test_failed_refresh_keeps_success_cursor(state, monkeypatch, failure):
    if failure == "read":
        state.get_strategies.side_effect = RuntimeError("read failed")
    elif failure == "publish":
        monkeypatch.setattr(Manager, "refresh_strategy", Mock(side_effect=RuntimeError("publish failed")))
    else:
        state.current["items"][0]["query_configs"][0]["intelligent_detect"]["use_sdk"] = True
        module.sync_aiops_strategy_signal.side_effect = RuntimeError("signal failed")
    try:
        Manager.smart_refresh()
    except RuntimeError:
        pass
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 900


def test_first_failure_keeps_fixed_replay_window(state):
    state.cache.delete(Manager.LAST_UPDATED_CACHE_KEY)
    state.get_strategies.side_effect = RuntimeError("read failed")
    Manager.smart_refresh()
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 700
    first_lower_bound = state.history_filter.call_args.kwargs["create_time__gt"]
    state.clock[0] += 600
    Manager.smart_refresh()
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 700
    second_lower_bound = state.history_filter.call_args.kwargs["create_time__gt"]
    assert second_lower_bound == first_lower_bound


def test_read_failure_does_not_delete_details_or_groups(state):
    put_group(state, "old", [1])
    key = Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1)
    state.cache.set(key, json.dumps(state.current))
    state.histories[0].content["is_enabled"] = False
    state.model_filter.return_value.values_list.return_value = []
    state.get_strategies.side_effect = RuntimeError("read failed")
    Manager.smart_refresh()
    assert state.cache.exists(key)
    assert state.cache.hexists(Manager.STRATEGY_GROUP_CACHE_KEY, "old")


def test_query_change_cleans_old_group_even_after_detail_was_overwritten(state):
    state.cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1), json.dumps(state.current))
    put_group(state, "old", [1])
    put_group(state, "other-business", [99], biz=3)
    Manager.smart_refresh()
    assert state.cache.hlen(Manager.STRATEGY_GROUP_CACHE_KEY) == 2
    assert state.cache.hexists(Manager.STRATEGY_GROUP_CACHE_KEY, "new")
    assert state.cache.hexists(Manager.STRATEGY_GROUP_CACHE_KEY, "other-business")


def test_shared_group_rebuilt_with_surviving_member(state):
    put_group(state, "old", [1, 2])
    state.get_strategies.return_value.append(strategy(2, group="old"))
    Manager.smart_refresh()
    old = json.loads(state.cache.hget(Manager.STRATEGY_GROUP_CACHE_KEY, "old"))
    assert "1" not in old
    assert old["2"] == [20]


@pytest.mark.parametrize("members", [[7], [1, 7]])
def test_group_with_unbuilt_enabled_strategy_is_preserved(state, members):
    put_group(state, "old", members)
    Manager.smart_refresh()
    old = json.loads(state.cache.hget(Manager.STRATEGY_GROUP_CACHE_KEY, "old"))
    assert "7" in old


def test_delete_with_missing_detail_recovers_business_from_group(state):
    state.histories[0].operate = "delete"
    state.histories[0].content = {}
    state.model_filter.return_value.values_list.return_value = []
    state.get_strategies.return_value = []
    state.cache.set(Manager.IDS_CACHE_KEY, "[1]")
    put_group(state, "old", [1])
    Manager.smart_refresh()
    state.get_strategies.assert_called_once_with({2})
    assert Manager.get_strategy_ids() == []
    assert not state.cache.hexists(Manager.STRATEGY_GROUP_CACHE_KEY, "old")


def test_delete_without_any_cached_business_does_not_query_all_strategies(state):
    state.histories[0].operate = "delete"
    state.histories[0].content = {}
    state.model_filter.return_value.values_list.return_value = []
    state.cache.set(Manager.IDS_CACHE_KEY, "[1]")
    Manager.smart_refresh()
    state.get_strategies.assert_not_called()
    assert Manager.get_strategy_ids() == []


def test_delete_retry_recovers_shared_group_after_detail_was_removed(state, monkeypatch):
    state.histories[0].operate = "delete"
    state.histories[0].content = {}
    state.model_filter.return_value.values_list.return_value = [2]
    state.get_strategies.return_value = [strategy(2, group="old")]
    state.cache.set(Manager.IDS_CACHE_KEY, "[1, 2]")
    deleted_key = Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1)
    state.cache.set(deleted_key, json.dumps(strategy(1, group="old")))
    put_group(state, "old", [1, 2])
    with monkeypatch.context() as patch:
        patch.setattr(Manager, "get_query_md5", Mock(return_value="old"))
        patch.setattr(Manager, "refresh_strategy", Mock(side_effect=RuntimeError("publication failed")))
        Manager.smart_refresh()

    assert not state.cache.exists(deleted_key)
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 900
    assert "1" in json.loads(state.cache.hget(Manager.STRATEGY_GROUP_CACHE_KEY, "old"))

    state.get_strategies.reset_mock()
    state.clock[0] = 1060
    Manager.smart_refresh()

    state.get_strategies.assert_called_once_with({2})
    group = json.loads(state.cache.hget(Manager.STRATEGY_GROUP_CACHE_KEY, "old"))
    assert "1" not in group
    assert group["2"] == [20]
    assert Manager.get_strategy_ids() == [2]
    assert int(state.cache.get(Manager.LAST_UPDATED_CACHE_KEY)) == 1060


def test_stale_disable_does_not_remove_reenabled_strategy(state):
    state.current["items"][0]["query_configs"][0]["intelligent_detect"]["use_sdk"] = True
    state.cache.set(Manager.AIOPS_SDK_CACHE_KEY, "[1]")
    state.histories[0].content = {**state.current, "is_enabled": False}
    state.cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1), json.dumps(state.current))
    _, deleted = Manager.handle_history_strategies(state.histories)
    assert not deleted
    Manager.smart_refresh()
    assert Manager.get_strategy_by_id(1)["is_enabled"] is True
    assert Manager.get_aiops_sdk_strategy_ids() == [1]


def test_full_ids_remove_deleted_and_disabled_but_keep_enabled_missing_build(state):
    state.cache.set(Manager.IDS_CACHE_KEY, "[1, 2, 3, 4]")
    for sid in (1, 2, 3, 4):
        state.cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid), json.dumps(strategy(sid)))
    state.model_filter.return_value.values_list.return_value = [4]
    Manager.refresh_strategy_ids([state.current])
    state.model_filter.assert_called_once_with(id__in={2, 3, 4}, is_enabled=True)
    assert set(Manager.get_strategy_ids()) == {1, 4}
    assert not Manager.get_strategy_by_id(2)
    assert not Manager.get_strategy_by_id(3)
    assert Manager.get_strategy_by_id(4)


def test_full_ids_database_failure_does_not_publish_or_delete(state):
    state.cache.set(Manager.IDS_CACHE_KEY, "[1, 2]")
    key = Manager.CACHE_KEY_TEMPLATE.format(strategy_id=2)
    state.cache.set(key, json.dumps(strategy(2)))
    state.model_filter.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        Manager.refresh_strategy_ids([state.current])
    assert json.loads(state.cache.get(Manager.IDS_CACHE_KEY)) == [1, 2]
    assert state.cache.exists(key)


@pytest.mark.parametrize("deleted", [None, [6]])
def test_batch_detail_read_preserves_missing_null_and_key_identity(state, deleted):
    state.cache.set(Manager.IDS_CACHE_KEY, json.dumps(list(range(1, 9))))
    details = {
        2: json.dumps({"id": 2, "bk_biz_id": 9}),
        4: "null",
        5: "{}",
        6: json.dumps({"id": 6, "bk_biz_id": 2}),
        7: json.dumps({"id": 99, "bk_biz_id": 9}),
        8: "",
    }
    for sid, raw in details.items():
        state.cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid), raw)
    state.model_filter.return_value.values_list.return_value = [3, 4, 5, 8]
    Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=deleted)
    assert set(Manager.get_strategy_ids()) == {1, 3, 4, 5, 8}
    for sid in [2, 6, 7]:
        assert not state.cache.exists(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid))
    for sid in [4, 5, 8]:
        assert state.cache.exists(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid))


def test_missing_details_use_bounded_mget_without_individual_get(state, monkeypatch):
    old_ids = set(range(1, 1003))
    state.cache.set(Manager.IDS_CACHE_KEY, json.dumps(list(old_ids)))
    for sid in old_ids:
        state.cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid), json.dumps({"id": sid, "bk_biz_id": 2}))
    mget = Mock(wraps=state.cache.mget)
    get = Mock(wraps=state.cache.get)
    monkeypatch.setattr(state.cache, "mget", mget)
    monkeypatch.setattr(state.cache, "get", get)
    Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=[])
    assert [len(call.args[0]) for call in mget.call_args_list] == [1000, 1]
    expected_keys = {Manager.CACHE_KEY_TEMPLATE.format(strategy_id=sid) for sid in old_ids - {1}}
    assert {key for call in mget.call_args_list for key in call.args[0]} == expected_keys
    assert all(call.args[0] not in expected_keys for call in get.call_args_list)
    assert set(Manager.get_strategy_ids()) == old_ids


def test_empty_missing_set_does_not_read_details(state, monkeypatch):
    state.cache.set(Manager.IDS_CACHE_KEY, "[1]")
    mget = Mock(wraps=state.cache.mget)
    monkeypatch.setattr(state.cache, "mget", mget)
    Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=[])
    mget.assert_not_called()
    assert Manager.get_strategy_ids() == [1]


def test_non_string_detail_uses_mget_missing_value_semantics(state):
    state.cache.set(Manager.IDS_CACHE_KEY, "[1, 2]")
    detail_key = Manager.CACHE_KEY_TEMPLATE.format(strategy_id=2)
    state.cache.hset(detail_key, mapping={"unexpected": "hash"})
    Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=[])
    assert set(Manager.get_strategy_ids()) == {1, 2}
    assert state.cache.type(detail_key) in ("hash", b"hash")


@pytest.mark.parametrize("failure_batch", [1, 2])
def test_mget_failure_keeps_ids_and_details_unchanged(state, monkeypatch, failure_batch):
    state.cache.set(Manager.IDS_CACHE_KEY, json.dumps(list(range(1, 1003))))
    real_mget = state.cache.mget
    calls = []

    def read(keys):
        calls.append(keys)
        if len(calls) == failure_batch:
            raise RuntimeError("read failed")
        return real_mget(keys)

    monkeypatch.setattr(state.cache, "mget", read)
    publish = Mock(wraps=state.cache.set)
    delete = Mock(wraps=state.cache.delete)
    monkeypatch.setattr(state.cache, "set", publish)
    monkeypatch.setattr(state.cache, "delete", delete)
    with pytest.raises(RuntimeError, match="read failed"):
        Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=[2])
    publish.assert_not_called()
    delete.assert_not_called()
    assert len(calls) == failure_batch


@pytest.mark.parametrize("raw, exception", [("invalid", json.JSONDecodeError), ('{"id": 2}', KeyError)])
def test_invalid_cached_detail_keeps_ids_and_details_unchanged(state, monkeypatch, raw, exception):
    state.cache.set(Manager.IDS_CACHE_KEY, "[1, 2]")
    detail_key = Manager.CACHE_KEY_TEMPLATE.format(strategy_id=2)
    state.cache.set(detail_key, raw)
    publish = Mock(wraps=state.cache.set)
    delete = Mock(wraps=state.cache.delete)
    monkeypatch.setattr(state.cache, "set", publish)
    monkeypatch.setattr(state.cache, "delete", delete)
    with pytest.raises(exception):
        Manager.refresh_strategy_ids([state.current], to_be_deleted_strategy_ids=[])
    publish.assert_not_called()
    delete.assert_not_called()
    assert Manager.get_strategy_ids() == [1, 2]
    assert state.cache.get(detail_key) in (raw, raw.encode())
