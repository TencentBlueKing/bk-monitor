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
from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--bk_env", type=str, help="来源蓝鲸环境(o.bk.tencent.com)", dest="bk_env", required=True)
        parser.add_argument("--old_bk_biz_id", type=int, help="旧业务ID", dest="old_bk_biz_id", required=True)
        parser.add_argument("--new_bk_biz_id", type=int, help="新业务ID", dest="new_bk_biz_id", required=True)
        parser.add_argument("--mysql_host", type=str, help="mysql host", dest="mysql_host", required=True)
        parser.add_argument("--mysql_password", type=str, help="mysql password", dest="mysql_password", required=True)
        parser.add_argument("--mysql_database", type=str, help="mysql database", dest="mysql_database", required=True)
        parser.add_argument("--mysql_port", type=int, default=3306, help="mysql port", dest="mysql_port", required=True)
        parser.add_argument("--mysql_user", type=str, help="mysql user", dest="mysql_user", default="root")

    def handle(self, **kwargs):
        from config_migrate.migrate import ConfigMigrator

        from bkmonitor.utils.local import local

        local.username = "admin"

        bk_env = kwargs["bk_env"]
        old_bk_biz_id = kwargs["old_bk_biz_id"]
        new_bk_biz_id = kwargs["new_bk_biz_id"]

        mysql_config = {
            "host": kwargs["mysql_host"],
            "port": kwargs["mysql_port"],
            "user": kwargs["mysql_user"],
            "password": kwargs["mysql_password"],
            "database": kwargs["mysql_database"],
        }
        migrator = ConfigMigrator(bk_env, old_bk_biz_id, new_bk_biz_id, mysql_config)
        migrator.upload_config(f"/app/migrate/config_{old_bk_biz_id}.tar.gz")
        migrator.migrate()
