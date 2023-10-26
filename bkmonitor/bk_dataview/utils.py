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
import logging
import os
import random
import string
from contextlib import contextmanager
from typing import List

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


@contextmanager
def os_env(**kwargs):
    """临时修改环境变量"""
    os.environ["SETTINGS_BASE_DIR"] = settings.BASE_DIR
    os.environ["SETTINGS_SITE_URL"] = settings.SITE_URL + settings.API_SUB_PATH

    # 添加自定义变量
    for k, v in kwargs.items():
        if not k.isupper():
            continue
        os.environ[k] = str(v)

    yield


def requests_curl_log(resp, *args, **kwargs):
    """记录requests curl log"""
    # 添加日志信息
    curl_req = "REQ: curl -X {method} '{url}'".format(method=resp.request.method, url=resp.request.url)

    if resp.request.body:
        curl_req += " -d '{body}'".format(body=resp.request.body)

    if resp.request.headers:
        for key, value in resp.request.headers.items():
            # ignore headers
            if key in ["User-Agent", "Accept-Encoding", "Connection", "Accept", "Content-Length"]:
                continue
            if key == "Cookie" and value.startswith("x_host_key"):
                continue

            curl_req += " -H '{k}: {v}'".format(k=key, v=value)

    if resp.headers.get("Content-Type", "").startswith("application/json"):
        resp_text = resp.content
    else:
        resp_text = f"Bin...(total {len(resp.content)} Bytes)"

    curl_resp = "RESP: [{}] {:.2f}ms {}".format(resp.status_code, resp.elapsed.total_seconds() * 1000, resp_text)

    logger.info("%s\n \t %s", curl_req, curl_resp)


def generate_uid(exclude_uids: List[str] = None, exclude_model: models.Model.__class__ = None) -> str:
    """
    9位随机字符串，由数字，大小写字母，下划线组成
    """
    uid = "".join(random.sample(string.ascii_letters + string.digits + "_", 9))
    while (exclude_uids and uid in exclude_uids) or (exclude_model and exclude_model.objects.filter(uid=uid).exists()):
        uid = "".join(random.sample(string.ascii_letters + string.digits + "_", 9))
    return uid
