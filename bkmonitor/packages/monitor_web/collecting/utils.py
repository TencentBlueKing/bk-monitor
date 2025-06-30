"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import namedtuple
from core.drf_resource import api
from monitor_web.collecting.constant import CollectStatus


def chunks(lst, n):
    """
    切割数组
    :param lst: 数组
    :param n: 每组多少份
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def fetch_sub_statistics(config_data_list):
    subscription_id_config_map = {
        config.deployment_config.subscription_id: config
        for config in config_data_list
        if config.deployment_config.subscription_id
    }

    # 避免对节点管理造成巨大压力，这里分组请求，每组20份
    collect_statistics_data = api.node_man.fetch_subscription_statistic.bulk_request(
        [
            {"subscription_id_list": subscription_id_group}
            for subscription_id_group in chunks(list(subscription_id_config_map.keys()), 20)
        ],
        ignore_exceptions=True,
    )
    collect_statistics_data = [item for group in collect_statistics_data for item in group]

    return subscription_id_config_map, collect_statistics_data


def get_subs_status_data(config_data_list):
    """
    获取节点管理订阅实时状态以及订阅ID与采集配置的映射
    :param config_data_list: 采集配置数据列表
    :return: 包含订阅状态和订阅ID与采集配置映射的字典
    """

    subscription_id_config_map, statistics_data = fetch_sub_statistics(config_data_list)

    subscription_id_status_map = {}

    # 节点管理返回的状态数量
    for subscription_status in statistics_data:
        status_number = {}
        for status_result in subscription_status.get("status", []):
            status_number[status_result["status"]] = status_result["count"]

        error_count = status_number.get(CollectStatus.FAILED, 0)
        total_count = subscription_status.get("instances", 0)
        pending_count = status_number.get(CollectStatus.PENDING, 0)
        running_count = status_number.get(CollectStatus.RUNNING, 0)
        subscription_status_data = {
            "error_instance_count": error_count,
            "total_instance_count": total_count,
            "pending_instance_count": pending_count,
            "running_instance_count": running_count,
        }
        subscription_id_status_map[subscription_status["subscription_id"]] = subscription_status_data

    SubscriptionStatusData = namedtuple("SubscriptionStatusData", ["status_map", "config_map"])
    return SubscriptionStatusData(subscription_id_status_map, subscription_id_config_map)
