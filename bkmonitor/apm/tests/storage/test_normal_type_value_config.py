# -*- coding: utf-8 -*-
import json

import django
import pytest

from apm.constants import DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG, ConfigTypes
from apm.core.application_config import ApplicationConfig
from apm.models import ApmApplication, NormalTypeValueConfig

pytestmark = pytest.mark.django_db


BK_BIZ_ID = 2
APP_NAME = "test_res_demo"
APP_ALIAS = "test_res_demo"
DESCRIPTION = "this is demo"
CONFIG_LEVEL = "app_level"
CONFIG_KEY = "test_res_demo"


DB_SLOW_COMMAND_CONFIG = {
    "destination": "db.is_slow",
    "rules": [{"match": "Mysql", "threshold": 100}, {"match": "Redis", "threshold": 10}],
}


@pytest.mark.django_db
class TestReleaseAppConfig(django.test.TestCase):

    databases = {
        'default',
        'monitor_api',
    }

    def test_db_slow_command_config(self):
        ApmApplication.objects.create(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, app_alias=APP_ALIAS, description=DESCRIPTION
        )

        type_value_config = {"type": ConfigTypes.DB_SLOW_COMMAND_CONFIG, "value": json.dumps(DB_SLOW_COMMAND_CONFIG)}
        NormalTypeValueConfig.refresh_config(
            BK_BIZ_ID, APP_NAME, CONFIG_LEVEL, CONFIG_KEY, [type_value_config], need_delete_config=False
        )

        queryset = NormalTypeValueConfig.objects.filter(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, type=ConfigTypes.DB_SLOW_COMMAND_CONFIG
        )
        assert queryset.count() == 1

        json_value = NormalTypeValueConfig.get_app_value(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, config_type=ConfigTypes.DB_SLOW_COMMAND_CONFIG
        )

        value = json.loads(json_value)

        assert DB_SLOW_COMMAND_CONFIG["destination"] == value.get("destination", "")

        _app = ApmApplication.objects.get(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        app_config = ApplicationConfig(_app)
        res = app_config.get_config(
            config_type=ConfigTypes.DB_SLOW_COMMAND_CONFIG, config=DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG
        )

        assert res.get("destination") == DB_SLOW_COMMAND_CONFIG["destination"]

        ApmApplication.objects.all().delete()
        NormalTypeValueConfig.objects.filter().delete()
