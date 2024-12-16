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

from alarm_backends.core.cache.cmdb import ServiceInstanceManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator
from constants.data_source import DataSourceLabel


class ServiceInstanceTranslator(BaseTranslator):
    """
    采集配置名称翻译
    """

    def is_enabled(self):
        return self.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR

    def translate(self, data):
        field = data.get("bk_target_service_instance_id")
        if not field:
            return data
        instance_id = field.value
        instance = ServiceInstanceManager.get(instance_id)
        if not instance:
            field.display_name = _("服务实例ID")
        else:
            field.display_name = _("服务实例名称")
            field.display_value = instance.name
        return data
