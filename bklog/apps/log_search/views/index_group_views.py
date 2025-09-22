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

from django.db.models import Count

from apps.generic import APIViewSet
from apps.log_search.models import LogIndexSet, LogIndexSetData
from rest_framework.response import Response


class IndexGroupViewSet(APIViewSet):
    def list(self, request, *args, **kwargs):
        # TODO 补充接口文档注释
        index_groups = (
            LogIndexSet.objects.filter(is_group=True)
            .values("index_set_id", "index_set_name")
            .order_by("index_set_name")
        )
        # 补充索引数量字段
        index_set_ids = [x["index_set_id"] for x in index_groups]
        index_counts = (
            LogIndexSetData.objects.filter(index_set_id__in=index_set_ids)
            .values("index_set_id")
            .annotate(count=Count("index_id"))
        )
        index_counts_dict = {x["index_set_id"]: x["count"] for x in index_counts}
        for x in index_groups:
            x["index_count"] = index_counts_dict.get(x["index_set_id"], 0)

        return Response(index_groups)

    def destroy(self, request, *args, **kwargs):
        index_group = LogIndexSet.objects.filter(is_group=True, index_set_id=kwargs["index_set_id"]).first()
        LogIndexSetData.objects.filter(index_set_id=index_group.index_set_id).delete()
        index_group.delete()

    def create(self, request, *args, **kwargs):
        LogIndexSet.objects.create(
            index_set_name=request.data["index_set_name"],
            space_uid=request.data["space_uid"],
            scenario_id=request.data["scenario_id"],
            is_group=True,
        )
        return Response()

    def update(self, request, *args, **kwargs):
        index_group = LogIndexSet.objects.filter(is_group=True, index_set_id=kwargs["index_set_id"]).first()
        index_group.index_name = request.data["index_set_name"]
        index_group.save()
        return Response()
