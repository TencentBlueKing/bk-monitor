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
from unittest import mock

import django
import pytest

from apm.constants import ConfigTypes
from apm.core.application_config import ApmConfigCache, ApplicationConfig
from apm.models import ApmApplication, AppConfigBase, NormalTypeValueConfig
from apm.resources import ReleaseAppConfigResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "test_drop_fields"
APP_ALIAS = "test_drop_fields"
DESCRIPTION = "drop fields test"
DROP_FIELD = "attributes.upstream_cluster.name"

USER_DB_CONFIG = {
    "cut": [
        {
            "predicate_key": "attributes.db.system",
            "match": ["Mysql"],
            "keys": ["attributes.db.statement"],
            "max_length": 1000,
        }
    ],
    "drop": [
        {
            "predicate_key": "attributes.db.system",
            "match": ["Mysql"],
            "keys": ["attributes.db.parameters"],
        }
    ],
}


def setup_drop_fields_config(bk_biz_id, app_name, drop_fields):
    NormalTypeValueConfig.refresh_config(
        bk_biz_id,
        app_name,
        AppConfigBase.APP_LEVEL,
        app_name,
        [{"type": ConfigTypes.DROP_FIELDS_CONFIG, "value": json.dumps(drop_fields)}],
        need_delete_config=False,
    )


@pytest.mark.django_db(databases="__all__")
class TestDropFieldsConfig(django.test.TestCase):
    databases = {
        "default",
        "monitor_api",
    }

    def setUp(self):
        ApmApplication.objects.create(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, app_alias=APP_ALIAS, description=DESCRIPTION
        )

    def _release_db_config(self):
        mock.patch("apm.task.tasks.refresh_apm_application_config", return_value=None).start()
        ReleaseAppConfigResource().perform_request(
            {
                "bk_biz_id": BK_BIZ_ID,
                "app_name": APP_NAME,
                "instance_name_config": [],
                "custom_service_config": [],
                "db_config": USER_DB_CONFIG,
            }
        )

    def test_backend_drop_fields_preserved_when_user_updates_db_config(self):
        setup_drop_fields_config(BK_BIZ_ID, APP_NAME, [DROP_FIELD, DROP_FIELD])
        self._release_db_config()

        drop_fields_value = NormalTypeValueConfig.get_app_value(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, config_type=ConfigTypes.DROP_FIELDS_CONFIG
        )
        db_config_value = NormalTypeValueConfig.get_app_value(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, config_type=ConfigTypes.DB_CONFIG
        )

        assert json.loads(drop_fields_value) == [DROP_FIELD, DROP_FIELD]
        assert json.loads(db_config_value) == USER_DB_CONFIG

    def test_drop_fields_merged_when_application_config_is_built(self):
        setup_drop_fields_config(BK_BIZ_ID, APP_NAME, [DROP_FIELD])
        self._release_db_config()

        application = ApmApplication.objects.get(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        attribute_config = ApplicationConfig(application).get_application_config()["attribute_config"]

        assert USER_DB_CONFIG["drop"][0] in attribute_config["drop"]
        assert {"predicate_key": DROP_FIELD, "keys": [DROP_FIELD]} in attribute_config["drop"]
        assert attribute_config["drop"].count({"predicate_key": DROP_FIELD, "keys": [DROP_FIELD]}) == 1

    def test_drop_fields_merged_on_periodic_refresh_with_config_cache(self):
        setup_drop_fields_config(BK_BIZ_ID, APP_NAME, [DROP_FIELD])
        self._release_db_config()

        application = ApmApplication.objects.get(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        attribute_config = ApplicationConfig(application, ApmConfigCache()).get_application_config()["attribute_config"]

        assert USER_DB_CONFIG["drop"][0] in attribute_config["drop"]
        assert {"predicate_key": DROP_FIELD, "keys": [DROP_FIELD]} in attribute_config["drop"]
