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

import os

__all__ = [
    "DJANGO_CONF_MODULE",
    "ROLE",
    "ENVIRONMENT",
    "PLATFORM",
    "RUN_MODE",
    "PAAS_VERSION",
    "IS_CONTAINER_MODE",
    "NEW_ENV",
    "BKAPP_DEPLOY_PLATFORM",
]


# PaaS Version
import warnings

if "BKPAAS_ENVIRONMENT" in os.environ:
    PAAS_VERSION = "V3"
elif "BK_ENV" in os.environ:
    PAAS_VERSION = "V2"
else:
    PAAS_VERSION = ""


BKAPP_DEPLOY_PLATFORM = os.environ.get("BKAPP_DEPLOY_PLATFORM") or os.environ.get("BKPAAS_ENGINE_REGION")

DJANGO_CONF_MODULE = os.environ.get("DJANGO_CONF_MODULE")
if not DJANGO_CONF_MODULE:
    if "BKPAAS_ENVIRONMENT" not in os.environ:
        # PaaS V2
        ENVIRONMENT = os.getenv("BK_ENV", "development")
    else:
        # PaaS V3
        PAAS_V3_ENVIRONMENT = os.environ.get("BKPAAS_ENVIRONMENT", "dev")
        ENVIRONMENT = {
            "dev": "development",
            "stag": "testing",
            "prod": "production",
        }.get(PAAS_V3_ENVIRONMENT)

    if not BKAPP_DEPLOY_PLATFORM:
        raise RuntimeError("Environment variable 'BKAPP_DEPLOY_PLATFORM' " "should not be empty.")

    DJANGO_CONF_MODULE = f"config.web.{ENVIRONMENT}.{BKAPP_DEPLOY_PLATFORM}"

# validate DJANGO_CONF_MODULE
try:
    _, ROLE, ENVIRONMENT, PLATFORM = DJANGO_CONF_MODULE.split(".")
    # DJANGO_CONF_MODULE 中最后一段包含了PLATFORM信息，以DJANGO_CONF_MODULE为准
    if BKAPP_DEPLOY_PLATFORM != PLATFORM:
        warnings.warn(
            "DJANGO_CONF_MODULE[{}] set PLATFORM: [{}] but BKAPP_DEPLOY_PLATFORM in env is [{}]".format(
                DJANGO_CONF_MODULE, PLATFORM, BKAPP_DEPLOY_PLATFORM
            )
        )
    BKAPP_DEPLOY_PLATFORM = PLATFORM
except Exception:
    raise RuntimeError(
        "Environment variable 'DJANGO_CONF_MODULE' "
        "should not be %r. format: %r" % (DJANGO_CONF_MODULE, "conf.{web|worker}.[environment].[platform]")
    )

RUN_MODE = {"development": "DEVELOP", "testing": "TEST", "production": "PRODUCT"}.get(ENVIRONMENT)
NEW_ENV = {"development": "dev", "testing": "stag", "production": "prod"}.get(ENVIRONMENT)


# 是否是容器化部署模式
IS_CONTAINER_MODE = os.getenv("DEPLOY_MODE") == "kubernetes"
