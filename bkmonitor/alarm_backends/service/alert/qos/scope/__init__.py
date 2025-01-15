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
from django.utils.module_loading import import_string


class EmptyScope:
    duration = 0

    def get_scope_dimension(self):
        return {}

    def get_scope_duration(self):
        return self.duration


empty = EmptyScope()


def load_scope(module_name, target):
    try:
        return import_string(f"{__name__}.{module_name}_{target}.Scope")()
    except ImportError:
        return empty
