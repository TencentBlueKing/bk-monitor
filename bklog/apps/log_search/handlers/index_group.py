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
from collections import defaultdict

from django.db import transaction

from apps.iam import Permission, ResourceEnum
from apps.log_search.constants import IndexSetDataType
from apps.log_search.exceptions import (
    IndexGroupNotExistException,
    DuplicateIndexGroupException,
    ChildIndexSetNotExistException,
)
from apps.log_search.handlers.index_set import BaseIndexSetHandler, IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario, SpaceApi
from apps.utils import APIModel
from bkm_space.define import SpaceTypeEnum
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
        current_space_uid = params["space_uid"]
        current_space_obj = SpaceApi.get_space_detail(space_uid=current_space_uid)

        related_space_uids = set()
        bkcc_space_uid = current_space_uid
        bkcc_space_obj = None

        if current_space_obj.space_type_id != SpaceTypeEnum.BKCC.value:
            bkcc_space_obj = SpaceApi.get_related_space(
                space_uid=current_space_uid,
                related_space_type=SpaceTypeEnum.BKCC.value
            )
            if bkcc_space_obj:
                bkcc_space_uid = bkcc_space_obj.space_uid
                related_space_uids.add(bkcc_space_uid)
            related_space_uids.add(current_space_uid)
        else:
            related_space_uids = set(IndexSetHandler.get_all_related_space_uids(bkcc_space_uid))

        space_uid_to_index_groups_map = defaultdict(list)

        index_group_queryset = LogIndexSet.objects.filter(is_group=True)

        if current_space_uid == bkcc_space_uid:
            current_space_index_groups = list(
                index_group_queryset.filter(
                    space_uid=current_space_uid
                ).values("space_uid", "index_set_id", "index_set_name")
            )
        else:
            related_space_index_groups = index_group_queryset.filter(space_uid__in=related_space_uids).values(
                "space_uid", "index_set_id", "index_set_name"
            )

            for index_groups in related_space_index_groups:
                space_uid_to_index_groups_map[index_groups["space_uid"]].append({
                    "space_uid": index_groups["space_uid"],
                    "index_set_id": index_groups["index_set_id"],
                    "index_set_name": index_groups["index_set_name"],
                })

            current_space_index_groups = space_uid_to_index_groups_map.get(current_space_uid, [])

        index_set_queryset = LogIndexSet.objects.filter(is_group=False)

        if current_space_uid == bkcc_space_uid:
            current_space_index_set_queryset = index_set_queryset.filter(space_uid__in=related_space_uids)
        else:
            current_space_index_set_queryset = index_set_queryset.filter(space_uid=current_space_uid)

        current_space_index_set_ids = set(current_space_index_set_queryset.values_list("index_set_id", flat=True))

        current_space_index_group_ids = [x["index_set_id"] for x in current_space_index_groups]
        child_records = LogIndexSetData.objects.filter(
            index_set_id__in=current_space_index_group_ids, type=IndexSetDataType.INDEX_SET.value
        ).values_list("index_set_id", "result_table_id")

        index_counts_dict = {}
        for group_id, child_id in child_records:
            if int(child_id) in current_space_index_set_ids:
                index_counts_dict[group_id] = index_counts_dict.get(group_id, 0) + 1
        for x in current_space_index_groups:
            x["space_name"] = current_space_obj.space_name
            x["bk_biz_id"] = current_space_obj.bk_biz_id
            x["index_count"] = index_counts_dict.get(x["index_set_id"], 0)
            x["is_related_space"] = False
            x["deletable"] = True  # TODO: 先给前端一个字段，后续需要判断索引组是否可以删除

        result = []

        current_space_index_groups.sort(key=lambda x: x["index_set_name"].encode("gbk", errors="ignore"))
        result.extend(current_space_index_groups)

        if current_space_uid != bkcc_space_uid and bkcc_space_obj:
            bkcc_space_index_groups = space_uid_to_index_groups_map.get(bkcc_space_uid, [])
            bkcc_space_index_groups.sort(key=lambda x: x["index_set_name"].encode("gbk", errors="ignore"))
            result.extend([g | {
                "space_name": bkcc_space_obj.space_name,
                "bk_biz_id": bkcc_space_obj.bk_biz_id,
                "index_count": None,
                "is_related_space": True,
                "deletable": False,
            } for g in bkcc_space_index_groups])

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
