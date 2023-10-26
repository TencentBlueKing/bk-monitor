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
from bk_audit.client import BkAudit
from bk_audit.contrib.django.formatters import DjangoFormatter
from bk_audit.contrib.opentelemetry.exporters import OTLogExporter
from bk_audit.contrib.opentelemetry.utils import ServiceNameHandler
from django.conf import settings

# LoggerExporter 为可选项用于 DEBUG 使用
bk_audit_client = BkAudit(
    settings.APP_CODE,
    settings.SECRET_KEY,
    {"formatter": DjangoFormatter(), "exporters": [OTLogExporter()], "service_name_handler": ServiceNameHandler},
)
