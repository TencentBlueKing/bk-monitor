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

from core.errors import Error


class K8sResourceNotFound(Error):
    status_code = 404
    code = 3380001
    name = "unsupported resource type"
    message_tpl = "unsupported resource type：{resource_type}"


class MultiWorkloadError(Error):
    status_code = 400
    code = 3380002
    name = "unsupported multi workload query"
    message_tpl = "unsupported multi workload query"
