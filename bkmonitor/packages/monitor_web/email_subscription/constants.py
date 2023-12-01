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
from bkmonitor.models import ScenarioEnum

CLUSTERING_VARIABLES = [
    {"name": "username", "description": "用户名称", "example": "admin"},
    {"name": "time", "description": "系统时间", "example": "2023-10-10 22:00:00"},
    {"name": "indicesname", "description": "索引集名称", "example": "apm_demo_app_1111"},
]

SUBSCRIPTION_VARIABLES_MAP = {ScenarioEnum.CLUSTERING: CLUSTERING_VARIABLES}
