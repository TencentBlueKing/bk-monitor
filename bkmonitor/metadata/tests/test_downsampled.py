import json
import logging

import pytest

from bkmonitor.utils import consul
from metadata import models

# import pdb
#
# pdb.set_trace()
from metadata.models import (
    DownsampledContinuousQueries,
    DownsampledDatabase,
    DownsampledRetentionPolicies,
    InfluxDBClusterInfo,
    InfluxDBHostInfo,
    InfluxDBStorage,
)
from metadata.utils import go_time

logger = logging.getLogger(__name__)


def assert_equal_list(a: list, b: list):
    a.sort()
    b.sort()
    assert a == b


class CustomBKConsul(object):
    def __init__(self):
        self.kv = CustomKV()

    def put(self, *args, **kwargs):
        return True


class CustomKV(object):
    def __init__(self):
        self.data = {}

    def get(self, key, keys=False):
        print(key)
        if keys:
            key_list = [k for k in self.data.keys() if k.startswith(key)]
            return [[key], key_list]
        else:
            return key, {"Value": json.dumps(self.data.get(key, None))}

    def put(self, key, value):
        print(key, value)
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)
        return True


@pytest.fixture
def clean_record(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", return_value=CustomBKConsul())
    yield
    models.DownsampledDatabase.objects.all().delete()
    models.DownsampledRetentionPolicies.objects.all().delete()


@pytest.mark.django_db
class TestDownSampled(object):
    influxQL = []

    def mock_influxdb(self, mocker, database_list: []):
        def influx_query(q, method: str = "POST"):
            self.influxQL.append(q)
            return {}

        def influx_get_list_retention_policies(database: str = ""):
            self.influxQL.append("SHOW RETENTION POLICIES ON {}".format(database))
            return []

        self.influxQL = []
        mocker.patch(
            "influxdb.client.InfluxDBClient.get_list_retention_policies", side_effect=influx_get_list_retention_policies
        )
        mocker.patch("influxdb.client.InfluxDBClient.query", side_effect=influx_query)

        for db in database_list:
            InfluxDBStorage.objects.get_or_create(
                table_id=db,
                storage_cluster_id=2,
                real_table_name=db,
                database=db,
                source_duration_time="90d",
                proxy_cluster_name=db,
            )
            for host in ["host1"]:
                InfluxDBClusterInfo.objects.get_or_create(
                    cluster_name=db,
                    host_name=host,
                )
                InfluxDBHostInfo.objects.get_or_create(
                    host_name=host,
                    domain_name=host,
                    port=1234,
                )

    def test_sample_for(self, mocker, clean_record):
        logger.info("=====start: test_sample_for=========")

        value_list = [
            ("1s", 2, "2s"),
            ("40s", 2, "80s"),
            ("12h", 2, "1d"),
            ("1.5h", 24, "36h"),
        ]

        for _ in value_list:
            t = go_time.parse_duration(_[0])
            assert go_time.duration_string(_[1] * t) == _[2]

    def test_sync_database(self, mocker, clean_record):
        logger.info("=====start: test_sync_database=========")

        add_database_list = ["demo", "demo1", "demo2"]
        self.mock_influxdb(mocker, add_database_list)

        tag_name = ""
        tag_value = ""
        for database in add_database_list:
            db, is_create = DownsampledDatabase.objects.get_or_create(
                database=database,
                tag_name=tag_name,
                tag_value=tag_value,
                enable=True,
            )
            db.sync_database_config()

        delete_database_list = ["demo1", "demo2"]
        for database in delete_database_list:
            DownsampledDatabase.objects.filter(database=database).delete()

        DownsampledDatabase.clean_consul_config()

        database_list = [database for database in add_database_list if database not in delete_database_list]

        # 验证mysql
        assert_database_list = []
        for db in DownsampledDatabase.objects.all():
            assert_database_list.append(db.database)
        assert_equal_list(database_list, assert_database_list)

        # 验证influxDB
        assert_equal_list([], self.influxQL)

        # 验证consul
        rp_consul_path = "/".join([DownsampledDatabase.CONSUL_PATH, ""])
        client = consul.BKConsul()
        #  bk_monitorv3_community_production/metadata/downsampled/{database}/cq
        consul_keys = client.kv.get(rp_consul_path, keys=True)[1]
        database_consul_keys = [k for k in consul_keys if len(k.split("/")) == 5 and k.split("/")[-1] == "cq"]
        assert_consul_keys = []
        for database in database_list:
            assert_consul_keys.append("/".join([DownsampledDatabase.CONSUL_PATH, database, "cq"]))
        assert_equal_list(database_consul_keys, assert_consul_keys)

        logger.info("=====end: test_sync_database=========")

    def test_sync_rp(self, mocker, clean_record):
        logger.info("=====start: test_sync_rp=========")

        database = "demo_rp"
        duration = "720h"

        self.mock_influxdb(mocker, [database])
        db, is_create = DownsampledDatabase.objects.get_or_create(
            database=database,
            enable=True,
        )
        db.sync_database_config()

        add_rp_name_list = ["1m", "5m", "1h", "12h", "1d"]
        for rp_name in add_rp_name_list:
            DownsampledRetentionPolicies.objects.get_or_create(
                database=database,
                name=rp_name,
                resolution=go_time.parse_duration(rp_name),
                duration=duration,
            )

        DownsampledRetentionPolicies.sync_all(database)

        delete_rp_name_list = ["1m", "1d"]
        for rp_name in delete_rp_name_list:
            DownsampledRetentionPolicies.objects.filter(
                database=database,
                name=rp_name,
            ).delete()

        DownsampledRetentionPolicies.sync_all(database)

        rp_name_list = [rp for rp in add_rp_name_list if rp not in delete_rp_name_list]

        # 验证mysql
        assert_rp_name_list = []
        for rp in DownsampledRetentionPolicies.objects.filter(database=database):
            assert_rp_name_list.append(rp.name)
        assert_equal_list(rp_name_list, assert_rp_name_list)

        # 验证influxDB
        assert_influxQL = ["SHOW RETENTION POLICIES ON {}".format(database)]
        for rp_name in add_rp_name_list:
            assert_influxQL.append(
                'CREATE RETENTION POLICY "{}" ON "{}" DURATION {} REPLICATION 1 SHARD DURATION 0s'.format(
                    rp_name,
                    database,
                    duration,
                )
            )

        for rp_name in delete_rp_name_list:
            # 删除 rp 暂无操作
            pass
        assert_equal_list(self.influxQL, assert_influxQL)

        # 验证consul
        rp_consul_path = "/".join([DownsampledRetentionPolicies.CONSUL_PATH, database, "rp", ""])
        client = consul.BKConsul()
        #  bk_monitorv3_community_production/metadata/downsampled/{database}/rp/{rp_name}
        consul_keys = client.kv.get(rp_consul_path, keys=True)[1]
        rp_consul_keys = [k for k in consul_keys if len(k.split("/")) == 6 and k.split("/")[-2] == "rp"]

        assert_consul_keys = []
        for rp_name in rp_name_list:
            assert_consul_keys.append("/".join([DownsampledRetentionPolicies.CONSUL_PATH, database, "rp", rp_name]))
        assert_equal_list(rp_consul_keys, assert_consul_keys)

        logger.info("=====end: test_sync_rp=========")

    def test_sync_cq(self, mocker, clean_record):
        logger.info("=====start: test_sync_cq=========")

        database = "demo_cq"
        self.mock_influxdb(mocker, [database])
        db, is_create = DownsampledDatabase.objects.get_or_create(
            database=database,
            enable=True,
        )
        db.sync_database_config()

        rp_name_list = ["5m", "1h", "12h"]
        duration = "720h"
        for rp_name in rp_name_list:
            DownsampledRetentionPolicies.objects.get_or_create(
                database=database,
                name=rp_name,
                resolution=go_time.parse_duration(rp_name),
                duration=duration,
            )

        DownsampledRetentionPolicies.sync_all(database)

        add_cq_rp_list = [
            ["autogen", "5m"],
            ["5m", "1h"],
            ["1h", "12h"],
        ]
        add_measurement_list = ["__all__", "bk_apm_duration"]
        fields = "value"
        aggregations = "count,sum,mean"

        for measurement in add_measurement_list:
            for rp in add_cq_rp_list:
                DownsampledContinuousQueries.objects.get_or_create(
                    database=database,
                    measurement=measurement,
                    fields=fields,
                    aggregations=aggregations,
                    source_rp=rp[0],
                    target_rp=rp[1],
                )

        DownsampledContinuousQueries.sync_all(database)

        delete_measurement_list = ["bk_apm_duration"]
        for measurement in delete_measurement_list:
            DownsampledContinuousQueries.objects.filter(database=database, measurement=measurement).delete()

        delete_cq_rp_list = [
            ["1h", "12h"],
        ]
        for rp in delete_cq_rp_list:
            DownsampledContinuousQueries.objects.filter(database=database, target_rp=rp[1]).delete()

        DownsampledContinuousQueries.sync_all(database)

        cq_measurement_list = [m for m in add_measurement_list if m not in delete_measurement_list]
        cq_rp_list = [r for r in add_cq_rp_list if r not in delete_cq_rp_list]

        # 验证mysql
        cq_list = []
        for m in cq_measurement_list:
            for rp in cq_rp_list:
                cq_list.append("{}.{}.{}".format(m, rp[0], rp[1]))
        assert_cq_list = []
        for cq in DownsampledContinuousQueries.objects.filter(database=database):
            assert_cq_list.append("{}.{}.{}".format(cq.measurement, cq.source_rp, cq.target_rp))
        assert_equal_list(cq_list, assert_cq_list)

        # 验证influxdb
        assert_influxQL = ["SHOW RETENTION POLICIES ON {}".format(database)]
        for rp_name in rp_name_list:
            assert_influxQL.append(
                'CREATE RETENTION POLICY "{}" ON "{}" DURATION {} REPLICATION 1 SHARD DURATION 0s'.format(
                    rp_name,
                    database,
                    duration,
                )
            )
        assert_influxQL += [
            "SHOW CONTINUOUS QUERIES",
            'CREATE CONTINUOUS QUERY "5m.__all__" ON "demo_cq" RESAMPLE EVERY 5m FOR 10m BEGIN SELECT count("value") AS count_value, sum("value") AS sum_value, mean("value") AS mean_value INTO "demo_cq"."5m".:MEASUREMENT FROM "demo_cq"."autogen"./.*/ GROUP BY time(5m), * END',  # noqa
            'CREATE CONTINUOUS QUERY "1h.__all__" ON "demo_cq" RESAMPLE EVERY 1h FOR 2h BEGIN SELECT sum("count_value") AS count_value, sum("sum_value") AS sum_value, mean("mean_value") AS mean_value INTO "demo_cq"."1h".:MEASUREMENT FROM "demo_cq"."5m"./.*/ GROUP BY time(1h), * END',  # noqa
            'CREATE CONTINUOUS QUERY "12h.__all__" ON "demo_cq" RESAMPLE EVERY 12h FOR 1d BEGIN SELECT sum("count_value") AS count_value, sum("sum_value") AS sum_value, mean("mean_value") AS mean_value INTO "demo_cq"."12h".:MEASUREMENT FROM "demo_cq"."1h"./.*/ GROUP BY time(12h), * END',  # noqa
            'CREATE CONTINUOUS QUERY "5m.bk_apm_duration" ON "demo_cq" RESAMPLE EVERY 5m FOR 10m BEGIN SELECT count("value") AS count_value, sum("value") AS sum_value, mean("value") AS mean_value INTO "demo_cq"."5m".:MEASUREMENT FROM "demo_cq"."autogen".bk_apm_duration GROUP BY time(5m), * END',  # noqa
            'CREATE CONTINUOUS QUERY "1h.bk_apm_duration" ON "demo_cq" RESAMPLE EVERY 1h FOR 2h BEGIN SELECT sum("count_value") AS count_value, sum("sum_value") AS sum_value, mean("mean_value") AS mean_value INTO "demo_cq"."1h".:MEASUREMENT FROM "demo_cq"."5m".bk_apm_duration GROUP BY time(1h), * END',  # noqa
            'CREATE CONTINUOUS QUERY "12h.bk_apm_duration" ON "demo_cq" RESAMPLE EVERY 12h FOR 1d BEGIN SELECT sum("count_value") AS count_value, sum("sum_value") AS sum_value, mean("mean_value") AS mean_value INTO "demo_cq"."12h".:MEASUREMENT FROM "demo_cq"."1h".bk_apm_duration GROUP BY time(12h), * END',  # noqa
            'DROP CONTINUOUS QUERY "12h.__all__" ON "demo_cq"',
            'DROP CONTINUOUS QUERY "5m.bk_apm_duration" ON "demo_cq"',
            'DROP CONTINUOUS QUERY "1h.bk_apm_duration" ON "demo_cq"',
            'DROP CONTINUOUS QUERY "12h.bk_apm_duration" ON "demo_cq"',
        ]

        assert_equal_list(self.influxQL, assert_influxQL)

        # 验证consul
        cq_consul_path = "/".join([DownsampledContinuousQueries.CONSUL_PATH, database, "cq", ""])
        client = consul.BKConsul()
        # bk_monitor_enterprise_development/metadata/downsampled/{database}/cq/{measurement}/{field}/{target_rp}/{aggregation}
        consul_keys = client.kv.get(cq_consul_path, keys=True)[1]
        cq_consul_keys = [k for k in consul_keys if len(k.split("/")) == 9 and k.split("/")[-5] == "cq"]
        assert_consul_keys = []
        for cq in DownsampledContinuousQueries.objects.filter(database=database):
            assert_consul_keys += cq.consul_config_path
        assert_equal_list(cq_consul_keys, assert_consul_keys)

        logger.info("=====end: test_sync_cq=========")
