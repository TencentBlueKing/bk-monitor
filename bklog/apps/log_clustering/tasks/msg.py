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
import arrow
from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.exceptions import ClusteringClosedException
from apps.log_clustering.models import ClusteringConfig
from apps.log_measure.events import NOTIFY_EVENT
from apps.log_search.handlers.search.aggs_handlers import AggsViewAdapter
from apps.log_search.models import LogIndexSet, Space
from apps.utils.local import set_local_param
from apps.utils.task import high_priority_task


@high_priority_task(ignore_result=True)
def access_clustering(index_set_id):
    clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id)
    log_index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
    doc_count = get_doc_count(index_set_id=index_set_id, bk_biz_id=clustering_config.bk_biz_id)
    space = Space.objects.get(bk_biz_id=clustering_config.bk_biz_id)

    if not FeatureToggleObject.switch(BKDATA_CLUSTERING_TOGGLE):
        raise ClusteringClosedException()
    conf = FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config

    # 若该配置小于0，则代表不需要审批
    auto_approve_doc_count = conf.get("auto_approve_doc_count", -1)

    if 0 <= auto_approve_doc_count < doc_count:
        # auto_approve_doc_count 大于 0，且单日文档数量大于 auto_approve_doc_count，则需要进行审批
        msg = _("[待审批] 有新聚类创建，请关注！索引集id: {}, 索引集名称: {}, 业务id: {}, 业务名称: {}, 创建者: {}, 过去一天的数据量doc_count={}").format(
            index_set_id,
            log_index_set.index_set_name,
            clustering_config.bk_biz_id
            if not clustering_config.related_space_pre_bk_biz_id
            else clustering_config.related_space_pre_bk_biz_id,
            space.space_name,
            clustering_config.created_by,
            doc_count,
        )
    else:
        # 原有逻辑保留
        # from apps.log_clustering.handlers.pipline_service.aiops_service import operator_aiops_service
        # pipeline_id = operator_aiops_service(index_set_id)

        # 自动接入聚类创建-在线训练任务    新建均走在线训练新流程
        from apps.log_clustering.handlers.pipline_service.aiops_service_online import (
            operator_aiops_service_online,
        )

        pipeline_id = operator_aiops_service_online(index_set_id)

        msg = _(
            "[自动接入] 有新聚类创建，请关注！索引集id: {}, 索引集名称: {}, 业务id: {}, 业务名称: {}, 创建者: {}, 过去一天的数据量doc_count={}，任务ID: {}"
        ).format(
            index_set_id,
            log_index_set.index_set_name,
            clustering_config.bk_biz_id
            if not clustering_config.related_space_pre_bk_biz_id
            else clustering_config.related_space_pre_bk_biz_id,
            space.space_name,
            clustering_config.created_by,
            doc_count,
            pipeline_id,
        )

    NOTIFY_EVENT(
        content=f"{msg}",
        dimensions={"index_set_id": clustering_config.index_set_id, "msg_type": "clustering_config"},
    )


def get_doc_count(index_set_id, bk_biz_id):
    set_local_param("time_zone", settings.TIME_ZONE)
    now = arrow.now()
    aggs_result = AggsViewAdapter().date_histogram(
        index_set_id=index_set_id,
        query_data={
            "bk_biz_id": bk_biz_id,
            "addition": [],
            "host_scopes": {"modules": [], "ips": "", "target_nodes": [], "target_node_type": ""},
            "start_time": now.shift(days=-1).format(),
            "end_time": now.format("YYYY-MM-DD HH:mm:ss"),
            "time_range": "customized",
            "keyword": "*",
            "begin": 0,
            "size": 500,
            "fields": [],
            "interval": "1d",
        },
    )
    doc_count = 0
    for bucket in aggs_result["aggs"]["group_by_histogram"]["buckets"]:
        doc_count += bucket["doc_count"]

    return doc_count


def format_timedelta(td):
    """
    将时间差转换为人类可读格式，比如 "1d 3h 45m"
    """
    days = td.days
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # 构建结果字符串
    result = []
    if days > 0:
        result.append(f"{days}d")
    if hours > 0:
        result.append(f"{hours}h")
    if minutes > 0:
        result.append(f"{minutes}m")

    return ' '.join(result)


@periodic_task(run_every=crontab(minute="*/10"))
def notify_access_not_finished():
    """
    30分钟内接入未完成接入的，触发事件
    """
    from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler

    half_hours_ago = arrow.now().shift(minutes=-30).datetime
    clustering_configs = ClusteringConfig.objects.filter(
        signature_enable=True, access_finished=False, created_at__lte=half_hours_ago
    )
    for clustering_config in clustering_configs:
        index_set_id = clustering_config.index_set_id
        log_index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
        space = Space.objects.get(bk_biz_id=clustering_config.bk_biz_id)

        # 先重新刷新一下接入状态，如果已经接入完成，就直接跳过
        result = ClusteringConfigHandler(index_set_id=index_set_id).get_access_status()
        if result["access_finished"]:
            continue

        msg = _("聚类接入持续 {} 未完成，请关注！索引集id: {}, 索引集名称: {}, 业务id: {}, 业务名称: {}, 创建者: {}").format(
            format_timedelta(arrow.now().datetime - clustering_config.created_at),
            index_set_id,
            log_index_set.index_set_name,
            clustering_config.bk_biz_id
            if not clustering_config.related_space_pre_bk_biz_id
            else clustering_config.related_space_pre_bk_biz_id,
            space.space_name,
            clustering_config.created_by,
        )
        NOTIFY_EVENT(
            content=f"{msg}",
            dimensions={"index_set_id": clustering_config.index_set_id, "msg_type": "clustering_access_not_finished"},
        )
