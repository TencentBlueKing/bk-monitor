# -*- coding: utf-8 -*-
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

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if settings.SYNC_APIGATEWAY_ENABLED == "off":
            return

        gateway_name = settings.BK_APIGW_NAME

        # 待同步网关、资源定义文件，需调整为实际的配置文件地址
        definition_path = f"{settings.BASE_DIR}/support-files/apigw/definition.yaml"
        resources_path = f"{settings.BASE_DIR}/support-files/apigw/resources.yaml"

        call_command("sync_apigw_config", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("sync_apigw_stage", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("sync_apigw_resources", f"--gateway-name={gateway_name}", "--delete", f"--file={resources_path}")
        call_command(
            "sync_resource_docs_by_archive",
            f"--gateway-name={gateway_name}",
            f"--file={definition_path}",
            "--safe-mode",
        )
        call_command("create_version_and_release_apigw", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("grant_apigw_permissions", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("fetch_apigw_public_key", f"--gateway-name={gateway_name}")
