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

from alarm_backends.core.cache.cmdb import BusinessManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator


class BizNameTranslator(BaseTranslator):
    """
    数据纬度-空间名称翻译
    """

    def is_enabled(self):
        return True

    def translate(self, data):
        field = data.get("bk_biz_id")
        if not field:
            return data
        business = BusinessManager.get(field.value)
        if not business:
            return data
        field.display_name = business.bk_biz_name
        return data
