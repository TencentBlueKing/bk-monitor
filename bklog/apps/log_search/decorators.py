# -*- coding: utf-8 -*-
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
import functools
import time

from apps.log_search.constants import IndexSetType
from apps.log_search.models import UserIndexSetSearchHistory
from apps.utils.local import get_request_external_username


# 接口耗时装饰器
def search_history_record(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 接口耗时
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        time_consume = round(end_time - start_time, 3) * 1000

        # 更新查询耗时和记录history
        result.data["took"] = time_consume
        history_obj = result.data.get("history_obj")
        union_search_history_obj = result.data.get("union_search_history_obj")
        if history_obj:
            obj = UserIndexSetSearchHistory.objects.create(
                index_set_id=history_obj["index_set_id"],
                params=history_obj["params"],
                search_type=history_obj["search_type"],
                from_favorite_id=history_obj["from_favorite_id"],
                duration=time_consume,
            )
            # 当外部用户检索的时候, 将记录设置为外部用户
            external_username = get_request_external_username()
            if external_username:
                obj.created_by = external_username
                obj.save()
            del result.data["history_obj"]

        if union_search_history_obj:
            UserIndexSetSearchHistory.objects.create(
                index_set_ids=union_search_history_obj["index_set_ids"],
                params=union_search_history_obj["params"],
                search_type=union_search_history_obj["search_type"],
                duration=time_consume,
                index_set_type=IndexSetType.UNION.value,
                from_favorite_id=union_search_history_obj["from_favorite_id"],
            )
            del result.data["union_search_history_obj"]

        return result

    return wrapper
