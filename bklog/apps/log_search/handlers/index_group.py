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

from django.db import transaction
from django.db.models import Count

from apps.iam import Permission, ResourceEnum
from apps.log_search.constants import IndexSetDataType
from apps.log_search.exceptions import (
    IndexGroupNotExistException,
    DuplicateIndexGroupException,
    ChildIndexSetNotExistException,
)
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from apps.utils import APIModel
from bkm_space.utils import space_uid_to_bk_biz_id


class IndexGroupHandler(APIModel):
    def __init__(self, index_set_id=None):
        super().__init__()
        self.index_set_id = index_set_id

    def _get_data(self):
        """重写父类方法"""
        index_group = LogIndexSet.objects.filter(is_group=True, index_set_id=self.index_set_id).first()
        if not index_group:
            raise IndexGroupNotExistException()
        return index_group

    @staticmethod
    def list_index_groups(params: dict) -> list[dict]:
        """
        获取索引组列表
        """
        index_groups = LogIndexSet.objects.filter(is_group=True, space_uid=params["space_uid"]).values(
            "index_set_id", "index_set_name"
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
            x["deletable"] = True  # TODO: 先给前端一个字段，后续需要判断索引组是否可以删除

        result = list(index_groups)
        result.sort(key=lambda x: x["index_set_name"].encode("gbk", errors="ignore"))
        return result

    @staticmethod
    def create_index_group(params: dict) -> LogIndexSet:
        """
        创建索引组
        """
        index_group, created = LogIndexSet.objects.get_or_create(
            index_set_name=params["index_set_name"],
            space_uid=params["space_uid"],
            is_deleted=False,
            defaults={
                "is_group": True,
                "scenario_id": Scenario.LOG,
            },
        )
        if not created:
            raise DuplicateIndexGroupException(
                DuplicateIndexGroupException.MESSAGE.format(index_set_name=params["index_set_name"])
            )

        # 授权
        Permission().grant_creator_action(
            resource=ResourceEnum.INDICES.create_simple_instance(
                index_group.index_set_id, attribute={"name": index_group.index_set_name}
            ),
            creator=index_group.created_by,
        )
        return index_group

    def update_index_group(self, params: dict):
        """
        更新索引组
        """
        self.data.index_set_name = params["index_set_name"]
        self.data.save(update_fields=["index_set_name"])
        return self.data

    @transaction.atomic
    def delete_index_group(self):
        """
        删除索引组
        """
        LogIndexSetData.objects.filter(index_set_id=self.data.index_set_id).delete()
        self.data.delete()

    def add_child_index_sets(self, child_index_set_ids: list):
        """
        向索引组中添加索引集
        """

        # 检查所有子索引集是否存在
        existing_child_index_set_ids = set(
            LogIndexSet.objects.filter(
                index_set_id__in=child_index_set_ids,
                is_group=False,
            ).values_list("index_set_id", flat=True)
        )
        missing_child_index_set_ids = set(child_index_set_ids) - existing_child_index_set_ids
        if missing_child_index_set_ids:
            raise ChildIndexSetNotExistException(
                ChildIndexSetNotExistException.MESSAGE.format(
                    child_index_set_id=",".join(str(cid) for cid in missing_child_index_set_ids)
                )
            )

        # 创建关联关系，排除已存在的
        created_child_index_set_ids = set(self.data.get_child_index_set_ids())
        to_create = [
            LogIndexSetData(
                index_set_id=self.index_set_id,
                result_table_id=cid,
                scenario_id=self.data.scenario_id,
                bk_biz_id=space_uid_to_bk_biz_id(self.data.space_uid),
                type=IndexSetDataType.INDEX_SET.value,
                apply_status=LogIndexSetData.Status.NORMAL,
            )
            for cid in child_index_set_ids
            if cid not in created_child_index_set_ids
        ]
        if to_create:
            LogIndexSetData.objects.bulk_create(to_create)
            BaseIndexSetHandler.sync_router(self.data)

    def remove_child_index_sets(self, child_index_set_ids: list):
        """
        从索引组中移除索引集
        """
        LogIndexSetData.objects.filter(
            index_set_id=self.data.index_set_id, result_table_id__in=child_index_set_ids
        ).delete()
        BaseIndexSetHandler.sync_router(self.data)
