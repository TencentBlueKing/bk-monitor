"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from rest_framework.response import Response

from apps.api import TGPATaskApi
from apps.generic import APIViewSet
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.serializers import CreateTGPATaskSerializer, GetTGPATaskListSerializer


class TGPATaskViewSet(APIViewSet):
    """日志拉取任务"""

    def list(self, request, *args, **kwargs):
        params = self.params_valid(GetTGPATaskListSerializer)
        params["cc_id"] = params.pop("bk_biz_id")
        return Response(TGPATaskHandler.get_task_list(params, need_format=True))

    def create(self, request, *args, **kwargs):
        params = self.params_valid(CreateTGPATaskSerializer)
        params["cc_id"] = params.pop("bk_biz_id")
        params["logpath"] = params.pop("log_path")
        params["taskName"] = params.pop("task_name")
        params["username"] = request.user.username
        return Response(TGPATaskApi.create_single_user_log_task_v2(params))
