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
from django.utils.translation import gettext_lazy as _  # noqa

from apps.api import MonitorApi
from apps.log_clustering.constants import (
    DEFAULT_NOTICE_WAY,
    DEFAULT_NOTIFY_RECEIVER_TYPE,
)
from apps.log_clustering.models import ClusteringConfig, NoticeGroup
from apps.log_databus.constants import EMPTY_REQUEST_USER
from apps.log_search.models import LogIndexSet


class MonitorUtils(object):
    @classmethod
    def save_notice_group(cls, bk_biz_id: int, name: str, notice_way: dict, notice_receiver: list, message: str = ""):
        return MonitorApi.save_notice_group(
            params={
                "bk_biz_id": bk_biz_id,
                "name": name,
                "message": message,
                "notice_way": notice_way,
                "notice_receiver": notice_receiver,
            }
        )

    @classmethod
    def generate_notice_receiver(cls, receivers, notice_tye: str):
        return [{"type": notice_tye, "id": receiver} for receiver in receivers]

    @classmethod
    def get_or_create_notice_group(cls, log_index_set_id, bk_biz_id):
        notice_group = NoticeGroup.objects.filter(index_set_id=log_index_set_id, bk_biz_id=bk_biz_id).first()
        if notice_group:
            return notice_group.notice_group_id
        log_index_set = LogIndexSet.objects.filter(index_set_id=log_index_set_id).first()
        maintainers = cls._generate_maintainer(index_set_id=log_index_set_id)
        notice_receiver = cls.generate_notice_receiver(receivers=maintainers, notice_tye=DEFAULT_NOTIFY_RECEIVER_TYPE)
        group = cls.save_notice_group(
            bk_biz_id=bk_biz_id,
            name=_("{}_{}聚类告警组").format(log_index_set_id, log_index_set.index_set_name),
            message="",
            notice_receiver=notice_receiver,
            notice_way=DEFAULT_NOTICE_WAY,
        )
        NoticeGroup.objects.get_or_create(
            index_set_id=log_index_set_id, notice_group_id=group["id"], bk_biz_id=bk_biz_id
        )
        return group["id"]

    @classmethod
    def _generate_maintainer(cls, index_set_id):
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id)
        maintainers = {clustering_config.created_by} - {EMPTY_REQUEST_USER}
        return maintainers
