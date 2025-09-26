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


from django.apps import AppConfig, apps


class MetaDataAppConfig(AppConfig):

    name = "metadata"

    def ready(self):
        # 使得信号配置生效
        from metadata import signals  # noqa

        # 进行一些赋值，防止在app没有准备好时就赋值
        from metadata.models import data_source

        data_source.ResultTable = apps.get_model("metadata", "ResultTable")
        data_source.ResultTableField = apps.get_model("metadata", "ResultTableField")
        data_source.ResultTableRecordFormat = apps.get_model("metadata", "ResultTableRecordFormat")
        data_source.ResultTableOption = apps.get_model("metadata", "ResultTableOption")

        from metadata.models import storage

        storage.ResultTableField = apps.get_model("metadata", "ResultTableField")
        storage.ResultTableFieldOption = apps.get_model("metadata", "ResultTableFieldOption")
        storage.ResultTable = apps.get_model("metadata", "ResultTable")
        storage.EventGroup = apps.get_model("metadata", "EventGroup")

        from metadata.models import custom_report

        custom_report.DataSource = apps.get_model("metadata", "DataSource")
