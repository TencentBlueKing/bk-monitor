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

from django.core.management import BaseCommand
from django.db import transaction

from apps.log_search.models import Favorite
from apps.log_search.models import FavoriteGroup
from apps.log_search.constants import FavoriteGroupType


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **kwargs):
        groups = FavoriteGroup.objects.filter(
            group_type__in=[FavoriteGroupType.PRIVATE.value, FavoriteGroupType.UNGROUPED.value]
        ).order_by("created_at")

        checked_groups = {}
        groups_to_delete = []
        for group in groups:
            key = f"{group.source_app_code}_{group.space_uid}_{group.group_type}_{group.created_by}"
            if key in checked_groups:
                # 如果已经存在相同的分组，检查是否有数据，有则将数据转移到第一个遇到的分组
                if Favorite.objects.filter(group_id=group.id).exists():
                    print(f"group: {group.name} has data, moving to group_id: {checked_groups[key]}")
                    Favorite.objects.filter(group_id=group.id).update(group_id=checked_groups[key])
                groups_to_delete.append(group.id)
            else:
                # 记录第一个遇到的分组ID
                checked_groups[key] = group.id
        FavoriteGroup.objects.filter(id__in=groups_to_delete).delete()
        print(f"Deleted {len(groups_to_delete)} groups\n")
