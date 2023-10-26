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
import base64
import json
import os
import urllib.parse

from config.tools.environment import ENVIRONMENT

_SVC_DATA = None


def get_service_url(app_code, module_name=None, bk_paas_host=""):
    """
    获取第三方服务访问地址
    """
    global _SVC_DATA
    if _SVC_DATA is None:
        _SVC_DATA = {}
        svc_string = os.getenv("BKPAAS_SERVICE_ADDRESSES_BKSAAS")
        svc_list = []
        if svc_string:
            svc_list = json.loads(base64.b64decode(svc_string).decode("utf-8"))
        for svc in svc_list:
            _SVC_DATA[(svc["key"]["bk_app_code"], svc["key"]["module_name"])] = svc["value"]

    env = {"testing": "stag", "production": "prod"}.get(ENVIRONMENT, "stag")
    if _SVC_DATA and (app_code, module_name) in _SVC_DATA:
        return _SVC_DATA[(app_code, module_name)][env]

    if app_code == "bk_iam" and os.getenv("BK_IAM_V3_SAAS_HOST"):
        return os.environ["BK_IAM_V3_SAAS_HOST"]

    return urllib.parse.urljoin(bk_paas_host, f"/o/{app_code}/")
