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
from bkmonitor.models import ApiAuthToken
from bkmonitor.share.handler import (
    ApmApiAuthChecker,
    CollectApiAuthChecker,
    CustomEventApiAuthChecker,
    CustomMetricApiAuthChecker,
    EventApiAuthChecker,
    GrafanaApiAuthChecker,
    HostApiAuthChecker,
    KubernetesApiAuthChecker,
    UptimeCheckApiAuthChecker,
)
from bkmonitor.utils.common_utils import camel_to_underscore
from core.errors.share import TokenValidatedError

checker_list = [
    HostApiAuthChecker,
    UptimeCheckApiAuthChecker,
    CustomMetricApiAuthChecker,
    CustomEventApiAuthChecker,
    CollectApiAuthChecker,
    ApmApiAuthChecker,
    KubernetesApiAuthChecker,
    EventApiAuthChecker,
    GrafanaApiAuthChecker,
]

checker_mapping = {camel_to_underscore(checker.__name__)[:-17]: checker for checker in checker_list}


def check_api_permission(request, request_data):
    token = getattr(request, "token", None)
    if not token:
        return
    try:
        record = ApiAuthToken.objects.get(token=token)
    except ApiAuthToken.DoesNotExist:
        raise TokenValidatedError
    else:
        checker_prefix = record.type.split("scene_", 1)[-1]
        checker_mapping[checker_prefix](record).check(request_data)
