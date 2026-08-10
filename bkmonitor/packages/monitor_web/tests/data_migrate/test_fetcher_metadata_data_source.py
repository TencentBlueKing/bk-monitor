import pytest

from monitor_web.data_migrate.fetcher.metadata.data_source import _to_log_group_table_ids


@pytest.mark.parametrize(
    ("table_id", "log_group_table_id"),
    [
        ("19078_bklog.test", "19078_bklog_test"),
        ("space_4281349_bklog.ai_flowtest8__default__json", "space_4281349_bklog_ai_flowtest8__default__json"),
    ],
)
def test_to_log_group_table_ids(table_id, log_group_table_id):
    assert _to_log_group_table_ids([table_id]) == [table_id, log_group_table_id]


def test_to_log_group_table_ids_keeps_unrelated_table_id():
    table_id = "system.cpu"

    assert _to_log_group_table_ids([table_id]) == [table_id]
