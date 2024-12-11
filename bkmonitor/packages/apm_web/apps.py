# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.apps import AppConfig


class ApmWebConfig(AppConfig):
    name = "apm_web"
    verbose_name = "apm_web"
    label = "apm_web"

    def ready(self):
        # 注册 profile 解析器
        from apm_web.profile.constants import InputType
        from apm_web.profile.doris.converter import DorisProfileConverter
        from apm_web.profile.perf.converter import PerfScriptProfileConverter
        from apm_web.profile.pprof.converter import PprofProfileConverter
        from apm_web.profile.profileconverter import register_profile_converter

        register_profile_converter(InputType.DORIS.value, DorisProfileConverter)
        register_profile_converter(InputType.PERF_SCRIPT.value, PerfScriptProfileConverter)
        register_profile_converter(InputType.PPROF.value, PprofProfileConverter)
