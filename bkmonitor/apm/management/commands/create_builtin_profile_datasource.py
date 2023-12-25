"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging

from django.core.management import BaseCommand

from apm.models.datasource import ProfileDataSource

logger = logging.getLogger("apm")


class Command(BaseCommand):
    help = "create builtin profile datasource"

    def handle(self, *args, **options):
        if ProfileDataSource.get_builtin_source():
            logger.info("builtin datasource already exists, noting to do.")
            return

        try:
            ProfileDataSource.create_builtin_source()
        except Exception:  # pylint: disable=broad-except
            logger.exception("create builtin datasource failed")
            return

        logger.info(
            f"create builtin datasource success, "
            f"biz_id: {ProfileDataSource.get_builtin_source().bk_biz_id}, "
            f"app_name: {ProfileDataSource.get_builtin_source().app_name}, "
            f"data id: {ProfileDataSource.get_builtin_source().bk_data_id}, "
            f"result_table_id: {ProfileDataSource.get_builtin_source().result_table_id}"
        )
