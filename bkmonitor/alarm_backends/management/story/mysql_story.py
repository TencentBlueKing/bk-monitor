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
from django.conf import settings
from django.db import connection

from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    register_step,
    register_story,
)


@register_story()
class MysqlStory(BaseStory):
    name = "Mysql Healthz Check"


@register_step(MysqlStory)
class TableSpace(CheckStep):
    name = "check table space"

    # 表空间占用预警100G
    warning_space = 100 * 1024
    # 自增ID 18亿 预警
    problem_increased_id_limit = 18000 * 10000 * 10

    def check(self):
        backend_database_name = settings.DATABASES[settings.BACKEND_DATABASE_NAME]["NAME"]

        p_list = []
        cursor = connection.cursor()
        # get Size with MB
        cursor.execute(
            """SELECT
        table_name AS `table`,
        round(((data_length + index_length) / 1024 / 1024), 2) `size`, TABLE_ROWS as `rows`,
        `AUTO_INCREMENT` AS `auto_increment`
        FROM information_schema.TABLES
        WHERE table_schema = "{}"
        order by `size` desc""".format(
                backend_database_name
            )
        )  # noqa
        columns = [col[0] for col in cursor.description]
        self.story.warning("table space top10: ")

        log_index = 0
        for row in cursor.fetchall():
            info = dict(list(zip(columns, row)))
            space_size = info["size"]
            func = self.story.info
            if space_size > self.warning_space:
                func = self.story.warning

            if info["auto_increment"] and info["auto_increment"] > self.problem_increased_id_limit:
                cursor.execute(
                    f"""
                    select COLUMN_TYPE from information_schema.COLUMNS
                    where table_name="{info['table']}" and table_schema="{backend_database_name}"
                    and COLUMN_KEY="PRI";
                    """
                )
                for row in cursor.fetchall():
                    # 检测是否为INT(11)，如果是的话则告警
                    if row[0] == "int(11)":
                        p_list.append(
                            IncresedIdProblem(
                                f"{info['table']}: auto increased id too big, now up to: [{info['auto_increment']}]",
                                self.story,
                            )
                        )
            if log_index < 10:
                func(
                    f"{info['table']}: {info['size']}MB rows: [{info['rows']}] "
                    f"increased_id_up_to: [{info['auto_increment']}]"
                )  # noqa
            log_index += 1

        return p_list


class IncresedIdProblem(Problem):
    def position(self):
        self.story.warning("建议：自增ID已达到预警线: 18亿, 请联系管理员处理")
