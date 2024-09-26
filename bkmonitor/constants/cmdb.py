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


BIZ_ID_FIELD_NAMES = ["bk_biz_id", "biz_id", "cc_biz_id", "app_id", "bizId"]


class TargetObjectType(object):
    """
    目标对象类型
    """

    SERVICE = "SERVICE"
    HOST = "HOST"
    CLUSTER = "CLUSTER"


class TargetNodeType(object):
    """
    目标节点类型
    """

    TOPO = "TOPO"  # 动态实例（拓扑）
    INSTANCE = "INSTANCE"  # 静态实例
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"  # 服务模板
    SET_TEMPLATE = "SET_TEMPLATE"  # 集群模板
    DYNAMIC_GROUP = "DYNAMIC_GROUP"  # 动态分组
    CLUSTER = "CLUSTER"  # BCS集群
