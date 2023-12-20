# -*- coding: utf-8 -*-

import pytest
from elasticmock import FakeElasticsearch

from metadata import models
from metadata.tests.common_utils import consul_client, generate_random_string

pytestmark = pytest.mark.django_db

DEFAULT_BK_DATA_ID = 100011
DEFAULT_TRANSFER_CLUSTER_ID = "default"


@pytest.fixture
def table_id():
    return f"{generate_random_string(3)}.{generate_random_string(5)}"


@pytest.fixture
def username():
    return "system"


@pytest.fixture
def create_and_delete_record(username, table_id, mocker):
    datasource_list = list(models.DataSource.objects.all())
    # 平台级 0 业务
    models.ResultTable.objects.create(
        table_id=table_id,
        table_name_zh="test1",
        is_custom_table=True,
        schema_type="fix",
        default_storage="influxDB",
        creator=username,
        last_modify_user=username,
        bk_biz_id=0,
    )
    models.DataSourceResultTable.objects.create(bk_data_id=100011, table_id=table_id, creator=username)
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_BK_DATA_ID,
        data_name="test_snapshot",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
        is_platform_data_id=True,
        transfer_cluster_id=DEFAULT_TRANSFER_CLUSTER_ID,
    )
    yield
    models.DataSourceResultTable.objects.filter(table_id=table_id).delete()
    models.ResultTable.objects.filter(table_id=table_id).delete()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.Space.objects.all().delete()
    models.SpaceResource.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.BCSClusterInfo.objects.all().delete()
    models.TimeSeriesMetric.objects.all().delete()
    models.DataSource.objects.bulk_create(datasource_list)


@pytest.fixture
def create_and_delete_space():
    models.Space.objects.bulk_create(
        [
            models.Space(space_type_id="bkcc", space_id="testcc", space_name="testcc", status=True),
            models.Space(
                space_type_id="bkci", space_id="testbkci1", space_name="testbkci1", status=True, is_bcs_valid=True
            ),
            models.Space(
                space_type_id="bkci", space_id="projectid", space_name="projectid", status=True, space_code="projectid"
            ),
        ]
    )
    yield
    models.Space.objects.all().delete()


class MockSpaceRedis:
    def __init__(self, *args, **kwargs):
        pass

    def push_bcs_type_space(self, *args, **kwargs):
        pass

    def push_bkcc_type_space(self, *args, **kwargs):
        pass


class EventGroupFakeES(FakeElasticsearch):
    def search(self, index=None, doc_type=None, body=None, params=None, headers=None):
        if "aggs" in body:
            # 聚合内容的返回
            return {
                "took": 19,
                "timed_out": False,
                "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
                "hits": {"total": {"value": 4, "relation": "eq"}, "max_score": None, "hits": []},
                "aggregations": {
                    "find_event_name": {
                        "doc_count_error_upper_bound": 0,
                        "sum_other_doc_count": 0,
                        "buckets": [{"key": "login", "doc_count": 2}],
                    }
                },
            }

        else:
            # 单条信息的查询返回
            return {
                "took": 3,
                "timed_out": False,
                "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
                "hits": {
                    "total": {"value": 2, "relation": "eq"},
                    "max_score": None,
                    "hits": [
                        {
                            "_index": "bkmonitor_event_1000_v1",
                            "_type": "_doc",
                            "_id": "9Monh3ABicoxAeyrzdAX",
                            "_score": None,
                            "_source": {
                                "event_name": "login",
                                "bk_target": "1:127.0.0.1",
                                "event": {"event_content": "user login success", "_bk_count": 30},
                                "dimensions": {
                                    "module": "db",
                                    "set": "guangdong",
                                    "log_path": "/data/net/access.log",
                                },
                                "timestamp": 1582795450000,
                            },
                            "sort": [1582795450000000000],
                        }
                    ],
                },
            }
