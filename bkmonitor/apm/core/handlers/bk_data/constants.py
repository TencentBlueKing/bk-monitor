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
from django.db.models import TextChoices


class FlowStatus(TextChoices):
    """
    Flow配置流各阶段状态
    用来追踪一个Flow的各个阶段
    """

    CONFIG_DEPLOY_FAILED = "config_deploy_failed", "数据源配置失败"
    CONFIG_CLEANS_FAILED = "config_cleans_failed", "清洗配置失败"
    CONFIG_CLEANS_START_FAILED = "config_cleans_start_failed", "清洗启动失败"
    AUTH_FAILED = "auth_failed", "项目授权失败"
    CONFIG_FLOW_FAILED = "config_flow_failed", "Flow配置失败"
    SUCCESS = "success", "启动完成"
