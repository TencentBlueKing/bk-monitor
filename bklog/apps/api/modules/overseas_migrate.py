"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.utils.translation import gettext_lazy as _

from apps.api.base import DataAPI
from apps.api.modules.utils import add_app_info_before_request
from config.domains import DATAFLOW_APIGATEWAY_ROOT
from home_application.management.commands.migrate_tool import Prompt


class _OverseasMigrateApi:
    MODULE = _("海外数据迁移")

    def __init__(self):
        self.get_migration_mapping_info = DataAPI(
            method="GET",
            url=_build_request_url("common/migration/mapping_info/", "获取 flow_id 映射信息"),
            module=self.MODULE,
            description=_("获取 flow_id 映射信息"),
            before_request=add_app_info_before_request,
        )


def _build_request_url(path, description):
    request_url = DATAFLOW_APIGATEWAY_ROOT + path
    Prompt.info(
        msg="构建请求 URL -> \n   request_url: {request_url}\n   description: {description}",
        request_url=request_url,
        description=description,
    )
    return request_url
