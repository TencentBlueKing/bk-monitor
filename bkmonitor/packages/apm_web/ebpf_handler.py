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

from apm_web.constants import (
    APM_EBPF_METRIC_DEFAULT_NEGATIVE_PREFIX,
    APM_EBPF_METRIC_DEFAULT_PREFIX,
)
from core.drf_resource import resource

logger = logging.getLogger("ebpf.custom")


class CustomTimeSeriesInstall(object):
    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.custom_report_name = f"{APM_EBPF_METRIC_DEFAULT_PREFIX}_{self.bk_biz_id}_metric"
        if self.bk_biz_id < 0:
            self.custom_report_name = f"{APM_EBPF_METRIC_DEFAULT_NEGATIVE_PREFIX}_{abs(self.bk_biz_id)}_metric"

    def create_default_custom_time_series(self):
        """
        内置自定义指标数据
        因是定时任务执行，故不考虑重试机制
        """

        param = {
            "name": self.custom_report_name,
            "scenario": "application_check",
            "data_label": self.custom_report_name,
            "is_platform": False,
            "protocol": "prometheus",
            "desc": "",
            "bk_biz_id": self.bk_biz_id,
        }
        try:
            resource.custom_report.create_custom_time_series(param)
        except Exception as e:
            logger.error(f"[create_default_custom_time_series], param: {param}, error: {e}")
