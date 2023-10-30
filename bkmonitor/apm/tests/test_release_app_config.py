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
import json
import django
import mock
import pytest
from apm.constants import ConfigTypes
from apm.models import ApmApplication, LicenseConfig, NormalTypeValueConfig, ProbeConfig
from apm.resources import ReleaseAppConfigResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"


@pytest.mark.django_db
class TestReleaseAppConfig(django.test.TestCase):
    databases = {
        'default',
        'monitor_api',
    }

    def setUp(self):
        ApmApplication.objects.create(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, app_alias=APP_ALIAS, description=DESCRIPTION
        )

    def test_license_config(self):
        param = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "instance_name_config": [],
            "custom_service_config": [],
            "license_config": {
                "enabled": False,
                "expire_time": 4102329600,
                "number_nodes": 1000000,
                "tolerable_expire": "1h",
                "tolerable_num_ratio": 1.0,
            },
        }

        mock.patch("apm.task.tasks.refresh_apm_application_config", return_value=None).start()

        obj = ReleaseAppConfigResource()

        obj.perform_request(param)

        data = LicenseConfig.get_application_license_config(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)

        assert isinstance(data, dict)

        assert data.get("expire_time") == param["license_config"]["expire_time"]

    def test_probe_config(self):
        param = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "instance_name_config": [],
            "custom_service_config": [],
            "probe_config": {
                "rules": [
                    {
                        "type": "Http",
                        "enable": False,
                        "name": "tonvi_rule2",
                        "target": "header",
                        "field": "Accept",
                        "prefix": "custom_tag",
                        "filters": [
                            {"field": "resource.service.name", "type": "service", "value": "order"},
                            {"field": "resource.service.name", "type": "service", "value": "account"},
                            {"field": "attributes.api_name", "type": "interface", "value": "POST:/order/create"},
                            {"field": "attributes.api_name", "type": "interface", "value": "POST:/account/pay"},
                        ],
                    }
                ],
                "sn": "1364b513cf040b4567e4f00f1bd2856d7a87091b",
            },
        }

        mock.patch("apm.task.tasks.refresh_apm_application_config", return_value=None).start()

        obj = ReleaseAppConfigResource()

        obj.perform_request(param)

        config = ProbeConfig.get_config(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)

        assert config.sn == param["probe_config"]["sn"]

    def test_db_slow_command_config(self):
        param = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "instance_name_config": [],
            "custom_service_config": [],
            "db_slow_command_config": {
                "destination": "db.is_slow",
                "rules": [
                    {"match": "mysql", "threshold": 500},
                    {"match": "postgresql", "threshold": 500},
                    {"match": "elasticsearch", "threshold": 500},
                    {"match": "oracle", "threshold": 500},
                    {"match": "redis", "threshold": 500},
                    {"match": "mangodb", "threshold": 500},
                    {"match": "cassandra", "threshold": 500},
                ],
            },
        }

        mock.patch("apm.task.tasks.refresh_apm_application_config", return_value=None).start()

        obj = ReleaseAppConfigResource()

        obj.perform_request(param)

        config_value = NormalTypeValueConfig.get_app_value(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, config_type=ConfigTypes.DB_SLOW_COMMAND_CONFIG
        )

        config = json.loads(config_value)

        assert config.get("destination") == param["db_slow_command_config"]["destination"]

    def test_db_config(self):
        param = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "instance_name_config": [],
            "custom_service_config": [],
            "db_config": {
                "cut": [
                    {
                        "predicate_key": "attributes.db.system",
                        "match": ["Mysql", "Postgresql", "Elasticsearch"],
                        "keys": ["attributes.db.statement"],
                        "max_length": 1000,
                    },
                    {
                        "predicate_key": "attributes.db.system",
                        "match": ["Redis", "Mangodb"],
                        "keys": ["attributes.db.statement"],
                        "max_length": 1000,
                    },
                ],
                "drop": [
                    {
                        "predicate_key": "attributes.db.system",
                        "match": ["Mysql", "Postgresql", "Elasticsearch"],
                        "keys": ["attributes.db.sql.parameters"],
                    },
                    {"predicate_key": "attributes.db.system", "match": ["Redis", "Mangodb"], "keys": []},
                ],
            },
        }

        mock.patch("apm.task.tasks.refresh_apm_application_config", return_value=None).start()

        obj = ReleaseAppConfigResource()

        obj.perform_request(param)

        config_value = NormalTypeValueConfig.get_app_value(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, config_type=ConfigTypes.DB_CONFIG
        )

        assert config_value is not None
