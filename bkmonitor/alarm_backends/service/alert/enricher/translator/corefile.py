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
from django.utils.translation import gettext as _

from alarm_backends.service.alert.enricher.translator.base import BaseTranslator


class CoreFileTranslator(BaseTranslator):
    """
    dimension translator of core file event
    """

    def is_enabled(self):
        return self.item["query_configs"][0]["metric_id"] == "bk_monitor.corefile-gse"

    def translate(self, data):
        if "executable_path" in data:
            data["executable_path"].display_name = _("进程路径")

        if "executable" in data:
            data["executable"].display_name = _("进程")

        if "signal" in data:
            data["signal"].display_name = _("异常信号")

        return data
