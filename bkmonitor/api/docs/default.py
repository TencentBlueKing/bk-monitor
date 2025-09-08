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


import abc

import six
from django.conf import settings

from core.drf_resource import APIResource


class BKDocsCenterResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    # 暂未接入esb
    # base_url = "%s/api/c/compapi/bk_login/" % settings.BK_COMPONENT_API_URL
    base_url = "%s/o/bk_docs_center/api/v1/" % settings.BK_PAAS_HOST

    # 模块名
    module_name = "bk_docs_center"

    @property
    def label(self):
        return self.__doc__


class GetDocLinkByPath(BKDocsCenterResource):
    """
    根据文档路径找文档链接
    """

    action = "/get_doc_link_by_path/"
    method = "GET"
