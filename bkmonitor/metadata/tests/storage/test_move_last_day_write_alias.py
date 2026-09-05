"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import elasticsearch
import elasticsearch5
import elasticsearch6
import pytest
from django.core.management import call_command

from metadata.models import ESStorage


TABLE_ID = "space_4228111_bklog.aigateway_journal_log"
INDEX_NAME = "space_4228111_bklog_aigateway_journal_log"
LATEST_INDEX_NAME = f"v2_{INDEX_NAME}_20260821_0"
LAST_WRITE_ALIAS_NAME = f"write_20260820_{INDEX_NAME}"


def build_es_storage(alias_result=None, alias_side_effect=None):
    es_client = Mock()
    es_client.indices.get_alias.return_value = alias_result
    es_client.indices.get_alias.side_effect = alias_side_effect
    return SimpleNamespace(
        table_id=TABLE_ID,
        now=datetime(2026, 8, 21, 17, 3, 45),
        date_format="%Y%m%d",
        index_name=INDEX_NAME,
        es_client=es_client,
        get_index_names=Mock(return_value=[LATEST_INDEX_NAME]),
        get_index_info=Mock(),
        _update_aliases_with_retry=Mock(),
    )


@pytest.mark.parametrize(
    "not_found_error",
    [
        elasticsearch5.NotFoundError,
        elasticsearch6.NotFoundError,
        elasticsearch.NotFoundError,
    ],
)
def test_move_last_day_write_alias_ignores_missing_alias(not_found_error, capsys):
    es_storage = build_es_storage(alias_side_effect=not_found_error)

    ESStorage.move_last_day_write_alias(es_storage=es_storage, force_move=True)

    assert "上一个索引没有进行配置" in capsys.readouterr().out
    es_storage.es_client.indices.get_alias.assert_called_once_with(name=LAST_WRITE_ALIAS_NAME)
    es_storage.get_index_info.assert_not_called()
    es_storage._update_aliases_with_retry.assert_not_called()


def test_move_last_day_write_alias_ignores_empty_alias_result(capsys):
    es_storage = build_es_storage(alias_result={})

    ESStorage.move_last_day_write_alias(es_storage=es_storage)

    assert "上一个索引没有进行配置" in capsys.readouterr().out
    es_storage.get_index_info.assert_not_called()
    es_storage._update_aliases_with_retry.assert_not_called()


def test_move_last_day_write_alias_ignores_alias_already_pointing_to_latest_index(capsys):
    es_storage = build_es_storage(alias_result={LATEST_INDEX_NAME: {}})

    ESStorage.move_last_day_write_alias(es_storage=es_storage)

    assert "已经在写别名指向的索引列表中" in capsys.readouterr().out
    es_storage.get_index_info.assert_not_called()
    es_storage._update_aliases_with_retry.assert_not_called()


def test_move_last_day_write_alias_propagates_unexpected_errors():
    es_storage = build_es_storage(alias_side_effect=RuntimeError("alias query failed"))

    with pytest.raises(RuntimeError, match="alias query failed"):
        ESStorage.move_last_day_write_alias(es_storage=es_storage)

    es_storage._update_aliases_with_retry.assert_not_called()


def test_move_last_day_write_alias_command_succeeds_when_alias_is_missing(mocker, capsys):
    es_storage = build_es_storage(alias_side_effect=elasticsearch.NotFoundError)
    mocker.patch(
        "metadata.management.commands.move_last_day_write_alias.ESStorage.objects.filter",
        return_value=[es_storage],
    )
    stdout = StringIO()

    call_command(
        "move_last_day_write_alias",
        table_id=TABLE_ID,
        bk_tenant_id="system",
        force_move=True,
        stdout=stdout,
    )

    assert "上一个索引没有进行配置" in capsys.readouterr().out
    assert f"处理完成 table_id->[{TABLE_ID}]" in stdout.getvalue()
    es_storage._update_aliases_with_retry.assert_not_called()
