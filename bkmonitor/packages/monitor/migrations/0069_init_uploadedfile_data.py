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

import os

from django.db import connections, migrations

from common.log import logger


def __dictfetchall(cursor):
    # Returns all rows from a cursor as a dict
    desc = cursor.description
    return [dict(list(zip([col[0] for col in desc], row))) for row in cursor.fetchall()]


def init_uploaded_file_data(apps, schema_editor):
    dataapi_connection = getattr(connections, "dataapi", None)
    if not dataapi_connection:
        return
    try:
        with dataapi_connection.cursor() as cursor:
            cursor.execute("select * from collector_user_file")
            data = __dictfetchall(cursor)
    except Exception as e:
        logger.exception("迁移 dataapi 文件上传数据发生异常：%s" % e)
        return
    UploadedFile = apps.get_model("monitor", "UploadedFile")
    for item in data:
        absolute_path, actual_filename = os.path.split(item["file_path"])
        relative_path = os.path.normpath(absolute_path.split("/dataapi/media/")[-1].strip("/"))
        params = {
            "id": item["id"],
            "create_user": item["user_name"],
            "update_user": item["user_name"],
            "relative_path": relative_path,
            "actual_filename": actual_filename,
            "original_filename": actual_filename,
            "file_data": os.path.join(relative_path, actual_filename).replace("\\", "/"),
        }
        UploadedFile.objects.create(**params)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0068_auto_20190315_1628"),
    ]

    operations = [migrations.RunPython(init_uploaded_file_data)]
