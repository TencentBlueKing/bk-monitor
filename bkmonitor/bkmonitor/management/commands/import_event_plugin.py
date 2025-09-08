# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# 导入事件源插件
# 使用方法
# source bin/environ.sh && DJANGO_CONF_MODULE=conf.api.production.enterprise \
# python manage.py import_event_plugin test.tar.gz

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from core.drf_resource import resource
from core.drf_resource.contrib import nested_api


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("src_path", type=str, help="the source package path")

    def handle(self, **kwargs):
        # 先切换 API Mode，因为直接调用会报错
        api_mode = nested_api.IS_API_MODE
        nested_api.IS_API_MODE = False

        try:
            src_path = kwargs["src_path"]
            print("package to import: {}".format(src_path))
            with open(src_path, "rb") as tar_obj:
                file_data = SimpleUploadedFile("plugin.tar.gz", tar_obj.read())
                plugin = resource.event_plugin.create_event_plugin(bk_biz_id=0, file_data=file_data, force_update=True)
            print("import success, plugin_id({})".format(plugin["plugin_id"]))
        finally:
            nested_api.IS_API_MODE = api_mode
