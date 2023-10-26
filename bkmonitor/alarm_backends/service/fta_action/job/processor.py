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
from django.conf import settings

from django.utils.functional import cached_property

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.service.fta_action.common.processor import ActionProcessor as CommonActionProcessor

logger = logging.getLogger("fta_action.run")


class ActionProcessor(CommonActionProcessor):
    """
    作业平台处理器
    """

    @cached_property
    def inputs(self):
        job_inputs = {"job_site_url": settings.JOB_URL.rstrip("/")}
        job_inputs.update(super(ActionProcessor, self).inputs)
        global_vars = []
        for param in job_inputs["execute_config"]["template_detail"]:
            (var_id, category) = tuple(param["key"].split("_"))
            params_value = param["value"]
            if category == "3":
                # IP参数的组装需要根据格式进行处理
                for ip in params_value.split(";"):
                    if not ip:
                        continue
                    if ":" in ip:
                        cloud_id, inner_ip = ip.split(":")
                    else:
                        inner_ip = ip
                        cloud_id = (
                            getattr(self.context["alert"].event, "bk_cloud_id", 0) if self.context["alert"] else 0
                        )

                    global_vars.append(
                        {
                            "id": int(var_id),
                            "server": {"ip_list": [{"bk_cloud_id": cloud_id, "ip": inner_ip}]},
                        }
                    )
            else:
                global_vars.append({"id": int(var_id), "value": params_value})
        job_inputs["global_vars"] = global_vars
        return job_inputs
