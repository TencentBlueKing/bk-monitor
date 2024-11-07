# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from copy import deepcopy

import mock
import pytest

from apm_web.models.application import Application

APP_NAME = "test_log_trace"
SUBSCRIPTION_ID = 1
OUTPUT_PARAM = {"token": "123", "host": "127.0.0.1"}
APPLICATION_ID = 1
API_APPLICATION = {
    "bk_biz_id": 2,
    "app_name": "test_log_trace",
    "application_id": APPLICATION_ID,
    "datasource_info": {
        "metric_config": {"bk_data_id": 1, "result_table_id": "2_test_log_trace", "time_series_group_id": 1},
        "trace_config": {"bk_data_id": 1, "result_table_id": "2_test_log_trace"},
    },
}

CREATE_APPLICATION = {
    "app_name": "test_log_trace",
    "app_alias": "test_log_trace",
    "description": "",
    "plugin_id": "log_trace",
    "deployment_ids": [],
    "language_ids": [],
    "datasource_option": {
        "es_storage_cluster": 3,
        "es_retention": 7,
        "es_number_of_replicas": 1,
        "es_shards": 3,
        "es_slice_size": 1,
    },
    "bk_biz_id": 2,
    "plugin_config": {
        "target_node_type": "INSTANCE",
        "target_object_type": "HOST",
        "target_nodes": [{"bk_host_id": 53}],
        "data_encoding": "UTF-8",
        "paths": ["/usr/local/test/test.log"],
    },
}
PLUGIN_CONFIG = {
    "target_node_type": "INSTANCE",
    "target_object_type": "HOST",
    "target_nodes": [{"bk_host_id": 48}],
    "data_encoding": "UTF-8",
    "paths": ["/usr/local/test/log"],
    "bk_data_id": 1,
    "bk_biz_id": 2,
    "subscription_id": 1,
}

SETUP = {
    "plugin_config": {
        "target_node_type": "INSTANCE",
        "target_nodes": [{"bk_host_id": 53}],
        "target_object_type": "HOST",
        "data_encoding": "UTF-8",
        "paths": ["/usr/local/test/test.log"],
        "bk_data_id": 1,
        "bk_biz_id": 2,
        "subscription_id": 1,
    },
    "application_id": APPLICATION_ID,
    "bk_biz_id": 2,
}


class TestLogTrace(object):
    @mock.patch("core.drf_resource.api.apm_api.create_application", lambda _: API_APPLICATION)
    @mock.patch("apm_web.models.Application.get_transfer_config", lambda _: {})
    @mock.patch("apm_web.models.Application.authorization", lambda _: {})
    @mock.patch("core.drf_resource.api.apm_api.release_app_config", lambda _: {})
    @mock.patch("apm_web.models.Application.get_output_param", lambda _: OUTPUT_PARAM)
    @mock.patch("apm_web.tasks.update_application_config.delay", lambda _: {})
    @mock.patch("core.drf_resource.api.node_man.create_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.switch_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.run_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @pytest.mark.django_db(transaction=True)
    def test_create_application(self):
        validated_request_data = deepcopy(CREATE_APPLICATION)
        result = Application.create_application(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=validated_request_data["app_alias"],
            description=validated_request_data["description"],
            plugin_id=validated_request_data["plugin_id"],
            deployment_ids=validated_request_data["deployment_ids"],
            language_ids=validated_request_data["language_ids"],
            datasource_option=validated_request_data["datasource_option"],
            plugin_config=validated_request_data["plugin_config"],
        )
        application = API_APPLICATION
        assert result.plugin_config == SETUP["plugin_config"]
        assert result.app_name == application["app_name"]
        assert result.application_id == application["application_id"]

    @mock.patch("apm_web.models.Application.get_output_param", lambda _: OUTPUT_PARAM)
    @mock.patch("core.drf_resource.api.node_man.update_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.run_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @pytest.mark.django_db(transaction=True)
    def test_setup(self, application_id=APPLICATION_ID):
        data = copy.deepcopy(PLUGIN_CONFIG)
        result = Application.update_plugin_config(application_id, data)
        assert result == data

    @mock.patch("core.drf_resource.api.node_man.update_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.switch_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.run_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @pytest.mark.django_db(transaction=True)
    def test_stop(self, application_id=APPLICATION_ID):
        result = Application.stop_plugin_config(application_id)
        assert result["subscription_id"] == SUBSCRIPTION_ID

    @mock.patch("core.drf_resource.api.node_man.switch_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.run_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @pytest.mark.django_db(transaction=True)
    def test_start(self, application_id=APPLICATION_ID):
        result = Application.start_plugin_config(application_id)
        assert result["subscription_id"] == SUBSCRIPTION_ID

    @mock.patch("core.drf_resource.api.node_man.switch_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.run_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @mock.patch("core.drf_resource.api.node_man.delete_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @pytest.mark.django_db(transaction=True)
    def test_delete(self, application_id=APPLICATION_ID):
        result = Application.delete_plugin_config(application_id)
        assert result["subscription_id"] == SUBSCRIPTION_ID
