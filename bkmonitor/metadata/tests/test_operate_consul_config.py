"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import time

import pytest
from django.core.management import call_command

from bkmonitor.utils import consul
from metadata import models
from metadata.utils import consul_tools

pytestmark = pytest.mark.django_db(databases="__all__")
IS_CONSUL_MOCK = False
es_index = {}
DEFAULT_NAME = "test_query.base"
DEFAULT_NAME_ONE = "cluster_name_one"
DEFAULT_MQ_CLUSTER_ID = 20000
DEFAULT_MQ_CLUSTER_ID_ONE = 20001
DEFAULT_MQ_CONFIG_ID = 20001


class CustomBKConsul:
    def __init__(self):
        self.kv = CustomKV()

    def put(self, *args, **kwargs):
        return True


class CustomKV:
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


@pytest.fixture()
def clean_record(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", return_value=CustomBKConsul())
    mocker.patch("django.dispatch.dispatcher.Signal.send", return_value=True)
    datasource_list = list(models.DataSource.objects.all())
    models.DataSource.objects.all().delete()
    yield
    models.DataSource.objects.filter(bk_data_id=1500001).delete()
    models.KafkaTopicInfo.objects.filter(bk_data_id=1500001).delete()
    models.DataSource.objects.bulk_create(datasource_list)


class TestOperateConsulConfig:
    def test_redirect_consul_config(self, mocker, clean_record):
        # ===================== mock start ===========================
        # mock gse 请求接口依赖
        base_channel_id = 1500000

        def gen_channel_id(*args, **kwargs):
            nonlocal base_channel_id
            base_channel_id += 1
            return {"channel_id": base_channel_id}

        mocker.patch("core.drf_resource.api.gse.add_route", side_effect=gen_channel_id)

        mocker.patch("metadata.models.DataSource.create_mq", return_value=True)
        mocker.patch("metadata.models.DataSource.refresh_gse_config", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_database", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_rp", return_value=True)
        mocker.patch("metadata.models.KafkaStorage.ensure_topic", return_value=True)
        mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay", return_value=True)
        # ==================== mock end ===============================

        # 该测试只做实际场景测试
        if IS_CONSUL_MOCK:
            return
        data_name = f"test_name_{time.time()}"
        etl_config = "bk_standard"
        operator = "admin"
        data_source_label = "bk_monitor"
        data_type_label = "time_series"
        hash_consul = consul_tools.HashConsul()
        consul_client = consul.BKConsul(
            host=hash_consul.host, port=hash_consul.port, scheme=hash_consul.scheme, verify=hash_consul.verify
        )
        # 新建一个datasource
        new_data_source = models.DataSource.create_data_source(
            data_name=data_name,
            etl_config=etl_config,
            operator=operator,
            source_label=data_source_label,
            type_label=data_type_label,
        )
        # 检查consul数据，确认配置成功处理
        result = consul_client.kv.get(new_data_source.consul_config_path)
        assert result[1] is not None
        # 手动传入redirect命令，将配置重定向到新路径下
        call_command("redirect_datasource", data_id=[new_data_source.bk_data_id], target_type="temp")
        # 检查旧路径consul数据
        result = consul_client.kv.get(new_data_source.consul_config_path)
        assert result[1] is None
        # 更新model实例
        new_data_source = models.DataSource.objects.get(pk=new_data_source.bk_data_id)
        # 检查新路径consul数据
        result = consul_client.kv.get(new_data_source.consul_config_path)
        assert result[1] is not None
        # 手动删除新路径下的consul数据
        consul_client.kv.delete(new_data_source.consul_config_path)
        result = consul_client.kv.get(new_data_source.consul_config_path)
        assert result[1] is None
        # 调用clean命令
        call_command("clean_old_consul_config")
        # 检查新路径下数据是否恢复
        result = consul_client.kv.get(new_data_source.consul_config_path)
        assert result[1] is not None
