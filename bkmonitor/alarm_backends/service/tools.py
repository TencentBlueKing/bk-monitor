"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings


def message_queue_add(biz_id, dsn):
    """
    新增指定业务的队列推送配置
    """
    biz_id_str = str(biz_id)

    # 如果当前是字符串，转换为字典格式
    if isinstance(settings.MESSAGE_QUEUE_DSN, str):
        current_dsn = settings.MESSAGE_QUEUE_DSN
        dsn_config = {"0": current_dsn} if current_dsn else {}
    else:
        dsn_config = dict(settings.MESSAGE_QUEUE_DSN) if settings.MESSAGE_QUEUE_DSN else {}

    dsn_config[biz_id_str] = dsn
    settings.MESSAGE_QUEUE_DSN = dsn_config


def message_queue_remove(biz_id):
    """
    移除指定业务的队列推送配置
    """
    biz_id_str = str(biz_id)

    if isinstance(settings.MESSAGE_QUEUE_DSN, dict) and biz_id_str in settings.MESSAGE_QUEUE_DSN:
        dsn_config = dict(settings.MESSAGE_QUEUE_DSN)
        del dsn_config[biz_id_str]
        settings.MESSAGE_QUEUE_DSN = dsn_config


def qos_set_bk_data_ts(interval=3):
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = [["bk_data", "time_series"]]
    settings.QOS_INTERVAL_EXPAND = interval


def qos_set_bk_log_ts(interval=3):
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = [
        ["bk_log_search", "log"],
        ["bk_log_search", "time_series"],
    ]
    settings.QOS_INTERVAL_EXPAND = interval


def qos_clear_access():
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = []
