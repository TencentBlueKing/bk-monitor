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
import time
from datetime import datetime

import requests
from django.conf import settings

from bkmonitor.utils.supervisor_utils import get_supervisor_client

logger = logging.getLogger(__name__)


def validate_license_info(url, cert_path, key_path, platform, now=None):
    if not os.path.exists(cert_path):
        message = "cert not found at: %s" % cert_path
        raise ValueError("cert not found at: %s" % cert_path)

    with open(cert_path, "rb") as fp:
        cert = fp.read()

    now = now or datetime.utcnow()
    response = requests.post(
        url,
        json={
            "certificate": cert,
            "platform": platform,
            "requesttime": now.strftime("%Y-%m-%d %H:%M:%S"),
        },
        verify=False,
        cert=(cert_path, key_path),
    )
    result = response.json()
    if not result.get("status"):
        message = "validate license failed: %s" % result.get(
            "message",
            "unknown",
        )
        raise ValueError(message)
    validate_result = result.get("result")
    validate_message = result.get("message", "unknown")
    if validate_result != 0:
        raise ValueError(validate_message)
    return result


def check_system_license():
    cert_path = os.path.join(settings.CERT_PATH, "platform.cert")
    key_path = os.path.join(settings.CERT_PATH, "platform.key")
    validate_license_info(
        "https://{}:{}/certificate".format(settings.LICENSE_HOST, settings.LICENSE_PORT),
        cert_path,
        key_path,
        "bkdata",
    )


def main():  # check by crontab
    num_of_req = len(settings.LICENSE_REQ_INTERVAL)
    count = 0
    while count <= num_of_req:
        try:
            return check_system_license()
        except ValueError as error:
            if count < num_of_req:
                try_again_interval = settings.LICENSE_REQ_INTERVAL[count]
                message = "The %dst request license error, %s. Trying again " "in %d seconds." % (
                    count + 1,
                    error,
                    try_again_interval,
                )
            else:
                try_again_interval = 1
                message = "The %dst request license error, %s. " "Stop All Process." % (count + 1, error)

            logger.error(message)
            time.sleep(try_again_interval)
            count += 1

    client = get_supervisor_client()
    client.supervisor.stopAllProcesses()


if __name__ == "__main__":
    main()
