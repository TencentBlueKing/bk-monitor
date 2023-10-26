# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models import ConvergeInstance, ActionInstance, ConvergeRelation
from constants.action import ConvergeType, ConvergeStatus


def list_other_converged_instances(matched_related_ids, current_instance, instance_type=ConvergeType.ACTION):
    """
    列出其他匹配的对象
    :param matched_related_ids:
    :param current_instance  当前收敛的对象
    :param instance_type 收敛类型
    :return:
    """
    if instance_type == ConvergeType.CONVERGE:
        queryset = ConvergeInstance.objects.filter(id__in=matched_related_ids)
    else:
        queryset = ActionInstance.objects.filter(id__in=matched_related_ids)
    return queryset.filter(id__lte=current_instance.id).exclude(id=current_instance.id)


def get_related_converge_action(converge_id):
    """
    获取收敛对象的关联
    :param converge_id: 收敛事件ID
    :return:
    """
    action_ids = set(
        ConvergeRelation.objects.filter(converge_id=converge_id, related_type=ConvergeType.ACTION).values_list(
            "related_id", flat=True
        )
    )
    if action_ids:
        return ActionInstance.objects.filter(id__in=action_ids).first()
    return None


def get_execute_related_ids(converge_id, related_type=ConvergeType.ACTION):
    """
    获取收敛相关的事件ID
    :param related_type: 关联关系
    :param converge_id: 收敛记录ID
    :return:
    """
    return ConvergeRelation.objects.filter(
        converge_id=converge_id,
        converge_status=ConvergeStatus.EXECUTED,
        related_type=related_type,
    ).values_list("related_id", flat=True)


def get_executed_actions(converge_id):
    """
    获取收敛对象的关联
    :param converge_id: 收敛事件ID
    :return:
    """
    action_ids = list(get_execute_related_ids(converge_id))

    return ActionInstance.objects.filter(id__in=action_ids)
