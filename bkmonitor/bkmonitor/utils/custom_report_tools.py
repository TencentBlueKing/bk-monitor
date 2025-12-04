"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import os

import requests
from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.thread_backend import ThreadPool

logger = logging.getLogger(__name__)


class custom_report_tool:
    """
    此类用于监控后台自身的自定义上报
    """

    def __init__(self, dataid):
        self.dataid = dataid

    def batch_cmd(self, cmds):
        """
        批量请求命令
        :param cmds: 命令集合
        :return: 命令执行结果
        """
        pool = ThreadPool()
        futures = []
        for cmd in cmds:
            futures.append(pool.apply_async(os.popen, args=(cmd,)))
        pool.close()
        pool.join()
        data = []
        for future in futures:
            data.extend(future.get())
        return data

    def send_data_by_http(self, all_data, access_token, parallel=True):
        """
        上报数据
        :param all_data: list, 待发送数据
        如：
        [{
            # 指标，必需项
            "metrics": {
                f"{stat['namespace']}_{metric.metric_name}": metric.metric_value
            },
            # 来源标识
            "target": settings.BK_PAAS_INNER_HOST,
            # 数据时间，精确到毫秒，非必需项
            "timestamp": arrow.now().int_timestamp * 1000
        }]
        :param access_token: token
        :param parallel: 是否并发请求
        """
        assert settings.CUSTOM_REPORT_DEFAULT_PROXY_IP, _(
            "全局配置中: 自定义上报默认服务器[CUSTOM_REPORT_DEFAULT_PROXY_IP]"
            "未配置，请确认bkmonitorproxy已部署，并在全局配置中配置！"
        )
        send_list = [[]]
        chunk_index = 0
        # 避免每次发送的数据太长，分批进行上报
        for data in all_data:
            send_list[chunk_index].append(data)
            if len(send_list[chunk_index]) > 500:
                chunk_index += 1
                send_list.append([])

        send_data = [{"data_id": self.dataid, "access_token": access_token, "data": data} for data in send_list]

        proxy_url = f"http://{settings.CUSTOM_REPORT_DEFAULT_PROXY_IP[0]}:10205/v2/push/"

        if not parallel:
            for data in send_data:
                resp = requests.post(proxy_url, json=data)

                if resp.status_code != 200:
                    logger.warning("failed send data to proxy(%s), got resp: %s", proxy_url, resp.text)
        else:
            pool = ThreadPool()
            for data in send_data:
                pool.apply_async(requests.post, args=(proxy_url,), kwds={"json": data})
            pool.close()
            pool.join()
