# -*- coding: utf-8 -*-  # noqa: UP009
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import connections

from alarm_backends.core.cache.strategy import StrategyCacheManager
from bkmonitor.db_routers import UsingDB
from bkmonitor.models import AlgorithmModel
from bkmonitor.models import DetectModel
from bkmonitor.models import ItemModel
from bkmonitor.models import QueryConfigModel
from bkmonitor.models import StrategyActionConfigRelation
from bkmonitor.models import StrategyHistoryModel
from bkmonitor.models import StrategyLabel
from bkmonitor.models import StrategyModel
from bkmonitor.models.issue import StrategyIssueConfig
from bkmonitor.strategy.new_strategy import Strategy
from monitor_web.strategies.resources.v2 import UpdatePartialStrategyV2Resource


def test_strategy_history_operate_choices_include_only_bulk_update():
    choices = dict(StrategyHistoryModel._meta.get_field("operate").choices)

    assert choices["bulk_update"] == "批量更新"
    assert "bulk_delete" not in choices


@pytest.mark.django_db
def test_bulk_delete_does_not_create_success_history_when_delete_fails():
    """中途删除失败时不应写入成功历史；事务保证与主表删除一并回滚。"""
    strategy_id = 1001

    def raise_delete_error():
        raise RuntimeError("delete relation failed")

    with (
        mock.patch.object(StrategyHistoryModel.objects, "bulk_create") as bulk_create_history,
        mock.patch.object(StrategyModel.objects, "filter") as strategy_filter,
        mock.patch.object(StrategyActionConfigRelation.objects, "filter") as relation_filter,
    ):
        relation_filter.return_value.delete.side_effect = raise_delete_error

        with pytest.raises(RuntimeError, match="delete relation failed"):
            Strategy.delete_by_strategy_ids([strategy_id])

    strategy_filter.return_value.delete.assert_called_once_with()
    bulk_create_history.assert_not_called()


@pytest.mark.django_db(databases=("default", "monitor_api"), transaction=True)
def test_bulk_delete_opens_transaction_on_monitor_api():
    """批量删除必须在实际承载策略模型写入的 monitor_api 库开启事务。"""
    transaction_state = {}

    def inspect_transaction():
        transaction_state.update(
            default=connections["default"].in_atomic_block,
            monitor_api=connections["monitor_api"].in_atomic_block,
        )
        raise RuntimeError("stop after inspecting transaction")

    with (
        mock.patch.object(StrategyModel.objects, "filter") as strategy_filter,
        mock.patch.object(Strategy, "_get_username", return_value="admin"),
    ):
        strategy_filter.return_value.delete.side_effect = inspect_transaction

        with pytest.raises(RuntimeError, match="stop after inspecting transaction"):
            Strategy.delete_by_strategy_ids([1001])

    assert transaction_state == {"default": False, "monitor_api": True}


@pytest.mark.django_db(databases=("default", "monitor_api"), transaction=True)
def test_bulk_delete_opens_transaction_on_runtime_routed_database():
    """动态路由覆盖时，事务必须与实际写入的数据库保持一致。"""
    transaction_state = {}

    def inspect_transaction():
        transaction_state.update(
            default=connections["default"].in_atomic_block,
            monitor_api=connections["monitor_api"].in_atomic_block,
        )
        raise RuntimeError("stop after inspecting transaction")

    with (
        mock.patch.object(StrategyModel.objects, "filter") as strategy_filter,
        mock.patch.object(Strategy, "_get_username", return_value="admin"),
    ):
        strategy_filter.return_value.delete.side_effect = inspect_transaction

        with pytest.raises(RuntimeError, match="stop after inspecting transaction"):
            with UsingDB("default"):
                Strategy.delete_by_strategy_ids([1001])

    assert transaction_state == {"default": True, "monitor_api": False}


@pytest.mark.django_db
def test_bulk_delete_creates_delete_histories_after_all_data_is_deleted():
    strategy_ids = [1001, 1002]
    delete_models = (
        StrategyModel,
        StrategyActionConfigRelation,
        DetectModel,
        ItemModel,
        AlgorithmModel,
        QueryConfigModel,
        StrategyLabel,
        StrategyIssueConfig,
    )
    operations = mock.Mock()

    with ExitStack() as stack:
        for index, model in enumerate(delete_models):
            model_filter = stack.enter_context(mock.patch.object(model.objects, "filter"))
            operations.attach_mock(model_filter.return_value.delete, f"delete_{index}")

        bulk_create_history = stack.enter_context(mock.patch.object(StrategyHistoryModel.objects, "bulk_create"))
        operations.attach_mock(bulk_create_history, "create_history")
        stack.enter_context(mock.patch.object(Strategy, "_get_username", return_value="admin"))

        Strategy.delete_by_strategy_ids(strategy_ids)

    histories = bulk_create_history.call_args.args[0]
    assert [(history.strategy_id, history.operate, history.status) for history in histories] == [
        (1001, "delete", True),
        (1002, "delete", True),
    ]
    assert operations.mock_calls[-1] == mock.call.create_history(histories, batch_size=100)


@pytest.mark.django_db
def test_bulk_update_creates_success_history_with_bulk_update_type():
    strategy_id = 1001
    strategy_queryset = mock.Mock()
    strategy = mock.Mock()
    strategy.id = strategy_id
    strategy.instance = mock.Mock()
    strategy.items = []
    strategy.to_dict.return_value = {"bk_biz_id": 2, "id": strategy_id, "is_enabled": False}

    with (
        mock.patch.object(StrategyModel.objects, "filter", return_value=strategy_queryset),
        mock.patch.object(StrategyModel.objects, "bulk_update"),
        mock.patch.object(StrategyHistoryModel.objects, "bulk_create") as bulk_create_history,
        mock.patch.object(Strategy, "from_models", return_value=[strategy]),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_relations", return_value=([], {})),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_action_configs", return_value={}),
        mock.patch("monitor_web.strategies.resources.v2.get_global_user", return_value="admin"),
    ):
        result = UpdatePartialStrategyV2Resource().perform_request(
            {"bk_biz_id": 2, "edit_data": {"is_enabled": False}, "ids": [strategy_id]}
        )

    histories = bulk_create_history.call_args.args[0]
    assert result == [strategy_id]
    assert len(histories) == 1
    assert histories[0].strategy_id == strategy_id
    assert histories[0].operate == "bulk_update"
    assert histories[0].status is True
    assert histories[0].content == {"bk_biz_id": 2, "id": strategy_id, "is_enabled": False}
    strategy_queryset.update.assert_called_once_with(hash="", snippet="")


@pytest.mark.django_db
def test_bulk_update_does_not_create_success_history_when_update_fails():
    """中途 bulk_update 失败时不应写入成功历史；事务保证与配置更新一并回滚。"""
    strategy_id = 1001
    strategy_queryset = mock.Mock()

    def raise_update_error(*_args, **_kwargs):
        raise RuntimeError("bulk update failed")

    with (
        mock.patch.object(StrategyModel.objects, "filter", return_value=strategy_queryset),
        mock.patch.object(StrategyModel.objects, "bulk_update", side_effect=raise_update_error),
        mock.patch.object(StrategyHistoryModel.objects, "bulk_create") as bulk_create_history,
        mock.patch.object(Strategy, "from_models", return_value=[]),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_relations", return_value=([], {})),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_action_configs", return_value={}),
        mock.patch("monitor_web.strategies.resources.v2.get_global_user", return_value="admin"),
    ):
        with pytest.raises(RuntimeError, match="bulk update failed"):
            UpdatePartialStrategyV2Resource().perform_request(
                {"bk_biz_id": 2, "edit_data": {"is_enabled": False}, "ids": [strategy_id]}
            )

    bulk_create_history.assert_not_called()


@pytest.mark.django_db(databases=("default", "monitor_api"), transaction=True)
def test_bulk_update_opens_transaction_on_monitor_api_before_processing_updates():
    """直接写库的局部更新方法必须位于 monitor_api 事务中。"""
    strategy_queryset = mock.Mock()
    strategy = mock.Mock(id=1001, instance=mock.Mock(), items=[])
    strategy.to_dict.return_value = {"bk_biz_id": 2, "id": 1001, "labels": ["updated"]}

    def update_labels(_strategy, _labels):
        assert connections["default"].in_atomic_block is False
        assert connections["monitor_api"].in_atomic_block is True
        return None, [], []

    with (
        mock.patch.object(StrategyModel.objects, "filter", return_value=strategy_queryset),
        mock.patch.object(StrategyModel.objects, "bulk_update"),
        mock.patch.object(StrategyHistoryModel.objects, "bulk_create"),
        mock.patch.object(Strategy, "from_models", return_value=[strategy]),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_relations", return_value=([], {})),
        mock.patch.object(UpdatePartialStrategyV2Resource, "get_action_configs", return_value={}),
        mock.patch.object(UpdatePartialStrategyV2Resource, "update_labels", side_effect=update_labels),
        mock.patch("monitor_web.strategies.resources.v2.get_global_user", return_value="admin"),
    ):
        UpdatePartialStrategyV2Resource().perform_request(
            {"bk_biz_id": 2, "edit_data": {"labels": {"labels": ["updated"]}}, "ids": [1001]}
        )


def test_strategy_cache_handles_bulk_update_and_delete_histories():
    histories = [
        SimpleNamespace(
            strategy_id=1001,
            operate="bulk_update",
            content={"bk_biz_id": 2, "is_enabled": True},
        ),
        SimpleNamespace(
            strategy_id=1002,
            operate="bulk_update",
            content={"bk_biz_id": 3, "is_enabled": False},
        ),
        SimpleNamespace(strategy_id=1003, operate="delete", content={}),
    ]

    with mock.patch.object(StrategyCacheManager, "get_strategy_by_id", return_value=None):
        target_biz_ids, deleted_strategy_ids = StrategyCacheManager.handle_history_strategies(
            histories, with_group_key=False
        )

    assert target_biz_ids == {2, 3}
    assert deleted_strategy_ids == {(1002, ""), (1003, "")}
