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

from apps.log_search.exceptions import IndexSetDoseNotExistException
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from apps.utils import APIModel


class IndexGroupHandler(APIModel):
    def __init__(self, index_set_id=None):
        super().__init__()
        self.index_set_id = index_set_id

    def _get_data(self):
        """重写父类方法"""
        index_group = LogIndexSet.objects.filter(is_group=True, index_set_id=self.index_set_id).first()
        if not index_group:
            raise IndexSetDoseNotExistException()
        return index_group

    @staticmethod
    def list_index_groups(params: dict) -> list[dict]:
        """
        获取索引集组列表
        """
        index_groups = (
            LogIndexSet.objects.filter(is_group=True, space_uid=params["space_uid"])
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

        return index_groups

    @staticmethod
    def create_index_groups(params: dict) -> LogIndexSet:
        """
        创建索引集组
        """
        index_group = LogIndexSet.objects.create(
            index_set_name=params["index_set_name"],
            space_uid=params["space_uid"],
            scenario_id=Scenario.LOG,
            is_group=True,
        )
        return index_group

    def update_index_groups(self, params: dict):
        """
        更新索引集组
        """
        self.data.index_set_name = params["index_set_name"]
        self.data.save(update_fields=["index_set_name"])
        return self.data

    def delete_index_groups(self):
        """
        删除索引集组
        """
        LogIndexSetData.objects.filter(index_set_id=self.data.index_set_id).delete()
        self.data.delete()
