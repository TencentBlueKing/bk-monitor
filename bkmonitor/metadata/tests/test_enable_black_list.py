import json

import pytest
from django.conf import settings
from mockredis import mock_redis_client

from bkmonitor.utils import consul
from metadata import models
from metadata.tests.test_models import TestDataSource

pytestmark = pytest.mark.django_db


class TestBlackList(object):
    data_name = "exporter_redis"
    etl_config = "bk_exporter"
    operator = "operator"

    result_table_label = "service_module"
    data_source_label = "bk_monitor"
    data_type_label = "bk_event"

    influxdb_cluster_name = "my_cluster"
    influxdb_host_name = "host1"
    influxdb_username = "username"
    influxdb_password = "password"

    time_series_group_name = "test_group"
    time_series_group_label = "others"

    table_id = "exporter_redis.__default__"

    create_index_mock = None

    def clear_old_db(self):
        models.DataSourceOption.objects.filter().delete()
        models.DataSource.objects.filter().delete()
        models.InfluxDBProxyStorage.objects.filter().delete()
        models.ResultTableOption.objects.filter().delete()
        models.ResultTable.objects.filter().delete()
        models.DataSourceResultTable.objects.filter().delete()
        models.TimeSeriesMetric.objects.filter().delete()
        models.TimeSeriesGroup.objects.filter().delete()

    def test_enable_black_list(self, mocker):
        consul_client = consul.BKConsul()

        # 判断1001基础数据源是否已经有了token
        if models.DataSource.objects.filter(bk_data_id=1001).exists():
            assert models.DataSource.objects.get(bk_data_id=1001).token != ""

        TestDataSource().mock_outer_ralay(mocker)
        mocker.patch("consul.base.Consul.KV.delete", return_value=True)

        TestDataSource().create_base_cluster()
        self.clear_old_db()

        # 2. 创建DataSource
        new_data_source = models.DataSource.create_data_source(
            data_name=self.data_name,
            etl_config=self.etl_config,
            operator=self.operator,
            type_label=self.data_type_label,
            source_label=self.data_source_label,
            option={
                models.DataSourceOption.OPTION_ALLOW_USE_ALIAS_NAME: True,
                models.DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT: True,
            },
        )

        # 3. 判断数据是否存在
        models.DataSource.objects.get(data_name=self.data_name)
        models.KafkaTopicInfo.objects.get(bk_data_id=new_data_source.bk_data_id)
        assert new_data_source.last_modify_user == new_data_source.creator
        assert new_data_source.transfer_cluster_id == settings.DEFAULT_TRANSFER_CLUSTER_ID

        params = {
            "operator": self.operator,
            "bk_data_id": new_data_source.bk_data_id,
            # 平台级接入，ts_group 业务id对应为0
            "bk_biz_id": 0,
            "time_series_group_name": self.time_series_group_name,
            "label": self.time_series_group_label,
            "metric_info_list": [],
            "is_split_measurement": True,
            "table_id": self.table_id,
            "additional_options": {
                "enable_field_black_list": True,
                "enable_default_value": False,
            },
        }
        mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay", return_value=True)
        mocker.patch(
            "metadata.models.custom_report.time_series.TimeSeriesGroup.pre_check",
            return_value={"time_series_group_name": self.time_series_group_name},
        )
        mocker.patch("metadata.utils.redis_tools.RedisTools.metadata_redis_client", side_effect=mock_redis_client)
        mocker.patch("metadata.models.result_table.ResultTable.real_storage_list", return_value=[])
        settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME = self.influxdb_cluster_name
        models.InfluxDBProxyStorage.objects.create(
            proxy_cluster_id=1,
            service_name="default",
            instance_cluster_name="default",
            creator="system",
            updater="system",
            is_default=True,
        ),
        # 创建 TimeSeriesGroup，并把数据写入consul
        group_info = models.TimeSeriesGroup.create_time_series_group(**params)
        # 判断tsgroup存在
        models.TimeSeriesGroup.objects.get(time_series_group_name=self.time_series_group_name)
        consul_config = json.loads(consul_client.kv.get(new_data_source.consul_config_path)[1]["Value"])
        # 判断单指标单表的option传参成功
        assert consul_config["option"]["is_split_measurement"]
        assert consul_config["option"]["disable_metric_cutter"]
        rt = consul_config["result_table_list"][0]
        # 指标启停的字段传递成功
        assert "is_disabled" in rt["field_list"][0]
        # 开启黑名单的option传参成功
        assert rt["option"]["is_split_measurement"]
        assert rt["option"]["enable_field_black_list"]

        group_info.modify_time_series_group(
            operator=self.operator,
            time_series_group_name=self.time_series_group_name,
            label=self.time_series_group_label,
            is_enable=True,
            field_list=[],
            enable_field_black_list=False,
        )

        consul_config = json.loads(consul_client.kv.get(new_data_source.consul_config_path)[1]["Value"])
        rt = consul_config["result_table_list"][0]
        assert not rt["option"]["enable_field_black_list"]
