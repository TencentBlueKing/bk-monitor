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
import datetime
import json
import os

import elasticsearch5
import pytest
from django.conf import settings
from django.core.management import call_command
from django.db.models import Q
from mockredis import mock_redis_client

from bkmonitor.utils import consul
from metadata import config, models

from ..utils import consul_tools
from .common_utils import any_return_model

pytestmark = pytest.mark.django_db
IS_CONSUL_MOCK = True
es_index = {}


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
            if self.data.get(key, None):
                return key, {"Value": json.dumps(self.data.get(key, None))}
            else:
                return key, None

    def put(self, key, value):
        print(key, value)
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)
        return True


@pytest.fixture(autouse=True)
def auto_fixture(mocker):
    mocker.patch("django.dispatch.dispatcher.Signal.send", return_value=True)


@pytest.fixture
def patch_redis_tools(mocker):
    client = mock_redis_client()

    def mock_hset_redis(*args, **kwargs):
        client.hset(*args, **kwargs)

    def mock_hget_redis(*args, **kwargs):
        return client.hget(*args, **kwargs)

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    def mock_hgetall_redis(*args, **kwargs):
        return client.hgetall(*args, **kwargs)

    def mock_publish(*args, **kwargs):
        return client.publish(*args, **kwargs)

    # NOTE: 这里需要把参数指定出来，防止 *["test"] 解析为 ["test"]
    def mock_hdel_redis(key, fields):
        return client.hdel(key, *fields)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", side_effect=mock_hset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hgetall", side_effect=mock_hgetall_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hget", side_effect=mock_hget_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hdel", side_effect=mock_hdel_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.publish", side_effect=mock_publish)


class TestKafkaTopic(object):
    def test_create_info(self, mocker):
        """没有同名的配置，可以正常写入"""

        # mock无已经存在的内容
        mocker.patch("django.db.models.query.QuerySet.exists", return_value=False)

        create_mock = mocker.patch(
            "metadata.models.KafkaTopicInfo.objects.create", side_effect=any_return_model(models.KafkaTopicInfo)
        )

        # 开始验证
        models.KafkaTopicInfo.create_info("123")
        create_mock.assert_called_once_with(
            bk_data_id="123",
            # 如果topic没有指定，则设定为该data_id同名
            topic="{}1230".format(config.KAFKA_TOPIC_PREFIX),
            partition=1,
            batch_size=None,
            flush_interval=None,
            consume_rate=None,
        )

    def test_create_info_exists(self, mocker):
        """假设已经有同名的配置，不可以继续写入"""
        mocker.patch("django.db.models.query.QuerySet.exists", return_value=True)

        with pytest.raises(ValueError):
            models.KafkaTopicInfo.create_info("123")


class TestDataSource(object):
    data_name = "2_system.cpu"
    etl_config = "basereport"
    operator = "operator"

    result_table_label = "service_module"
    data_source_label = "bk_monitor"
    data_type_label = "bk_event"

    influxdb_cluster_name = "my_cluster"
    influxdb_host_name = "host1"
    influxdb_username = "username"
    influxdb_password = "password"

    create_index_mock = None

    @pytest.fixture
    def mock_outer_ralay(self, mocker):
        """统一的屏蔽外部的依赖"""

        # 全局屏蔽外部的依赖
        mocker.patch("metadata.models.DataSource.create_mq", return_value=True)
        mocker.patch("metadata.models.DataSource.refresh_gse_config", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_database", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_rp", return_value=True)
        mocker.patch("metadata.models.KafkaStorage.ensure_topic", return_value=True)
        mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay", return_value=True)
        mocker.patch("celery.app.task.Task.delay", return_value=True)

        def es_exists(index, *args, **kwargs):
            return index in es_index

        def add_es_index(index, *args, **kwargs):
            es_index[index] = True
            return True

        self.put_alias_mock = mocker.patch("elasticsearch5.client.indices.IndicesClient.put_alias", return_value=True)

        self.create_index_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.create",
            side_effect=add_es_index,
        )

        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.exists",
            side_effect=es_exists,
        )

        def es_get_index(index_name, *args, **kwargs):
            # 先找到原本的table_id
            table_id = index_name[:-1].replace(".", "_")

            # 返回两个index -- 一个是过期（三年前），一个未过期（一天后）
            out_date = (datetime.datetime.utcnow() - datetime.timedelta(days=365 * 3)).strftime("%Y%m%d%H")
            new_date = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y%m%d%H")

            return {"{}_{}_0".format(table_id, out_date): "", "{}_{}_0".format(table_id, new_date): ""}

        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.get",
            side_effect=es_get_index,
        )

        self.delete_index_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.delete",
        )

        self.delete_alias_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.delete_alias",
        )

        def empty_stat(*args, **kwargs):
            return {"indices": {}}

        stat_mock = mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=empty_stat)  # noqa

        count_mock = mocker.patch(  # noqa
            "elasticsearch5.client.Elasticsearch.count", side_effect=elasticsearch5.NotFoundError()
        )

        if IS_CONSUL_MOCK:
            mocker.patch("consul.base.Consul.KV.delete", return_value=True)

            mocker.patch("consul.base.Consul.KV.put", return_value=True)

            test_storage_dict = {}

            def _save(key, value):
                test_storage_dict[key] = {
                    "CreateIndex": 438,
                    "Flags": 0,
                    "Key": key,
                    "LockIndex": 0,
                    "ModifyIndex": 3634,
                    "Value": value,
                }

            def _get(key):
                value = test_storage_dict.get(key)
                return 1, value

            put_method = mocker.patch("consul.base.Consul.KV.put", return_value=True, side_effect=_save)  # noqa

            mocker.patch("consul.base.Consul.KV.get", return_value=True, side_effect=_get)

        # mock gse 请求接口依赖
        base_channel_id = 1500000

        def gen_channel_id(*args, **kwargs):
            nonlocal base_channel_id
            base_channel_id += 1
            return {"channel_id": base_channel_id}

        mocker.patch("core.drf_resource.api.gse.add_route", side_effect=gen_channel_id)

    @pytest.fixture
    def create_and_delete_record(self, mocker):
        clusters = list(models.ClusterInfo.objects.all())
        models.ClusterInfo.objects.all().delete()
        models.ResultTableField.objects.all().delete()
        models.ClusterInfo.objects.create(
            cluster_name="test_kafka_cluster",
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=True,
        )
        models.ClusterInfo.objects.create(
            cluster_name="test_kafka_cluster2",
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=False,
        )
        models.ClusterInfo.objects.create(
            cluster_name="test_ES_cluster",
            cluster_type=models.ClusterInfo.TYPE_ES,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=True,
            version="5.x",
        )
        influx = models.ClusterInfo.objects.create(
            cluster_name="test_influxdb_cluster",
            cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=True,
        )
        models.ClusterInfo.objects.create(
            cluster_name="test_redis_cluster",
            cluster_type=models.ClusterInfo.TYPE_REDIS,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=True,
        )
        models.Label.objects.create(label_id=self.data_type_label, label_type=models.Label.LABEL_TYPE_TYPE)
        models.InfluxDBClusterInfo.objects.create(
            host_name="host_name",
            cluster_name=self.influxdb_cluster_name,
            host_readable=True,
        )
        models.InfluxDBProxyStorage.objects.create(
            is_default=True, proxy_cluster_id=influx.cluster_id, instance_cluster_name=self.influxdb_cluster_name
        )
        yield
        models.ClusterInfo.objects.filter(
            cluster_name__in=[
                "test_ES_cluster",
                "test_influxdb_cluster",
                "test_kafka_cluster",
                "test_kafka_cluster2",
                "test_redis_cluster",
            ]
        ).delete()
        models.ESStorage.objects.all().delete()
        models.Label.objects.filter(label_id=self.data_type_label).delete()
        models.InfluxDBClusterInfo.objects.filter(cluster_name=self.influxdb_cluster_name).delete()
        models.InfluxDBStorage.objects.filter(proxy_cluster_name=self.influxdb_cluster_name).delete()
        models.InfluxDBProxyStorage.objects.all().delete()
        models.ResultTable.objects.filter(table_name_zh__in=["test_group_name", self.data_name]).delete()
        models.ResultTableOption.objects.all().delete()
        models.ResultTableField.objects.all().delete()
        models.RedisStorage.objects.all().delete()
        models.KafkaStorage.objects.all().delete()
        models.DataSource.objects.filter(bk_data_id__gte=1500000).delete()
        models.DataSourceResultTable.objects.filter(bk_data_id__gte=1500000).delete()
        models.KafkaTopicInfo.objects.filter(bk_data_id__gte=1500000).delete()
        models.DataSourceOption.objects.filter(bk_data_id__gte=1500000).delete()
        models.TimeSeriesGroup.objects.filter(bk_data_id__gte=1500000).delete()
        models.EventGroup.objects.filter(bk_data_id__gte=1500000).delete()
        models.ResultTableFieldOption.objects.filter(table_id__contains="1500").delete()
        models.ResultTableFieldOption.objects.filter(table_id="2_system.cpu").delete()
        models.CMDBLevelRecord.objects.all().delete()
        models.ClusterInfo.objects.bulk_create(clusters)

    def test_create_new_data_source(self, mocker, mock_outer_ralay, patch_redis_tools, create_and_delete_record):
        consul_client = consul.BKConsul()

        # 判断1001基础数据源是否已经有了token
        if models.DataSource.objects.filter(bk_data_id=1001).exists():
            assert models.DataSource.objects.get(bk_data_id=1001).token != ""

        mocker.patch("consul.base.Consul.KV.delete", return_value=True)

        cluster = models.ClusterInfo.objects.get(cluster_type=models.ClusterInfo.TYPE_KAFKA, is_default_cluster=True)

        # 2. 测试创建
        new_data_source = models.DataSource.create_data_source(
            data_name=self.data_name,
            etl_config=self.etl_config,
            operator=self.operator,
            type_label=self.data_type_label,
            source_label=self.data_source_label,
            option={models.DataSourceOption.OPTION_ALLOW_USE_ALIAS_NAME: True},
        )

        # 3. 判断数据是否存在
        models.DataSource.objects.get(data_name=self.data_name)
        models.KafkaTopicInfo.objects.get(bk_data_id=new_data_source.bk_data_id)
        old_modify_time = new_data_source.last_modify_time

        assert new_data_source.last_modify_user == new_data_source.creator
        assert new_data_source.transfer_cluster_id == settings.DEFAULT_TRANSFER_CLUSTER_ID

        # 更新配置
        new_data_source.update_config(
            operator="new_%s" % self.operator,
            mq_cluster_id=cluster.cluster_id,
            etl_config="new_etl_config",
            data_name="{}_new".format(self.data_name),
        )
        new_data_source.refresh_from_db()
        assert new_data_source.data_name == "{}_new".format(self.data_name)

        new_data_source.update_config(operator="new_%s" % self.operator, data_name=self.data_name)
        new_data_source.refresh_from_db()
        assert new_data_source.data_name == self.data_name

        new_data_source.update_config(operator=f"new_{self.operator}", is_enable=False)
        if not IS_CONSUL_MOCK:
            consul_client.kv.get(new_data_source.consul_config_path)

        new_data_source.update_config(operator=f"new_{self.operator}", is_enable=True)

        with pytest.raises(ValueError):
            new_data_source.update_config(
                operator="new_%s" % self.operator, mq_cluster_id=123123, etl_config="new_etl_config"
            )

        new_data_source.refresh_from_db()
        assert new_data_source.last_modify_user == "new_%s" % self.operator
        assert new_data_source.last_modify_time != old_modify_time
        assert new_data_source.etl_config == "new_etl_config"
        assert new_data_source.source_label == self.data_source_label
        assert new_data_source.type_label == self.data_type_label

        # 4. 进一步的测试创建RT表
        settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME = self.influxdb_cluster_name
        new_table = models.ResultTable.create_result_table(
            bk_data_id=new_data_source.bk_data_id,
            table_id=new_data_source.data_name,
            table_name_zh=new_data_source.data_name,
            is_custom_table=False,
            schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
            operator=self.operator,
            default_storage=models.ClusterInfo.TYPE_INFLUXDB,
            default_storage_config={
                "database": "2_system",
                "real_table_name": "cpu",
                "proxy_cluster_name": self.influxdb_cluster_name,
                "source_duration_time": "90d",
            },
            field_list=(
                {
                    "field_name": "custom_field",
                    "field_type": models.ResultTableField.FIELD_TYPE_INT,
                    "operator": self.operator,
                    "is_config_by_user": True,
                    "tag": "dimension",
                    "option": {models.ResultTableFieldOption.OPTION_ES_FIELD_TYPE: "string"},
                },
            ),
            bk_biz_id=2,
            label=self.result_table_label,
            external_storage={"kafka": {}},
            option={"es_unique_field_list": ["field_1"]},
        )

        # 判断创建的新结果表label是否符合预期
        assert new_table.label == self.result_table_label
        # 判断存在kafka的配置
        assert models.KafkaStorage.objects.filter(table_id=new_table.table_id).count() == 1
        # 判断存在对应的字段选项
        rt_field_option = models.ResultTableFieldOption.objects.get(
            table_id=new_data_source.data_name,
            field_name="custom_field",
            name=models.ResultTableFieldOption.OPTION_ES_FIELD_TYPE,
        )
        assert rt_field_option.name == models.ResultTableFieldOption.OPTION_ES_FIELD_TYPE
        assert rt_field_option.value == "string"
        assert "type" in rt_field_option.get_field_option_es_format(
            table_id=new_data_source.data_name, field_name="custom_field"
        )
        # 结果表option可以正常创建
        models.ResultTableOption.objects.get(table_id=new_table.table_id, name="es_unique_field_list")
        assert (
            models.InfluxDBStorage.objects.get(
                table_id=new_table.table_id, proxy_cluster_name=self.influxdb_cluster_name
            ).source_duration_time
            == "90d"
        )

        # 清理所有的kafka存储，防止影响其他的测试进度
        models.KafkaStorage.objects.all().delete()

        # 变更字段，可以正常加入
        new_table.create_field(
            **{
                "field_name": "good_custom_field",
                "field_type": models.ResultTableField.FIELD_TYPE_INT,
                "operator": self.operator,
                "is_config_by_user": True,
                "tag": "dimension",
            }
        )

        # 变更字段，由于原本是FIXED字段的，不可变更
        with pytest.raises(ValueError):
            new_table.schema_type = models.ResultTable.SCHEMA_TYPE_FIXED
            new_table.create_field(
                **{
                    "field_name": "bad_custom_field",
                    "field_type": models.ResultTableField.FIELD_TYPE_INT,
                    "operator": self.operator,
                    "is_config_by_user": True,
                    "tag": "dimension",
                }
            )
        # 恢复字段自有配置
        new_table.schema_type = models.ResultTable.SCHEMA_TYPE_FREE

        # 验证结果表路由写入consul能力
        if not IS_CONSUL_MOCK:
            # 配置刷入至consul中
            for result_table in models.InfluxDBStorage.objects.all():
                result_table.refresh_consul_cluster_config()

            models.InfluxDBClusterInfo.refresh_consul_cluster_config()

            for host in models.InfluxDBHostInfo.objects.all():
                host.refresh_consul_cluster_config()

            consul_config = json.loads(consul_client.kv.get(new_data_source.consul_config_path)[1]["Value"])
            for storage_config in consul_config["result_table_list"][0]["shipper_list"]:
                if storage_config["cluster_type"] == "influxdb":
                    assert storage_config["storage_config"]["retention_policy_name"] == ""
                    break

            # 结果表路由信息
            measurement_path = "/".join([config.CONSUL_PATH, "influxdb_info", "router", "2_system", "cpu"])
            measurement_router_info = json.loads(consul_client.kv.get(measurement_path)[1]["Value"])
            assert measurement_router_info["cluster"] == self.influxdb_cluster_name

            # 集群信息
            cluster_path = "/".join([config.CONSUL_PATH, "influxdb_info", "cluster_info", "default"])
            cluster_info = json.loads(consul_client.kv.get(cluster_path)[1]["Value"])
            assert len(cluster_info["host_list"]) != 0

            # 主机信息
            host_path = "/".join([config.CONSUL_PATH, "influxdb_info", "host_info", self.influxdb_host_name])
            host_info = json.loads(consul_client.kv.get(host_path)[1]["Value"])
            assert host_info["domain_name"] == "domain.com"

        # 5. 判断RT的信息都是存在的
        models.ResultTable.objects.get(table_id=new_data_source.data_name)
        assert models.ResultTableField.objects.all().count() == 11
        models.InfluxDBStorage.objects.get(table_id=new_table.table_id)
        assert models.DataSourceResultTable.objects.filter(bk_data_id=new_data_source.bk_data_id).count() == 1

        # 6. 更新RT的配置信息
        new_table.modify(
            field_list=(
                {
                    "field_type": "long",
                    "field_name": "idle",
                    "tag": "metric",
                    "option": {models.ResultTableFieldOption.OPTION_ES_INCLUDE_IN_ALL: False},
                },
            ),
            default_storage=models.ClusterInfo.TYPE_INFLUXDB,
            external_storage={
                models.ClusterInfo.TYPE_INFLUXDB: {
                    "source_duration_time": "30d",
                    # 测试增加异常配置不会影响逻辑
                    "external_config": "nothing",
                }
            },
            operator="other_operator",
        )
        new_table.refresh_from_db()
        # 判断存储是否有更新
        assert new_table.default_storage == models.ClusterInfo.TYPE_INFLUXDB
        # 判断修改时间是否有生效
        assert new_table.last_modify_user == "other_operator"
        # 判断字段的修改是否生效
        assert models.ResultTableField.objects.filter(table_id=new_table.table_id).count() == 10
        models.ResultTableField.objects.get(table_id=new_table.table_id, field_name="idle")
        assert not models.ResultTableField.objects.filter(table_id=new_table.table_id, field_name="good_custom_field")
        # 修改后，确保这个结果表对应的已有option已经都被清理了
        with pytest.raises(models.ResultTableFieldOption.DoesNotExist):
            models.ResultTableFieldOption.objects.get(
                table_id=new_table.table_id, name=models.ResultTableFieldOption.OPTION_ES_FIELD_TYPE
            )
        # 新加的配置存在
        assert models.ResultTableFieldOption.objects.get(
            table_id=new_table.table_id, name=models.ResultTableFieldOption.OPTION_ES_INCLUDE_IN_ALL
        )

        assert models.InfluxDBStorage.objects.get(table_id=new_table.table_id).source_duration_time == "30d"

        field_name = models.ResultTableField.objects.get(table_id=new_table.table_id, field_name="idle")
        field_name.alias_name = "haha_field"
        field_name.save()
        # 确认修改不会影响data_source与result_table的关系
        models.DataSourceResultTable.objects.get(table_id=new_table.table_id)

        new_data_source.refresh_consul_config()

        # ================option及别名测试================
        # 验证存在option及alias_name
        if not IS_CONSUL_MOCK:
            # 该测试只有在consul生效时进行校验
            consul_client = consul.BKConsul()
            consul_config = consul_client.kv.get(new_data_source.consul_config_path)[1]

            assert (
                json.loads(consul_config["Value"])["option"].get(models.DataSourceOption.OPTION_ALLOW_USE_ALIAS_NAME)
                is True
            )

        # ================多写入配置测试===================
        # 增加一个redis的写入配置
        models.RedisStorage.create_table(new_table.table_id)
        new_data_source.refresh_consul_config()

        if not IS_CONSUL_MOCK:
            # 该测试只有在consul生效时进行校验
            consul_client = consul.BKConsul()
            consul_config = json.loads(consul_client.kv.get(new_data_source.consul_config_path)[1]["Value"])

            # 验证consul的option配置有效
            assert {"es_unique_field_list": ["field_1"]} == consul_config["result_table_list"][0]["option"]

            shipper_list = consul_config["result_table_list"][0]["shipper_list"]

            # 增加一个kafka及redis配置
            assert len(shipper_list) == 2
            # 单元测试的写法而已，不值得参考
            redis_config = [
                rconfig for rconfig in shipper_list if rconfig["cluster_type"] == models.ClusterInfo.TYPE_REDIS
            ][0]
            assert "db" in redis_config["storage_config"]
            assert redis_config["storage_config"]["key"] == "_".join([config.REDIS_KEY_PREFIX, new_table.table_id])

        # 增加一个KAFKA的写入配置
        models.KafkaStorage.create_table(new_table.table_id)
        new_data_source.refresh_consul_config()

        if not IS_CONSUL_MOCK:
            # 该测试只有在consul生效时进行校验
            consul_client = consul.BKConsul()
            consul_config = json.loads(consul_client.kv.get(new_data_source.consul_config_path)[1]["Value"])

            shipper_list = consul_config["result_table_list"][0]["shipper_list"]

            assert len(shipper_list) == 3
            # 单元测试的写法而已，不值得参考
            redis_config = [
                rconfig for rconfig in shipper_list if rconfig["cluster_type"] == models.ClusterInfo.TYPE_KAFKA
            ][0]
            assert "topic" in redis_config["storage_config"]
            assert redis_config["storage_config"]["topic"] == "_".join(
                [config.KAFKA_TOPIC_PREFIX_STORAGE, new_table.table_id]
            )

            # 判断字段option是否写入
            field_list = consul_config["result_table_list"][0]["field_list"]
            assert "option" in field_list[0]

        # ===========CMDB字段拆分测试==============
        data_source_count = models.DataSource.objects.all().count()

        # 1. 创建一个新的CMDB拆分配置
        new_table.set_metric_split(cmdb_level="level_1", operator=self.operator)
        cmdb_record = models.CMDBLevelRecord.objects.get(source_table_id=new_table.table_id)
        cmdb_record_data_source = models.DataSource.objects.get(bk_data_id=cmdb_record.bk_data_id)
        # 确认：
        # 有新的数据源创建
        assert models.DataSource.objects.all().count() - 1 == data_source_count
        new_table_id = config.RT_CMDB_LEVEL_RT_NAME.format(new_table.table_id)
        # 已有的结果表有新写入的MQ配置
        assert (
            models.KafkaStorage.objects.filter(
                table_id=new_table.table_id, topic=cmdb_record_data_source.mq_config.topic
            ).count()
            == 1
        )
        assert cmdb_record_data_source.mq_config.topic == "_".join(
            [config.KAFKA_TOPIC_PREFIX_STORAGE, new_table.table_id]
        )

        # 有新的结果表创建
        models.ResultTable.objects.get(table_id=new_table_id)
        # 新的结果表字段有对应的CMDB字段
        models.ResultTableField.objects.get(table_id=new_table_id, field_name="idle")
        models.ResultTableField.objects.get(table_id=new_table_id, field_name="bk_obj_id")
        models.ResultTableField.objects.get(table_id=new_table_id, field_name="bk_inst_id")

        # 新的结果表有对应的option配置
        models.ResultTableOption.objects.get(table_id=new_table_id)

        result_table_count = models.ResultTable.objects.all().count()

        # 2. 重新创建一个CMDB拆分配置
        new_table.set_metric_split(cmdb_level="level_2", operator=self.operator)

        # 确认：
        # 没有新的数据源创建
        assert models.DataSource.objects.all().count() - 1 == data_source_count
        # 没有新的结果表创建
        assert result_table_count == models.ResultTable.objects.all().count()

        # 3. 修改已有的结果表字段
        new_table.modify(
            field_list=({"field_type": "long", "field_name": "idle_new", "tag": "metric"},), operator="other_operator"
        )
        # 确认：
        # 新的结果表字段也有对应的增加
        models.ResultTableField.objects.get(table_id=new_table_id, field_name="idle_new")
        # option有对应的数组写入
        option_value = models.ResultTableOption.objects.get(table_id=new_table_id).to_json()["cmdb_level_config"]
        assert isinstance(option_value, list)
        assert "level_1" in option_value
        assert "level_2" in option_value

        # 清理其中一个level
        new_table.clean_metric_split(cmdb_level="level_2", operator=self.operator)
        option_value = models.ResultTableOption.objects.get(table_id=new_table_id).to_json()["cmdb_level_config"]
        assert isinstance(option_value, list)
        assert "level_1" in option_value
        assert "level_2" not in option_value

        # =======================结果表升级能力测试=============
        # 测试升级能力
        new_table.upgrade_result_table("system_modify")

        # 结果表已经指向了新的内容
        assert new_table.table_id == "system.cpu"
        assert new_table.bk_biz_id == 0
        assert new_table.last_modify_user == "system_modify"

        # 信息已经被删除
        assert not models.DataSourceResultTable.objects.filter(table_id=self.data_name).exists()
        assert not models.ResultTableField.objects.filter(table_id=self.data_name).exists()
        assert not models.InfluxDBStorage.objects.filter(table_id=self.data_name).exists()
        # 需要确保之前的结果表已经被标记为删除
        models.ResultTable.objects.get(table_id=self.data_name, is_deleted=True)

        # 新信息存在
        assert models.DataSourceResultTable.objects.filter(table_id="system.cpu").exists()
        assert models.ResultTableField.objects.filter(table_id="system.cpu").exists()
        assert models.InfluxDBStorage.objects.filter(table_id="system.cpu").exists()
        # 新信息中的结果表指向没有变化
        influxdb_storage = models.InfluxDBStorage.objects.get(table_id="system.cpu")
        assert influxdb_storage.real_table_name == "cpu" and influxdb_storage.database == "2_system"

        # =====================默认存储Kafka测试===========
        default_storage_table_id = "{}_kafka_defaul_storage".format(new_data_source.data_name)
        new_table = models.ResultTable.create_result_table(
            bk_data_id=new_data_source.bk_data_id,
            table_id=default_storage_table_id,
            table_name_zh=new_data_source.data_name,
            is_custom_table=False,
            schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
            operator=self.operator,
            default_storage=models.ClusterInfo.TYPE_KAFKA,
            default_storage_config={},
            field_list=(
                {
                    "field_name": "custom_field",
                    "field_type": models.ResultTableField.FIELD_TYPE_INT,
                    "operator": self.operator,
                    "is_config_by_user": True,
                    "tag": "dimension",
                },
            ),
            bk_biz_id=2,
            label=self.result_table_label,
        )
        assert models.KafkaStorage.objects.filter(table_id=new_table.table_id).exists()

    def test_create_exists_data_source(self, mocker):
        # 已经有DataSource了
        mocker.patch("django.db.models.query.QuerySet.exists", return_value=True)

        with pytest.raises(ValueError):
            models.DataSource.create_data_source(
                data_name=self.data_name,
                etl_config=self.etl_config,
                operator=self.operator,
                source_label=self.data_source_label,
                type_label=self.data_type_label,
            )

    def test_create_data_source_no_cluster(self, mocker):
        # Datasource不存在
        mocker.patch("django.db.models.query.QuerySet.exists", return_value=False)

        def raise_error(*args, **kwargs):
            raise models.ClusterInfo.DoesNotExist()

        # 但是集群不存在
        mocker.patch("metadata.models.ClusterInfo.objects.get", side_effect=raise_error)

        with pytest.raises(ValueError):
            models.DataSource.create_data_source(
                data_name=self.data_name,
                etl_config=self.etl_config,
                operator=self.operator,
                type_label=self.data_type_label,
                source_label=self.data_source_label,
            )

    def test_standard_fields_discover(self, mocker, mock_outer_ralay, create_and_delete_record, patch_redis_tools):
        """测试字段自动发现的逻辑能力"""
        # 1. 准备工作
        new_data_source = models.DataSource.create_data_source(
            data_name=self.data_name,
            etl_config="bk_standard",
            operator=self.operator,
            source_label=self.data_source_label,
            type_label=self.data_type_label,
        )

        # 创建一个对应的结果表
        new_table = models.ResultTable.create_result_table(
            bk_data_id=new_data_source.bk_data_id,
            table_id=new_data_source.data_name,
            table_name_zh=new_data_source.data_name,
            is_custom_table=False,
            schema_type=models.ResultTable.SCHEMA_TYPE_DYNAMIC,
            operator=self.operator,
            default_storage=models.ClusterInfo.TYPE_INFLUXDB,
            default_storage_config={"database": "standard", "real_table_name": new_data_source.data_name},
            field_list=[
                {"field_name": "usage", "field_type": "float"},
                {"field_name": "hostname", "field_type": "string"},
            ],
            bk_biz_id=2,
            time_alias_name="haha_time_field",
        )

        # 屏蔽Consul返回字段的信息内容
        mocker.patch(
            "metadata.models.DataSource.get_consul_fields",
            return_value=[
                {
                    # 指标字段名称
                    "metric": {
                        # 字段类型可有以下选项：
                        # int: 整形
                        # float: 浮点型
                        # string: 字符串
                        # timestamp: 时间戳
                        "type": "float",
                        # 是否由用户配置字段，可能存在字段已自动发现，但未由用户确认
                        "is_config_by_user": True,
                        # 字段名
                        "field_name": "usage",
                        "updated_time": "2018-09-09 10:10:10",
                    },
                    # 组成该条记录的维度字段列表
                    "dimension": [
                        {
                            # 字段类型可有以下选项：
                            # int: 整形
                            # float: 浮点型
                            # string: 字符串
                            # timestamp: 时间戳
                            "type": "string",
                            # 是否由用户配置字段，可能存在字段已自动发现，但未由用户确认
                            "is_config_by_user": True,
                            # 字段名
                            "field_name": "hostname",
                            "updated_time": "2018-09-09 10:10:10",
                        }
                    ],
                    "result_table": new_table.table_id,
                }
            ],
        )

        # 先断言判断DataSource是否正确的拼接了Consul路径
        field_path = "{}_{}_{}/metadata/v1/default/data_id/{}/fields".format(
            settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, new_data_source.bk_data_id
        )
        assert new_data_source.consul_fields_path == field_path

        # 执行一次更新字段的逻辑
        new_data_source.update_field_config()

        # 判断是否正确的更新了字段： 存在字段信息 & 存在record_format但是未激活
        models.ResultTableField.objects.get(table_id=new_data_source.data_name, field_name="usage", field_type="float")

        models.ResultTableField.objects.get(
            table_id=new_data_source.data_name, field_name="hostname", field_type="string"
        )

        models.ResultTableRecordFormat.objects.get(
            table_id=new_data_source.data_name, metric="usage", dimension_list=json.dumps(["hostname"])
        )

        time_field = models.ResultTableField.objects.get(table_id=new_data_source.data_name, field_name="time")
        assert time_field.alias_name == "haha_time_field"

        # 激活record_format
        record = models.ResultTableRecordFormat.objects.get()
        record.set_metric_available()

        assert record.is_available

    @pytest.fixture
    def clean_init_influxdb_record(self):
        clusters = list(models.ClusterInfo.objects.all())
        models.ClusterInfo.objects.all().delete()
        models.InfluxDBHostInfo.objects.all().delete()
        models.InfluxDBClusterInfo.objects.all().delete()
        yield
        models.ClusterInfo.objects.all().delete()
        models.InfluxDBHostInfo.objects.all().delete()
        models.InfluxDBClusterInfo.objects.all().delete()
        models.ClusterInfo.objects.bulk_create(clusters)

    def test_init_influxdb_config(self, mocker, clean_init_influxdb_record):
        """测试influxdb的配置初始化能力"""
        # 写入环境变量
        os.environ["BK_MONITOR_INFLUXDB_PORT"] = "5290"
        for index in range(2):
            host_name = "BK_INFLUXDB_BKMONITORV3_IP%s" % index
            os.environ[host_name] = "127.0.0.%s" % index

        os.environ["BK_INFLUXDB_PROXY_HOST"] = "test.influxdb.name"
        os.environ["BK_INFLUXDB_PROXY_PORT"] = "10203"

        os.environ["BK_MONITOR_ES7_REST_PORT"] = "10004"
        os.environ["BK_MONITOR_ES7_HOST"] = "test.es7.name"
        os.environ["BK_MONITOR_ES7_USER"] = "username"
        os.environ["BK_MONITOR_ES7_PASSWORD"] = "password"

        os.environ["BK_MONITOR_KAFKA_HOST"] = "test.kafka.name"
        os.environ["BK_MONITOR_KAFKA_PORT"] = "9200"

        # 调用配置初始化命令
        call_command("sync_cluster_config")

        # 判断已经存在初始化配置
        # 判断influxdb backend 存在
        assert models.InfluxDBClusterInfo.objects.filter(cluster_name="default").count() == 2
        assert models.InfluxDBHostInfo.objects.all().count() == 2
        ip0 = models.InfluxDBHostInfo.objects.get(host_name="INFLUXDB_IP0")
        assert ip0.domain_name == "127.0.0.0"
        ip1 = models.InfluxDBHostInfo.objects.get(host_name="INFLUXDB_IP1")
        assert ip1.domain_name == "127.0.0.1"

        # 判断cluster集群都存在
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_INFLUXDB, is_default_cluster=True
            ).count()
            == 1
        )
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_ES, is_default_cluster=True, version="7.2"
            ).count()
            == 1
        )
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_KAFKA, is_default_cluster=True
            ).count()
            == 1
        )

        # 再次调用
        call_command("sync_cluster_config")

        # 判断没有任何新增的内容
        assert models.InfluxDBClusterInfo.objects.filter(cluster_name="default").count() == 2
        assert models.InfluxDBHostInfo.objects.all().count() == 2

        # 判断cluster集群信息依然是唯一的
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_INFLUXDB, is_default_cluster=True
            ).count()
            == 1
        )
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_ES, is_default_cluster=True
            ).count()
            == 1
        )
        assert (
            models.ClusterInfo.objects.filter(
                ~Q(domain_name=""), cluster_type=models.ClusterInfo.TYPE_KAFKA, is_default_cluster=True
            ).count()
            == 1
        )

    def test_consul_hash_function(self, mocker):
        """测试consul对于同样内容是否有重复写入的问题"""
        test_storage_dict = {}

        test_value = {"1": 1, "2": [1, 2, {1: 3}], "3": "123"}

        def _save(key, value):
            test_storage_dict[key] = {
                "CreateIndex": 438,
                "Flags": 0,
                "Key": key,
                "LockIndex": 0,
                "ModifyIndex": 3634,
                "Value": value,
            }

        def _get(key):
            value = test_storage_dict.get(key)
            return 1, value

        put_method = mocker.patch("consul.base.Consul.KV.put", return_value=True, side_effect=_save)

        mocker.patch("consul.base.Consul.KV.get", return_value=True, side_effect=_get)

        tools = consul_tools.HashConsul()
        tools.put(key="test", value=test_value)
        tools.put(key="test", value=test_value)
        put_method.assert_called_once_with(key="test", value=json.dumps(test_value))

        put_method.reset_mock()
        tools.put(key="test", value={})
        put_method.assert_called_once_with(key="test", value=json.dumps({}))

    def test_cluster_info(self):
        """测试集群写入、修改和查询能力"""
        try:
            # 类型不支持
            cluster = models.ClusterInfo.create_cluster(
                cluster_name="test_cluster",
                cluster_type="influxdb",
                domain_name="haha.domain",
                port=123,
                registered_system="test",
                operator="system",
            )
            assert cluster.username == ""
            assert cluster.creator == "system"
            assert cluster.last_modify_time.strftime("%H%M%S") == cluster.create_time.strftime("%H%M%S")
            last_modify_time = cluster.last_modify_time

            with pytest.raises(ValueError):
                # 类型不支持
                models.ClusterInfo.create_cluster(
                    cluster_name="test_cluster",
                    cluster_type="influxDB",
                    domain_name="haha.domain",
                    port=123,
                    registered_system="test",
                    operator="system",
                )

            with pytest.raises(ValueError):
                # 重复的集群名
                models.ClusterInfo.create_cluster(
                    cluster_name="test_cluster",
                    cluster_type="influxdb",
                    domain_name="haha.domain",
                    port=123,
                    registered_system="test",
                    operator="system",
                )

            with pytest.raises(ValueError):
                # 重复的域名端口信息
                models.ClusterInfo.create_cluster(
                    cluster_name="test_cluster123",
                    cluster_type="influxdb",
                    domain_name="haha.domain",
                    port=123,
                    registered_system="test",
                    operator="system",
                )

            # 修改正常
            cluster.modify(username="haha_user", operator="other_system")

            cluster.refresh_from_db()
            assert cluster.username == "haha_user"
            assert cluster.last_modify_user == "other_system"
            assert cluster.last_modify_time != last_modify_time

        finally:
            models.ClusterInfo.objects.filter(cluster_name="test_cluster").delete()

    def test_event(self, mocker, mock_outer_ralay, create_and_delete_record):
        # 1. 准备工作
        new_data_source = models.DataSource.create_data_source(
            data_name=self.data_name,
            etl_config="bk_standard_v2_event",
            operator=self.operator,
            source_label=self.data_source_label,
            type_label=self.data_type_label,
        )

        # 将所有的创建操作mock为成功
        mocker.patch("elasticsearch5.client.indices.IndicesClient.create", return_value=True)

        index_item = {
            "indices": {
                "v2_1_bkmonitor_event_{}_{}_0".format(
                    new_data_source.bk_data_id, datetime.datetime.now().strftime("%Y%m%d")
                ): {"primaries": {"store": {"size_in_bytes": 566}}}
            }
        }

        # mock成能够找到目标index的场景
        mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", return_value=index_item)

        mocker.patch("elasticsearch5.client.indices.IndicesClient.get_alias", side_effect=elasticsearch5.NotFoundError)

        mocker.patch("elasticsearch5.client.indices.IndicesClient.update_aliases", return_value={"acknowledged": True})

        mocker.patch("metadata.models.ESStorage.is_index_enable", return_value=True)

        # 创建事件分组
        new_group = models.EventGroup.create_event_group(
            bk_data_id=new_data_source.bk_data_id,
            bk_biz_id=1,
            event_group_name="test_group_name",
            label="applications",
            operator="admin",
            event_info_list=[
                {
                    "event_name": "custom_event_name",
                    "dimension_list": ["dimension_one", "dimension_one", "dimension_two"],
                }
            ],
        )

        # 判断是否正确的获取事件信息
        assert models.Event.objects.filter(event_group_id=new_group.event_group_id).count() == 1
        # 判断维度记录是否正确
        assert set(models.Event.objects.get(event_group_id=new_group.event_group_id).dimension_list) == {
            "dimension_one",
            "dimension_two",
            "target",
        }
        # 测试option是否到位
        assert models.DataSourceOption.get_option(query_id=new_data_source.bk_data_id)["timestamp_precision"] == "ms"
        # 测试字段ID是否正常
        assert models.ResultTableOption.get_option(query_id=new_group.table_id)["es_unique_field_list"] == [
            "event",
            "target",
            "dimensions",
            "event_name",
            "time",
        ]

        assert models.ESStorage.objects.all()[0].index_body == {
            "mappings": {
                "1_bkmonitor_event_1500001": {
                    "dynamic_templates": [
                        {"discover_dimension": {"mapping": {"type": "keyword"}, "path_match": "dimensions.*"}}
                    ],
                    "properties": {
                        "dimensions": {"dynamic": True, "type": "object"},
                        "event": {
                            "properties": {"content": {"type": "text"}, "count": {"type": "integer"}},
                            "type": "object",
                        },
                        "event_name": {"type": "keyword"},
                        "target": {"type": "keyword"},
                        "time": {"format": "epoch_millis", "type": "date_nanos"},
                    },
                }
            },
            "settings": {"number_of_replicas": 1, "number_of_shards": 1},
        }

        # 测试是否正确的从ES获取了对应的结果
        def dynamic_search(body, *args, **kwargs):
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

        mocker.patch("elasticsearch5.client.Elasticsearch.search", side_effect=dynamic_search)
        new_group.update_event_dimensions_from_es()
        # 判断是否正确的获取时间信息
        assert models.Event.objects.filter(event_group_id=new_group.event_group_id).count() == 2
        event = models.Event.objects.get(event_group_id=new_group.event_group_id, event_name="login")
        assert set(event.dimension_list) == {"module", "set", "log_path", "target"}
        assert new_group.table_id == "{}_bkmonitor_event_{}".format(new_group.bk_biz_id, new_group.bk_data_id)

        # 测试不可以同一个数据源注册到多个事件上
        with pytest.raises(ValueError):
            models.EventGroup.create_event_group(
                bk_data_id=new_data_source.bk_data_id,
                bk_biz_id=1,
                event_group_name="test_group_name",
                label="applications",
                operator="admin",
                event_info_list=[
                    {
                        "event_name": "custom_event_name",
                        "dimension_list": ["dimension_one", "dimension_one", "dimension_two"],
                    }
                ],
            )

        # 检查全业务的事件源table_id是否符合预期
        new_data_source = models.DataSource.create_data_source(
            data_name="new_data_name",
            etl_config="bk_standard_v2_event",
            operator=self.operator,
            source_label=self.data_source_label,
            type_label=self.data_type_label,
        )

        # 此时由于是全业务的注册，index名需要去掉业务ID
        index_item = {
            "indices": {
                "v2_bkmonitor_event_{}_{}_0".format(
                    new_data_source.bk_data_id, datetime.datetime.now().strftime("%Y%m%d")
                ): {"primaries": {"store": {"size_in_bytes": 566}}}
            }
        }
        mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", return_value=index_item)

        new_group = models.EventGroup.create_event_group(
            bk_data_id=new_data_source.bk_data_id,
            bk_biz_id=0,
            event_group_name="test_group_name",
            label="applications",
            operator="admin",
            event_info_list=[
                {
                    "event_name": "custom_event_name",
                    "dimension_list": ["dimension_one", "dimension_one", "dimension_two"],
                }
            ],
        )

        assert new_group.table_id == "bkmonitor_event_{}".format(new_group.bk_data_id)

    def test_time_series(self, mocker, mock_outer_ralay, patch_redis_tools, create_and_delete_record):
        # 1. 准备工作

        new_data_source = models.DataSource.create_data_source(
            data_name=self.data_name,
            etl_config="bk_standard_v2_time_series",
            operator=self.operator,
            source_label=self.data_source_label,
            type_label=self.data_type_label,
        )

        # 创建事件分组
        new_group = models.TimeSeriesGroup.create_custom_group(
            bk_data_id=new_data_source.bk_data_id,
            bk_biz_id=1,
            custom_group_name="test_group_name",
            label="applications",
            operator="admin",
        )

        # 判断是否正确的获取事件信息
        assert models.TimeSeriesGroup.objects.filter(time_series_group_id=new_group.time_series_group_id).count() == 1
        # 测试option是否到位
        assert models.DataSourceOption.get_option(query_id=new_data_source.bk_data_id)["timestamp_precision"] == "ms"

        assert models.InfluxDBStorage.objects.all()[0].table_id == new_group.table_id

        # 测试consul更新能力
        if not IS_CONSUL_MOCK:
            consul_client = consul.BKConsul()
            consul_client.kv.put(
                key="/".join([new_group.metric_consul_path, "field1"]), value=json.dumps(["tag1", "tag2"])
            )

            new_group.update_time_series_metric_from_consul()

            # 验证有对应的metric记录
            assert models.TimeSeriesMetric.objects.all().count() == 1
            time_series_metric = models.TimeSeriesMetric.objects.get()
            assert time_series_metric.field_name == "field1"
            assert set(time_series_metric.tag_list) == {"tag2", "tag1", "target"}

            assert models.ResultTableField.objects.all().count() == 5
            models.ResultTableField.objects.get(field_name="field1", tag=models.ResultTableField.FIELD_TAG_METRIC)
            models.ResultTableField.objects.get(field_name="tag2", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
            models.ResultTableField.objects.get(field_name="tag1", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
            models.ResultTableField.objects.get(field_name="target", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
            models.ResultTableField.objects.get(field_name="time", tag=models.ResultTableField.FIELD_TAG_TIMESTAMP)

        new_data_source = models.DataSource.create_data_source(
            data_name="new_data_name",
            etl_config="bk_standard_v2_time_series",
            operator=self.operator,
            source_label=self.data_source_label,
            type_label=self.data_type_label,
        )
        new_group = models.TimeSeriesGroup.create_custom_group(
            bk_data_id=new_data_source.bk_data_id,
            bk_biz_id=0,
            custom_group_name="test_group_name",
            label="applications",
            operator="admin",
        )
        assert new_group.table_id == "bkmonitor_time_series_{}.__default__".format(new_group.bk_data_id)

    def test_es_storage(self, mocker, create_and_delete_record):
        """
        测试对es storage的新增，更新，清理逻辑
        """
        now_datetime = datetime.datetime.utcnow()

        date_format = "%Y%m%d%H"
        now_datetime_str = now_datetime.strftime(date_format)
        # 将所有的创建操作mock为成功
        mock_es_create = mocker.patch("elasticsearch5.client.indices.IndicesClient.create", return_value=True)

        index_item = [{"indices": {"v2_index_test_2020070707_0": {"primaries": {"store": {"size_in_bytes": 566}}}}}]

        # mock成能够找到目标index的场景
        mock_es_stat = mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=index_item)

        mock_es_get_alias = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.get_alias", side_effect=elasticsearch5.NotFoundError
        )

        mock_es_update_alias = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.update_aliases", return_value={"acknowledged": True}
        )

        mocker.patch("metadata.models.ESStorage.is_index_enable", return_value=True)

        # 测试创建index及alias能力
        new_es_storage = models.ESStorage.create_table(
            table_id="index_test",
            date_format=date_format,
        )

        mock_es_create.assert_called_once_with(
            body={"settings": {}, "mappings": {"index_test": {"properties": {}}}},
            index=f"v2_index_test_{now_datetime.strftime(new_es_storage.date_format)}_0",
            params={"request_timeout": 30},
        )
        mock_es_stat.assert_called_once_with(f"v2_{new_es_storage.index_name}_*")

        mock_es_get_alias.assert_any_call(
            name=f"write_{now_datetime.strftime(new_es_storage.date_format)}_{new_es_storage.index_name}"
        )
        mock_es_update_alias.assert_any_call(
            body={
                "actions": [
                    {
                        "add": {
                            "index": f"v2_{new_es_storage.index_name}_2020070707_0",
                            "alias": f"write_{now_datetime_str}_{new_es_storage.index_name}",
                        }
                    },
                    {
                        "add": {
                            "index": f"v2_{new_es_storage.index_name}_2020070707_0",
                            "alias": f"{new_es_storage.index_name}_{now_datetime_str}_read",
                        }
                    },
                ]
            }
        )
        assert 2 == mock_es_update_alias.call_count

        # 测试更新逻辑
        # 调整mock的index大小，以触发分片
        new_es_storage.slice_size = 1
        index_item = [
            {"indices": {"v2_index_test_2020070707_0": {"primaries": {"store": {"size_in_bytes": 2147483648}}}}}
        ]

        # 刷新create计数
        mock_es_create = mocker.patch("elasticsearch5.client.indices.IndicesClient.create", return_value=True)

        # mock成能够找到目标index的场景
        mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=index_item)

        # mock掉is_mapping_same,这里只判断mapping相同的场景
        mocker.patch("metadata.models.ESStorage.is_mapping_same", return_value=True)

        # 执行更新流程
        new_es_storage.update_index_v2()

        # 和创建时的区别在于，新的index建立使用当前时间
        mock_es_create.assert_called_once_with(
            body={"settings": {}, "mappings": {"index_test": {"properties": {}}}},
            index=f"v2_index_test_{now_datetime.strftime(new_es_storage.date_format)}_0",
            params={"request_timeout": 30},
        )

    def test_es_reallocate_index(self, mocker, create_and_delete_record):
        date_format = "%Y%m%d%H"

        mocker.patch("elasticsearch5.client.indices.IndicesClient.create", return_value=True)

        index_item = [{"indices": {"v2_index_test_2020070707_0": {"primaries": {"store": {"size_in_bytes": 566}}}}}]
        mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=index_item)
        mocker.patch("elasticsearch5.client.indices.IndicesClient.get_alias", side_effect=elasticsearch5.NotFoundError)

        mocker.patch("elasticsearch5.client.indices.IndicesClient.update_aliases", return_value={"acknowledged": True})

        new_es_storage = models.ESStorage.create_table(
            table_id="index_test",
            date_format=date_format,
            warm_phase_days=3,
            warm_phase_settings={
                "allocation_attr_name": "bk_tag",
                "allocation_attr_value": "cold",
                "allocation_type": "include",
            },
        )

        mock_es_get_alias = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.get_alias",
            return_value={
                f"{new_es_storage.index_name}_2020010306_0": {
                    "aliases": {
                        f"{new_es_storage.index_name}_20200103_write": {},
                        f"write_2020010306_{new_es_storage.index_name}": {},
                    }
                },
            },
        )

        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.get_settings",
            return_value={
                f"{new_es_storage.index_name}_2020010306_0": {
                    "settings": {
                        "index": {
                            "number_of_shards": "5",
                            "provided_name": f"{new_es_storage.index_name}_2020010306_0",
                            "creation_date": "1596719538095",
                            "number_of_replicas": "1",
                            "uuid": "CQ4WG4fCRnaEnofju-447Q",
                            "version": {"created": "7080199"},
                        }
                    }
                }
            },
        )
        mocker.patch(
            "elasticsearch5.client.ClusterClient.state",
            return_value={
                "metadata": {
                    "indices": {
                        f"{new_es_storage.index_name}_2020010306_0": {
                            "state": "open",
                            "settings": {
                                "index": {
                                    "number_of_shards": "5",
                                    "provided_name": f"{new_es_storage.index_name}_2020010306_0",
                                    "creation_date": "1596719538095",
                                    "number_of_replicas": "1",
                                    "uuid": "CQ4WG4fCRnaEnofju-447Q",
                                    "version": {"created": "7080199"},
                                }
                            },
                        }
                    }
                }
            },
        )
        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.stats",
            return_value={
                "indices": {
                    f"{new_es_storage.index_name}_2020010306_0": {
                        "uuid": "CQ4WG4fCRnaEnofju-447Q",
                        "primaries": {"docs": {"count": 169, "deleted": 0}, "store": {"size_in_bytes": 647663}},
                        "total": {"docs": {"count": 338, "deleted": 0}, "store": {"size_in_bytes": 1295326}},
                    }
                }
            },
        )
        mock_es_put_settings = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.put_settings", return_value=True
        )

        new_es_storage.reallocate_index()
        mock_es_get_alias.assert_called_once()
        mock_es_put_settings.assert_called_once_with(
            index=f"{new_es_storage.index_name}_2020010306_0", body={"index.routing.allocation.include.bk_tag": "cold"}
        )

        new_es_storage.update_storage(
            warm_parse_days=0,
            warm_parse_settings={"allocation_attr_name": "", "allocation_attr_value": "", "allocation_type": "include"},
        )
        new_es_storage.reallocate_index()

    def test_es_clear_index(self, mocker, create_and_delete_record):
        date_format = "%Y%m%d%H"

        mocker.patch("elasticsearch5.client.indices.IndicesClient.create", return_value=True)

        index_item = [{"indices": {"v2_index_test_2020070707_0": {"primaries": {"store": {"size_in_bytes": 566}}}}}]
        mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=index_item)
        mocker.patch("elasticsearch5.client.indices.IndicesClient.get_alias", side_effect=elasticsearch5.NotFoundError)

        mocker.patch("elasticsearch5.client.indices.IndicesClient.update_aliases", return_value={"acknowledged": True})
        new_es_storage = models.ESStorage.create_table(table_id="index_test", date_format=date_format, retention=3)
        now_datetime = datetime.datetime.utcnow()
        datetime0_str = (now_datetime - datetime.timedelta(days=4)).strftime(date_format)
        datetime1_str = (now_datetime - datetime.timedelta(days=3)).strftime(date_format)
        datetime2_str = (now_datetime - datetime.timedelta(days=2)).strftime(date_format)

        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.get_alias",
            return_value={
                f"{new_es_storage.index_name}_2020010306_0": {
                    "aliases": {
                        f"{new_es_storage.index_name}_{datetime0_str}_write": {},
                        f"write_{datetime2_str}_{new_es_storage.index_name}": {},
                    }
                },
                f"{new_es_storage.index_name}_2020010305_0": {
                    "aliases": {f"{new_es_storage.index_name}_{datetime1_str}_write": {}}
                },
                f"{new_es_storage.index_name}_2020010304_0": {
                    "aliases": {f"{new_es_storage.index_name}_{datetime0_str}_write": {}}
                },
                f"{new_es_storage.index_name}_2020010303_0": {"aliases": {"invalid_alias": {}}},
            },
        )

        mock_es_delete = mocker.patch("elasticsearch5.client.indices.IndicesClient.delete", return_value=True)
        mock_es_delete_alias = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.delete_alias", return_value=True
        )

        new_es_storage.clean_index_v2()

        mock_es_delete_alias.assert_called_once_with(
            index=f"{new_es_storage.index_name}_2020010306_0", name=f"{new_es_storage.index_name}_{datetime0_str}_write"
        )
        mock_es_delete.assert_called_once_with(index=f"{new_es_storage.index_name}_2020010304_0")
