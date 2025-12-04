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
import ntpath
import os
import posixpath
from collections import defaultdict, namedtuple

import six
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext as _

from bkmonitor.utils.common_utils import host_key
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.user import get_admin_username
from core.drf_resource import api, resource

logger = logging.getLogger(__name__)

# 系统信息
SystemInfo = namedtuple("SystemInfo", ["bk_os_type", "script_ext", "job_execute_account", "script_type"])

windows_system_info = SystemInfo(
    bk_os_type="windows",
    script_ext=settings.WINDOWS_SCRIPT_EXT,
    job_execute_account=settings.WINDOWS_JOB_EXECUTE_ACCOUNT,
    script_type=settings.SCRIPT_TYPE_BAT,
)

linux_system_info = SystemInfo(
    bk_os_type="linux",
    script_ext=settings.LINUX_SCRIPT_EXT,
    job_execute_account=settings.LINUX_JOB_EXECUTE_ACCOUNT,
    script_type=settings.SCRIPT_TYPE_SHELL,
)

aix_system_info = SystemInfo(
    bk_os_type="aix",
    script_ext=settings.AIX_SCRIPT_EXT,
    job_execute_account=settings.AIX_JOB_EXECUTE_ACCOUNT,
    script_type=settings.SCRIPT_TYPE_SHELL,
)


class JobTaskClient:
    """
    JOB任务执行客户端
    """

    def __init__(self, bk_biz_id, operator=None):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        self.operator = operator or get_admin_username(bk_tenant_id=self.bk_tenant_id)

    @staticmethod
    def _get_system_info_dict():
        """
        JOB执行需要用到的关于系统的信息
        """
        return {
            "linux": linux_system_info,
            "windows": windows_system_info,
            "aix": aix_system_info,
        }

    def get_linux_setup_path(self, gse_agent_path=None):
        if not gse_agent_path:
            gse_agent_path = settings.LINUX_GSE_AGENT_PATH
        return posixpath.join(gse_agent_path, "plugins", "bin")

    def get_linux_conf_path(self):
        return posixpath.join(settings.LINUX_GSE_AGENT_PATH, "plugins", "etc")

    def get_windows_setup_path(self, gse_agent_path=None):
        if not gse_agent_path:
            gse_agent_path = settings.WINDOWS_GSE_AGENT_PATH
        return ntpath.join(gse_agent_path, "plugins", "bin")

    def get_windows_conf_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "plugins", "etc")

    def render_script(self, directory, name, cxt):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tpl_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "uptime_check", "collector")
        with open(os.path.join(tpl_path, directory, name), encoding="utf-8") as fd:
            script_tpl = fd.read()
        template = Template(script_tpl)

        return template.render(Context(cxt or {}))

    # 如果settings里配置了分割符，就生成对应的语句，否则传回空字符串
    def get_divide_symbol(self):
        return settings.DIVIDE_SYMBOL

    def execute_task_by_system_and_path(self, hosts, task_func):
        """
        根据系统类型执行用户给定的JOB任务并返回结果
        :param hosts: IP列表
        :param task_func: 任务定义
        :return:
        """
        task_results = []

        hosts_info, error_hosts = self.separate_hosts_by_system_and_path(hosts)
        # 按系统类型分别执行任务
        for system_info, setup_path, ip_list in hosts_info:
            task_result = task_func(system_info, setup_path, ip_list)
            task_results.append(task_result)

        # 任务结果合并
        merged_result = {
            "success": [],
            "pending": [],
            "failed": error_hosts,
        }

        for task_result in task_results:
            for status, ip_list in six.iteritems(merged_result):
                ip_list += task_result[status]

        return merged_result

    def separate_hosts_by_system_and_path(self, hosts):
        """
        将主机按系统类型进行分组，以便进行差异化的处理
        :rtype: dict[str, dict]
        """
        supported_systems = list(self._get_system_info_dict().keys())

        hosts_by_system_and_path = defaultdict(lambda: {"hosts": [], "system": None, "path": ""})
        error_hosts = []

        # 实时获取当前主机的操作系统
        all_hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=self.bk_biz_id)

        # 给业务下的所有主机建立索引，便于查找
        ip_os_dict = {}
        host_key_dict = {}
        for host in all_hosts:
            ip_os_dict[f"{host.bk_host_innerip}|{host.bk_cloud_id}"] = host.bk_os_type_name
            ip_os_dict[int(host.bk_host_id)] = host.bk_os_type_name
            host_key_dict[f"{host.bk_host_innerip}|{host.bk_cloud_id}"] = int(host.bk_host_id)

        bk_host_ids = [
            int(host["bk_host_id"]) if host.get("bk_host_id") else host_key_dict[f"{host['ip']}|{host['plat_id']}"]
            for host in hosts
        ]
        host_info = api.node_man.plugin_search(
            {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
        )["list"]
        host_path_dict = defaultdict()
        for host in host_info:
            if host.get("setup_path"):
                host_path_dict[host["bk_host_id"]] = host["setup_path"]
                host_path_dict[f"{host['inner_ip']}|{host['bk_cloud_id']}"] = host["setup_path"]

        for host in hosts:
            if host.get("bk_host_id"):
                host_id = int(host["bk_host_id"])
                host_dict = {"bk_host_id": host_id}
                host_name = f"bk_host_id:{host_id}"
            else:
                ip = host["ip"]
                bk_cloud_id = host.get("bk_cloud_id") or host.get("plat_id", 0)
                host_id = host_key(ip=ip, plat_id=bk_cloud_id)
                host_dict = {"ip": ip, "bk_cloud_id": bk_cloud_id}
                host_name = host_id

            if host_id not in ip_os_dict:
                error_hosts.append(
                    {"errmsg": _("{host_name} 主机不属于该业务").format(host_name=host_name), **host_dict}
                )
                continue
            bk_os_type = ip_os_dict[host_id]
            if bk_os_type in supported_systems:
                path = host_path_dict.get(host_id, "")
                host_type = (bk_os_type, path)
                hosts_by_system_and_path[host_type]["hosts"].append(host_dict)
                hosts_by_system_and_path[host_type]["path"] = path
                hosts_by_system_and_path[host_type]["system"] = bk_os_type
            elif not bk_os_type:
                error_hosts.append(
                    {"errmsg": _("{host_name} 操作系统类型不能为空").format(host_name=host_name), **host_dict}
                )
            else:
                error_hosts.append(
                    {
                        "errmsg": _("{host_name} 不支持的操作系统类型：{bk_os_type}").format(
                            host_name=host_name, bk_os_type=bk_os_type
                        ),
                        **host_dict,
                    }
                )

        # 删除主机列表为空的系统信息
        for k in list(hosts_by_system_and_path.keys()):
            if not hosts_by_system_and_path[k]["hosts"]:
                del hosts_by_system_and_path[k]

        return [
            (self._get_system_info_dict()[info["system"]], info["path"], info["hosts"])
            for info in list(hosts_by_system_and_path.values())
        ], error_hosts

    def render_context(self, system_info, attr_name, test_config_yml, setup_path):
        """
        :param attr_name: 属性名称
        :param system_info: 系统信息
        :param test_config_yml: 测试配置模版
        :param setup_path: gse路径
        :return:
        """
        # 生成执行脚本
        test_filename = "test_bkmonitorbeat.yml"
        script_content = self.render_script(
            "linux",
            "test.sh.tpl",
            {
                "divide_symbol": self.get_divide_symbol(),
                "test_config_file_path": posixpath.join(settings.LINUX_FILE_DOWNLOAD_PATH, test_filename),
                "test_config_yml": test_config_yml,
                "setup_path": self.get_linux_setup_path(setup_path),
                "download_path": settings.LINUX_FILE_DOWNLOAD_PATH,
            },
        )
        system_special = (
            dict(
                windows=dict(
                    script_content=self.render_script(
                        "windows",
                        "test.bat.tpl",
                        {
                            "divide_symbol": self.get_divide_symbol(),
                            "test_config_file_path": posixpath.join(settings.WINDOWS_FILE_DOWNLOAD_PATH, test_filename),
                            "test_config_yml": test_config_yml,
                            "setup_path": self.get_windows_setup_path(setup_path),
                            "download_path": settings.WINDOWS_FILE_DOWNLOAD_PATH,
                        },
                    ),
                ),
            ),
        )

        if system_info.bk_os_type in system_special:
            return system_special[system_info.bk_os_type].get(attr_name, script_content)
        return script_content

    def fast_execute_script(self, hosts, test_config_yml):
        """
        快速执行脚本
        :param hosts: IP列表
        :param test_config_yml: 测试配置模板
        :return:
        """
        result = self.execute_task_by_system_and_path(
            hosts=hosts,
            task_func=lambda system_info, setup_path, host_list: resource.commons.fast_execute_script(
                host_list=host_list,
                bk_biz_id=self.bk_biz_id,
                account_alias=system_info.job_execute_account,
                script_content=self.render_context(system_info, "script_content", test_config_yml, setup_path),
                script_type=system_info.script_type,
            ),
        )
        return result
