from metadata import models
from monitor_web.data_migrate.fetcher.metadata.datalink import get_metadata_datalink_fetcher


def test_migration_omits_empty_link_name():
    # 使用真实 ORM 构造子查询，确认排除条件进入最终组件查询。
    fetchers = get_metadata_datalink_fetcher(["2_test.metric"])
    data_id_fetcher = next(item for item in fetchers if item[0] is models.DataIdConfig)
    names = data_id_fetcher[1]["data_link_name__in"]
    sql, params = names.query.sql_with_params()
    assert "NOT" in sql
    assert "data_link_name" in sql
    assert "" in params
