from unittest.mock import PropertyMock

import pytest

from apm.models import TraceDataSource, SharedTraceDataSource
from apm.tests.trace_switch_history import EXCLUSIVE_RT, SHARED_RT


@pytest.fixture
def datasource_apis(mocker):
    mocker.patch.object(TraceDataSource, "retention", new_callable=PropertyMock, return_value=7)
    mocker.patch("apm.models.datasource.bk_biz_id_to_bk_tenant_id", return_value="default")
    mocker.patch("apm.models.datasource.get_global_user", return_value="admin")
    mocker.patch.object(TraceDataSource, "_should_enable_bkdata_datalink", return_value=False)
    mocker.patch.object(TraceDataSource, "_build_result_table_option", return_value={})
    mocker.patch(
        "apm.models.datasource.api.metadata.query_cluster_info",
        return_value=[{"cluster_config": {"custom_option": "{}"}}],
    )
    return {
        "modify": mocker.patch("apm.models.datasource.resource.metadata.modify_result_table", create=True),
        "create_rt": mocker.patch("apm.models.datasource.resource.metadata.create_result_table", create=True),
        "create_index": mocker.patch(
            "apm.models.datasource.api.log_search.create_index_set",
            return_value={"index_set_id": 22, "index_set_name": "new-index"},
        ),
        "update_index": mocker.patch(
            "apm.models.datasource.api.log_search.update_index_set",
            return_value={"index_set_id": 11, "index_set_name": "old-index"},
        ),
        "delete_index": mocker.patch("apm.models.datasource.api.log_search.delete_index_set"),
        "datalink": mocker.patch.object(TraceDataSource, "apply_datalink"),
    }


@pytest.fixture
def exclusive(db):
    return TraceDataSource.objects.create(
        bk_biz_id=2,
        app_name="demo",
        bk_data_id=101,
        result_table_id=EXCLUSIVE_RT,
        index_set_id=11,
        index_set_name="old-index",
        bkdata_datalink_config={"version": 4},
    )


@pytest.fixture
def shared_pool(db):
    return SharedTraceDataSource.objects.create(
        bk_data_id=201,
        result_table_id=SHARED_RT,
        is_enabled=True,
        usage_count=0,
        index_set_id=21,
        index_set_name="shared-index",
        bkdata_datalink_config={"version": 4},
    )


@pytest.fixture
def new_data_id(mocker):
    return mocker.patch(
        "apm.models.datasource.resource.metadata.query_data_source", return_value={"bk_data_id": 301}, create=True
    )
