# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import mock
import pytest
from influxdb.resultset import ResultSet

from query_api.drivers import influxdb
from query_api.drivers.proxy import load_driver_by_sql
from query_api.exceptions import ResultTableNotExist, SQLSyntaxError, StorageResultTableNotExist

influxdb.CUSTOM_RT_MAP = {}
pytestmark = pytest.mark.django_db
timestamp_mock_now = 1555000000
ns_step = 1000 ** 3
timestamp_mock_dict = {
    "24h": (timestamp_mock_now - 60 * 60 * 24) * ns_step,
    "1h": (timestamp_mock_now - 60 * 60) * ns_step,
    "5m": (timestamp_mock_now // 60 * 60 - 60 * 5) * ns_step,
    "today": 1554998400 * ns_step,
}


def gen_mocked_cluster_info(db, table):
    return {
        "cluster_config": {"domain_name": "10.0.0.1", "port": 8086},
        "storage_config": {"real_table_name": table, "database": db, "retention_policy_name": ""},
        "cluster_type": "influxdb",
    }


@mock.patch("time.time", return_value=timestamp_mock_now)
class TestInfluxdbDriver(object):
    def test_load_driver(self, mocker):
        table = "heartbeat"
        database = "uptimecheck"
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        with mock.patch("metadata.models.ResultTable.get_result_table", return_value=mocked_rt):
            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info", return_value=mocked_cluster_info
            ):
                assert type(load_driver_by_sql("select * from 2_uptimecheck_heartbeat")) is influxdb.InfluxDBDriver

    def get_driver_obj(self):
        # make a sql driver object
        driver = influxdb.load_driver
        sql = (
            "select avg(runing_tasks) from 2_uptimecheck_heartbeat "
            "where time>='24h' group by node_id, minute1 limit 2"
        )
        table = "heartbeat"
        database = "uptimecheck"
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        with mock.patch("metadata.models.ResultTable.get_result_table", return_value=mocked_rt):
            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info", return_value=mocked_cluster_info
            ):
                driver_obj = driver(sql)
                assert driver_obj._gen_string_token("") is None
                return driver_obj

    def do_test_parse(self, sql_tuple, mocked_rt, mocked_cluster_info):
        with mock.patch(
            "metadata.models.ResultTable.get_result_table", return_value=mocked_rt
        ) as mocked_get_result_table:

            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info", return_value=mocked_cluster_info
            ) as mocked_get_result_table_storage_info:

                driver = influxdb.load_driver
                query_obj = driver(sql_tuple[0])
                assert query_obj.sql == sql_tuple[1]
                mocked_get_result_table.assert_called_once_with(query_obj.q.result_table.value.lower())
                mocked_get_result_table_storage_info.assert_called_once_with(
                    mocked_rt.table_id, influxdb.ClusterInfo.TYPE_INFLUXDB
                )

    def do_test_parse_with_raise(self, sql_tuple, mocked_rt, mocked_cluster_info, e1=None, e2=None):
        with mock.patch(
            "metadata.models.ResultTable.get_result_table", return_value=mocked_rt
        ) as mocked_get_result_table:
            if e1:
                mocked_get_result_table.side_effect = e1

            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info", return_value=mocked_cluster_info
            ) as mocked_get_result_table_storage_info:
                if e2:
                    mocked_get_result_table_storage_info.side_effect = e2

                driver = influxdb.load_driver
                driver(sql_tuple[0])

    def test_parse_sql_1(self, mocker):
        # input
        sql_tuple = (
            "select max(usage) from System.cpu_detail  where time>='1h' and "
            "((ip='10.0.0.1' and bk_cloud_id='0') or (ip='10.0.0.1' and "
            "bk_cloud_id='0')) group by device_name slimit 1000",
            'select max("usage") from cpu_detail  where time>=%d and '
            "((ip='10.0.0.1' and bk_cloud_id='0') or (ip='10.0.0.1' and "
            "bk_cloud_id='0')) group by device_name slimit 1000" % timestamp_mock_dict["1h"],
        )
        table = "cpu_detail"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)

        # begin
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_2(self, mocker):
        # test_max_limit
        max_limit = 5
        # input
        sql_tuple = (
            "select avg(runing_tasks) from 2_uptimecheck_heartbeat "
            "where time>='24h' group by node_id limit 0, 10000000",
            'select MEAN("runing_tasks") from heartbeat '
            "where time>=%d  and bk_biz_id='2' group by node_id limit 200000 slimit %d"
            % (timestamp_mock_dict["24h"], max_limit),
        )
        table = "heartbeat"
        database = "uptimecheck"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        # begin
        with mock.patch("query_api.drivers.influxdb.MAX_LIMIT", max_limit):
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_3(self, mocker):
        # test alias && keyword: LIKE && time format
        # input
        sql_tuple = (
            "select  MAX(w_s) as _value_ from 2_system_io  where "
            "time>=1552638300000 and time<1552641900000 and "
            "ip = '10.0.0.1' and device_name not like '%dev/loop%' and "
            "device_name not like '%dev/sr%' and device_name like '%.iso' "
            "and bk_cloud_id='0' group by minute1,device_name  slimit 50000",
            'select  MAX("w_s") as "_value_" from io  where '
            "time>=1552638300000000000 and time<1552641900000000000 and "
            "ip = '10.0.0.1' and device_name !~ /dev/loop/ and "
            "device_name !~ /dev/sr/ and device_name =~ /.iso$/ and "
            "bk_cloud_id='0'  and bk_biz_id='2' "
            "group by time(1m),device_name  slimit 50000",
        )
        table = "io"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        # begin
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_4(self, mocker):
        # test keyword: * && plat_id -> bk_biz_id && minuteX parse & order
        # input
        sql_tuple = (
            "select count(*) from 2_system_cpu_detail where time>'5m'"
            " group by ip,plat_id,minute1,device_name order by time desc"
            " slimit 1000",
            "select count(*) from cpu_detail where time>%d  and bk_biz_id='2'"
            " group by ip,bk_cloud_id,time(1m),device_name order by time desc"
            " slimit 1000" % timestamp_mock_dict["5m"],
        )
        table = "cpu_detail"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        # begin
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_5(self, mocker):
        # test free schema query parse
        # test ResultTableNotExist、StorageResultTableNotExist
        sql_tuple = (
            "select  MEAN(consul_net_node_latency_max) as _value_ "
            "from 2_exporter_consul_base_metrics where "
            "((consul_datacenter='dc' and ip='127.0.0.1') or (ip!='127.0.0.1'))"
            " and time>=1547298921000 and time<1547385321000 "
            "group by ip,minute5 slimit 5000",
            'select  MEAN(metric_value) as "_value_" from base_metrics where '
            "((consul_datacenter='dc' and ip='127.0.0.1') or (ip!='127.0.0.1'))"
            " and time>=1547298921000000000 and time<1547385321000000000  "
            "and bk_biz_id='2' and metric_name='consul_net_node_latency_max' "
            "group by ip,time(5m) slimit 5000",
        )
        table = "base_metrics"
        database = "exporter_consul"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="free", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        # begin
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)
        with pytest.raises(ResultTableNotExist):
            self.do_test_parse_with_raise(
                sql_tuple, mocked_rt, mocked_cluster_info, e1=influxdb.ResultTable.DoesNotExist()
            )

        with pytest.raises(StorageResultTableNotExist):
            self.do_test_parse_with_raise(
                sql_tuple, mocked_rt, mocked_cluster_info, e1=None, e2=influxdb.ObjectDoesNotExist()
            )

    def test_parse_sql_6(self, mocker):
        # test time field: today
        sql_tuple = (
            "select count(*) from 2_system_cpu_summary where time='today'" " group by ip,plat_id  slimit 50000",
            "select count(*) from cpu_summary where time=%s"
            "  and bk_biz_id='2' group by ip,bk_cloud_id  slimit 50000" % timestamp_mock_dict["today"],
        )
        table = "cpu_summary"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_7(self, mocker):
        # test time filed in where ()
        sql_tuple = (
            'select max("cpu_usage_pct") from system.proc '
            "where (time>='1h' and ip='10.0.0.1' and display_name='es-java' and bk_cloud_id='0') and (app_id='test') "
            "group by pid  slimit 50000",
            'select max("cpu_usage_pct") from "bkmonitor_rp_system.proc".proc '
            "where (time>=%s and ip='10.0.0.1' and display_name='es-java' and bk_cloud_id='0') and "
            "(bk_app_code='test') group by pid  slimit 50000" % timestamp_mock_dict["1h"],
        )
        table = "proc"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        mocked_cluster_info["storage_config"]["retention_policy_name"] = "bkmonitor_rp_system.proc"
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_8(self, mocker):
        # test with slimit keyword (influxql)
        sql_tuple = (
            "select difference(mean(conection_total)) from exporter.base"
            " where bk_biz_id='2' group by minute1, bk_target_ip limit 1",
            'select difference(mean("conection_total")) from base'
            " where bk_biz_id='2' group by time(1m), bk_target_ip limit 1 slimit 50000",
        )
        table = "base"
        database = "exporter"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_9(self, mocker):
        # add case
        sql_tuple = (
            "SELECT cpu, busid, table, target, DELAY_AVG, Environment, 环境, 进程ID, 表名, 进程名, Process, Table, ProcessId, DELAY_MAX, DELAY_MIN, dispatch_to_idc4294967295, ERR_0, ERR_28020, ERR_87006, HeapAllocBalance FROM 2_bkmonitor_time_series_500000.base WHERE time >= '5m' ORDER BY time desc LIMIT 200000",
            'SELECT "cpu", "busid", "table", "target", "DELAY_AVG", "Environment", "环境", "进程ID", "表名", "进程名", "Process", "Table", "ProcessId", "DELAY_MAX", "DELAY_MIN", "dispatch_to_idc4294967295", "ERR_0", "ERR_28020", "ERR_87006", "HeapAllocBalance" FROM base WHERE time >= 1554999660000000000 ORDER BY time desc LIMIT 200000 slimit 50000',
        )
        table = "base"
        database = "2_bkmonitor_time_series_500000"
        table_id = "{}.{}".format(database, table)
        influxdb.CUSTOM_RT_MAP[table_id] = True
        # mock requirements
        mocked_rt = influxdb.ResultTable(table_id=table_id, schema_type="fixed", default_storage="influxdb")
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        # 字段中文不支持
        # self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_10(self, mocker):
        # add case field_name startswith number
        sql_tuple = (
            "SELECT AVG(5v5PvpSettleFormalLeoJack_delay) as A FROM 2_bkmonitor_time_series_500000.__default__ WHERE targets = '' AND time >= 1651891020000 AND time < 1651894620000 GROUP BY time(60s) ORDER BY time desc LIMIT 200000",
            """SELECT MEAN("5v5PvpSettleFormalLeoJack_delay") as "A" FROM __default__ WHERE targets = '' AND time >= 1651891020000000000 AND time < 1651894620000000000 GROUP BY time(60s) ORDER BY time desc LIMIT 200000 slimit 50000""",
        )
        table = "__default__"
        database = "2_bkmonitor_time_series_500000"
        table_id = "{}.{}".format(database, table)
        influxdb.CUSTOM_RT_MAP[table_id] = True
        # mock requirements
        mocked_rt = influxdb.ResultTable(table_id=table_id, schema_type="fixed", default_storage="influxdb")
        mocked_cluster_info = gen_mocked_cluster_info(database, table)
        self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_parse_sql_error(self, mocker):
        # test SQLSyntaxError
        sql_tuple = (
            "select count(*) from 2_system_cpu_summary where time>'today' group by ip,plat_id  limit a, 100",
            "`LIMIT` syntax error.",
        )
        table = "cpu_summary"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select count(*) from 2_system_cpu_summary where time>'today'" " group by ip,plat_id  limit 0, 100, 200",
            "`LIMIT` allows only one value to be specified.",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select count(*) from system_cpu_summary where time>'today'" " group by ip,plat_id  limit 100",
            "无效的rt表名",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select from 2_system_cpu_summary where time>'today'" " group by ip,plat_id  limit 100",
            "语法错误: 查询字段不能为空",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select  MEAN(consul_net_node_latency_max) as _value_, max(usage) "
            "from 2_exporter_consul_base_metrics where "
            "((consul_datacenter='dc' and ip='127.0.0.1') or (ip!='127.0.0.1'))"
            " and time>=1547298921000 and time<1547385321000 "
            "group by ip,minute5 limit 5000",
            "动态字段表查询的指标项最多只能指定一个",
        )
        table = "base_metrics"
        database = "exporter_consul"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="free", default_storage="influxdb"
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1 as a, max(usage) from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id  limit 100",
            "minuteX字段不能设置别名",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1, max(usage) from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id minute2 "
            "order by minute2 limit 100",
            "minuteX字段必须保持一致",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1, max(usage), time from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id minute1 "
            "order by time limit 100",
            "只能使用一个minuteX/time字段",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1, max(usage), time from 2_system_cpu_summary, "
            "system.disk where time>'today' group by ip,plat_id minute1 "
            "order by time limit 100",
            "result_table must only one",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1, max(usage), time from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id minute1 "
            "order by time limit 100;"
            "select minute1, max(usage), time from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id minute1 "
            "order by time limit 100",
            "unsupported multiple sql",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "select minute1, max(usage), time from 2_system_cpu_summary "
            "where time>'today' group by ip,plat_id minute1 "
            "order by time limit abc",
            "LIMIT` need a number",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

        sql_tuple = (
            "from 2_system_io where time >= 1557541380000 and "
            "time < 1557541440000 and fstype!='iso9660' and fstype!='tmpfs' "
            "and fstype!='udf' "
            "group by ip, plat_id, company_id, device_name, minute1 "
            "order by time desc limit 5",
            "sql must start with keyword: `select`",
        )
        with pytest.raises(SQLSyntaxError):
            mocked_cluster_info = gen_mocked_cluster_info(database, table)
            self.do_test_parse(sql_tuple, mocked_rt, mocked_cluster_info)

    def test_query(self, mocker):
        query_obj = self.get_driver_obj()
        mocked_resultset = ResultSet(
            {
                "series": [
                    {
                        "columns": ["time", "mean", "node_id"],
                        "name": "heartbeat",
                        "values": [[1504225680000, 2, "1"], [1504225740000, 3, "2"]],
                    }
                ],
                "statement_id": 0,
            }
        )
        with mock.patch("influxdb.client.InfluxDBClient.query", return_value=mocked_resultset):
            result = query_obj.query()
            assert result.get("device") == influxdb.ClusterInfo.TYPE_INFLUXDB
            assert "list" in result and isinstance(result["list"], list)
            assert "totalRecords" in result and result["totalRecords"] == 2
            assert "timetaken" in result

    def test_query_with_nothing_returned(self, mocker):
        query_obj = self.get_driver_obj()
        with mock.patch("influxdb.client.InfluxDBClient.query", return_value=[]):
            result = query_obj.query()
            assert "list" in result and isinstance(result["list"], list)
            assert "totalRecords" in result and result["totalRecords"] == 0

    def test_where_sql_process(self, mocker):
        # input
        test_sql1 = "select max(usage) from 2_system_cpu_detail"
        test_sql2 = "select max(usage) from 2_system_cpu_detail where time>'1m'"

        table = "cpu_detail"
        database = "system"
        # mock requirements
        mocked_rt = influxdb.ResultTable(
            table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
        )

        # begin
        with mock.patch("metadata.models.ResultTable.get_result_table", return_value=mocked_rt):

            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info",
                return_value=gen_mocked_cluster_info(database, table),
            ):
                driver = influxdb.load_driver
                query_obj = driver(test_sql1)
                assert len(query_obj.sql.split(" where ")) > 1

            with mock.patch(
                "metadata.models.ResultTable.get_result_table_storage_info",
                return_value=gen_mocked_cluster_info(database, table),
            ):
                query_obj = driver(test_sql2)
                assert len(query_obj.sql.split(" and ")) > 1
