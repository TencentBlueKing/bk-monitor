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
"""

from datetime import datetime, timedelta

from blueapps.contrib.celery_tools.periodic import periodic_task  # noqa
from celery.schedules import crontab  # noqa

from apps.log_search.models import LogIndexSet, Space, UserIndexSetSearchHistory
from apps.utils.core.cache.cmdb_host import CmdbHostCache


@periodic_task(run_every=crontab(minute="0", hour="*"))
def refresh_cmdb():
    index_set_ids = list(
        UserIndexSetSearchHistory.objects.filter(created_at__gte=datetime.now() - timedelta(days=1)).values_list(
            "index_set_id", flat=True
        )
    )
    space_uids = set(
        LogIndexSet.objects.filter(index_set_id__in=index_set_ids, is_active=True).values_list("space_uid", flat=True)
    )
    bk_biz_ids = set(Space.objects.filter(space_uid__in=space_uids).values_list("bk_biz_id", flat=True))
    current_hour = datetime.now().hour
    if current_hour % 12 != 0:
        CmdbHostCache.refresh(bk_biz_ids)
    else:
        CmdbHostCache.refresh()
