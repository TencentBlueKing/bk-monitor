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


import abc
import json
import logging
import os

import six
from django.conf import settings
from django.utils.translation import gettext as _
from jinja2.sandbox import SandboxedEnvironment as Environment

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from core.errors.uptime_check import UnknownProtocolError
from monitor.constants import UptimeCheckProtocol
from monitor_web.commons.job import JobTaskClient

logger = logging.getLogger(__name__)


class CollectorInstallWay(object):
    """采集器安装方式"""

    BUILD_IN = 0
    ZIP_FILE = 1
    EXE_FILE = 2


pwd = os.path.dirname(os.path.realpath(__file__))


class UptimeCheckCollector(six.with_metaclass(abc.ABCMeta, object)):
    """
    uptimecheckbeat采集器，用于测试下发
    """

    COLLECTOR_NAME = "uptimecheckbeat"

    def __init__(self, bk_biz_id, operator=None, *args, **kwargs):
        self.job_client = JobTaskClient(bk_biz_id=bk_biz_id, operator=operator)

    # 获取脚本执行结果，过滤掉额外输出
    def fetch_content(self, result):
        """
        根据分隔符拿回真实的content
        :param result: fast_script的返回结果
        :return: 处理后的返回结果
        """
        divide_symbol = settings.DIVIDE_SYMBOL
        for success_item in result["success"]:
            if success_item["log_content"].find(divide_symbol) != -1:
                success_item["log_content"] = success_item["log_content"].split(divide_symbol, 1)[1].strip()
        return result

    def label_failed_ip(self, task_result, label):
        """
        对JOB失败的任务进行标记，用于定位出错所处的步骤
        :param task_result: 任务结果, dict
        :param label: 标签, str
        """
        for host in task_result["failed"]:
            host["errmsg"] = "[{}] {}: {}".format(self.COLLECTOR_NAME, label, host.get("errmsg", ""))
        logger.warning("Execute job task failed: result = %s" % json.dumps(task_result))
        return task_result

    # 使用jinjia的原因是为了让配置文件的模板适配节点管理的订阅机制
    def render_script_jinjia(self, directory, name, ctx):
        with open(os.path.join(pwd, directory, name), "r", encoding="utf-8") as fd:
            script_tpl = fd.read()
        template = Environment().from_string(script_tpl)

        return template.render(ctx or {})

    def generate_uptimecheck_config(self, task):
        protocol = task["protocol"]
        config = task["config"]

        dataid_map = {
            UptimeCheckProtocol.HTTP: settings.UPTIMECHECK_HTTP_DATAID,
            UptimeCheckProtocol.TCP: settings.UPTIMECHECK_TCP_DATAID,
            UptimeCheckProtocol.UDP: settings.UPTIMECHECK_UDP_DATAID,
            UptimeCheckProtocol.ICMP: settings.UPTIMECHECK_ICMP_DATAID,
        }

        params = {
            "data_id": dataid_map[protocol],
            "max_timeout": str(settings.UPTIMECHECK_DEFAULT_MAX_TIMEOUT) + "ms",
            "tasks": resource.uptime_check.generate_sub_config({"config": config, "protocol": protocol, "test": True}),
        }

        tpl_map = {
            UptimeCheckProtocol.HTTP: "bkmonitorbeat_http_global.conf.tpl",
            UptimeCheckProtocol.TCP: "bkmonitorbeat_tcp_global.conf.tpl",
            UptimeCheckProtocol.UDP: "bkmonitorbeat_udp_global.conf.tpl",
            UptimeCheckProtocol.ICMP: "bkmonitorbeat_icmp_global.conf.tpl",
        }
        if protocol not in list(tpl_map.keys()):
            raise UnknownProtocolError({"msg": protocol})

        return self.render_script_jinjia("template", tpl_map[protocol], params)

    def test(self, task, hosts=None):
        """
        下发测试配置
        """

        # 如果是动态拓扑，转化为主机
        node_ip_list = []
        if task["config"].get("node_list", []):
            params = {
                "bk_biz_id": task["bk_biz_id"],
                "hosts": task["config"]["node_list"],
                "output_fields": task["config"].get("output_fields", settings.UPTIMECHECK_OUTPUT_FIELDS),
            }
            node_ip_list = resource.uptime_check.topo_template_host(**params)
            task["config"]["node_list"] = []
        task["config"]["ip_list"] = task["config"].get("ip_list", []) + node_ip_list
        if not task["config"]["ip_list"] and not task["config"].get("url_list", []):
            raise CustomException(_("节点测试失败: 目标服务为空"))

        result = self.job_client.fast_execute_script(
            hosts=hosts, test_config_yml=self.generate_uptimecheck_config(task)
        )
        result = self.fetch_content(result)
        result = self.label_failed_ip(result, _("测试任务失败"))

        return result
