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
import base64
import json
import logging
import ntpath
import os
import posixpath
import traceback

import six
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import ugettext as _
from jinja2 import Template as JTemplate
from monitor.constants import UptimeCheckProtocol
from monitor_web.commons.job import JobTaskClient

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from core.errors.uptime_check import DeprecatedFunctionError, UnknownProtocolError

logger = logging.getLogger(__name__)


class CollectorInstallWay(object):
    """采集器安装方式"""

    BUILD_IN = 0
    ZIP_FILE = 1
    EXE_FILE = 2


class GenericCollector(six.with_metaclass(abc.ABCMeta, object)):
    """
    采集器基类
    """

    def __init__(self, bk_biz_id, operator=None, *args, **kwargs):
        self.job_client = JobTaskClient(bk_biz_id=bk_biz_id, operator=operator)

    def label_failed_ip(self, task_result, label):
        """
        对JOB失败的任务进行标记，用于定位出错所处的步骤
        :param task_result: 任务结果, dict
        :param label: 标签, str
        """
        return self.job_client.label_failed_ip(task_result, label)

    def start_deposit(self, *args, **kwargs):
        """
        启动托管程序
        """
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def stop_deposit(self, *args, **kwargs):
        """
        停用托管程序
        """
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def test(self, *args, **kwargs):
        """
        执行采集器测试流程
        """
        raise NotImplementedError

    def deploy(self, *args, **kwargs):
        """
        下发采集器
        """
        raise NotImplementedError


class StandardCollector(six.with_metaclass(abc.ABCMeta, GenericCollector)):
    """
    标准组件
    """

    # 通用配置
    COLLECTOR_NAME = None  # 采集器名称
    COLLECTOR_VERSION = None  # 采集器版本号

    # linux系统配置
    LINUX_SETUP_PATH = ""  # 采集器安装路径
    LINUX_COLLECTOR_FILENAME = ""  # 采集器下发的文件名称（默认为tar.gz压缩文件）
    LINUX_COLLECTOR_FILE_PATH = ""  # 采集器在本地的存放路径
    LINUX_PROC_NAME = ""  # 采集器在运行时，其可执行文件的名称，用于agent判断进程是否启动成功
    LINUX_PID_PATH = ""  # 进程ID文件存放路径
    LINUX_LOG_PATH = ""  # 日志存放路径
    LINUX_DATA_PATH = ""  # 存放DB文件等动态生成的文件路径
    LINUX_CONF_PATH = ""  # 配置文件路径
    LINUX_CONFIG_NAME = ""  # 配置文件名称

    # windows系统配置
    WINDOWS_SETUP_PATH = ""  # 采集器安装路径
    WINDOWS_COLLECTOR_FILENAME = ""  # 采集器下发的文件名称
    WINDOWS_COLLECTOR_FILE_PATH = ""  # 采集器在本地的存放路径
    WINDOWS_PROC_NAME = ""  # 采集器在运行时，其可执行文件的名称，用于agent判断进程是否启动成功
    WINDOWS_PID_PATH = ""  # 进程ID文件存放路径
    WINDOWS_LOG_PATH = ""  # 日志存放路径
    WINDOWS_DATA_PATH = ""  # 存放DB文件等动态生成的文件路径
    WINDOWS_CONF_PATH = ""  # 配置文件路径
    WINDOWS_CONFIG_NAME = ""  # 配置文件名称

    # aix 系统配置
    AIX_SETUP_PATH = ""  # 采集器安装路径
    AIX_COLLECTOR_FILENAME = ""  # 采集器下发的文件名称（默认为tar.gz压缩文件）
    AIX_COLLECTOR_FILE_PATH = ""  # 采集器在本地的存放路径
    AIX_PROC_NAME = ""  # 采集器在运行时，其可执行文件的名称，用于agent判断进程是否启动成功
    AIX_PID_PATH = ""  # 进程ID文件存放路径
    AIX_LOG_PATH = ""  # 日志存放路径
    AIX_DATA_PATH = ""  # 存放DB文件等动态生成的文件路径
    AIX_CONF_PATH = ""  # 配置文件路径
    AIX_CONFIG_NAME = ""  # 配置文件名称

    # 如果settings里配置了分割符，就生成对应的语句，否则传回空字符串
    def get_divide_symbol(self):
        return settings.DIVIDE_SYMBOL

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
            host["errmsg"] = "[{}] {}: {}".format(self.get_collector_name(), label, host.get("errmsg", ""))
        logger.warning("Execute job task failed: result = %s" % json.dumps(task_result))
        return task_result

    def get_collector_name(self):
        return self.COLLECTOR_NAME

    def get_collector_version(self):
        return self.COLLECTOR_VERSION

    def get_linux_setup_path(self):
        return self.LINUX_SETUP_PATH

    def get_linux_collector_filename(self):
        return self.LINUX_COLLECTOR_FILENAME

    def get_linux_collector_file_path(self):
        return self.LINUX_COLLECTOR_FILE_PATH

    def get_linux_proc_name(self):
        return self.LINUX_PROC_NAME

    def get_linux_pid_path(self):
        """
        采集器PID文件所在路径
        """
        default = posixpath.join(self.get_linux_setup_path(), "%s.pid" % self.get_collector_name())
        return self.LINUX_PID_PATH or default

    def get_linux_version_script(self):
        """
        获取采集器当前版本号脚本模版
        """
        return "cd {setup_path} && cat VERSION".format(setup_path=self.LINUX_SETUP_PATH)

    def get_linux_install_script(self):
        """
        采集器重装操作脚本模版
        """
        return "mkdir -p {setup_path} && cd {setup_path} && tar -zxf {download_path} && ./install.sh".format(
            setup_path=self.get_linux_setup_path(),
            download_path=posixpath.join(settings.LINUX_FILE_DOWNLOAD_PATH, self.get_linux_collector_filename()),
        )

    def get_linux_log_path(self):
        return self.LINUX_LOG_PATH or self.get_linux_setup_path()

    def get_linux_data_path(self):
        return self.LINUX_DATA_PATH or self.get_linux_setup_path()

    def get_linux_conf_path(self):
        return self.LINUX_CONF_PATH or self.get_linux_setup_path()

    def get_linux_config_name(self):
        default = "%s.yml" % self.get_collector_name()
        return self.LINUX_CONFIG_NAME or default

    def get_windows_setup_path(self):
        return self.WINDOWS_SETUP_PATH

    def get_windows_collector_filename(self):
        return self.WINDOWS_COLLECTOR_FILENAME

    def get_windows_collector_file_path(self):
        return self.WINDOWS_COLLECTOR_FILE_PATH

    def get_windows_proc_name(self):
        return self.WINDOWS_PROC_NAME

    def get_windows_pid_path(self):
        """
        采集器PID文件所在路径
        """
        default = ntpath.join(self.get_windows_setup_path(), "%s.pid" % self.get_collector_name())
        return self.WINDOWS_PID_PATH or default

    def get_windows_version_script(self):
        """
        获取采集器当前版本号脚本模版
        """
        return "@echo off && cd {setup_path} && type VERSION".format(setup_path=self.WINDOWS_SETUP_PATH)

    def get_windows_install_script(self):
        """
        采集器重装操作脚本模版
        """
        return "{download_path} -y -o{setup_path} && cd {setup_path} && install.bat".format(
            setup_path=self.get_windows_setup_path(),
            download_path=ntpath.join(settings.WINDOWS_FILE_DOWNLOAD_PATH, self.get_windows_collector_filename()),
        )

    def get_windows_log_path(self):
        return self.WINDOWS_LOG_PATH or self.get_windows_setup_path()

    def get_windows_data_path(self):
        return self.WINDOWS_DATA_PATH or self.get_windows_setup_path()

    def get_windows_conf_path(self):
        return self.WINDOWS_CONF_PATH or self.get_windows_setup_path()

    def get_windows_config_name(self):
        default = "%s.yml" % self.get_collector_name()
        return self.WINDOWS_CONFIG_NAME or default

    def get_aix_setup_path(self):
        return self.AIX_SETUP_PATH

    def get_aix_collector_filename(self):
        return self.AIX_COLLECTOR_FILENAME

    def get_aix_collector_file_path(self):
        return self.AIX_COLLECTOR_FILE_PATH

    def get_aix_proc_name(self):
        return self.AIX_PROC_NAME

    def get_aix_pid_path(self):
        """
        采集器PID文件所在路径
        """
        default = posixpath.join(self.get_aix_setup_path(), "%s.pid" % self.get_collector_name())
        return self.AIX_PID_PATH or default

    def get_aix_version_script(self):
        """
        获取采集器当前版本号脚本模版
        """
        return "cd {setup_path} && cat VERSION".format(setup_path=self.AIX_SETUP_PATH)

    def get_aix_install_script(self):
        """
        采集器重装操作脚本模版
        """
        return "mkdir -p {setup_path} && cd {setup_path} && tar -zxf {download_path} && ./install.sh".format(
            setup_path=self.get_aix_setup_path(),
            download_path=posixpath.join(settings.AIX_FILE_DOWNLOAD_PATH, self.get_aix_collector_filename()),
        )

    def get_aix_log_path(self):
        return self.AIX_LOG_PATH or self.get_aix_setup_path()

    def get_aix_data_path(self):
        return self.AIX_DATA_PATH or self.get_aix_setup_path()

    def get_aix_conf_path(self):
        return self.AIX_CONF_PATH or self.get_aix_setup_path()

    def get_aix_config_name(self):
        default = "%s.yml" % self.get_collector_name()
        return self.AIX_CONFIG_NAME or default

    def check_update_required(self, hosts):
        """
        检查是否需要升级
        :return: 不需要升级的IP，需要升级的IP，未知的IP
        """
        if self.install_way == CollectorInstallWay.BUILD_IN:
            # Agent内置组件无需升级
            return hosts, [], []

        hosts_not_required = []
        hosts_required = []
        hosts_unknown = []

        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content=self.get_linux_version_script(),
            system_special=dict(
                windows=dict(
                    script_content=self.get_windows_version_script(),
                ),
                aix=dict(
                    script_content=self.get_aix_version_script(),
                ),
            ),
        )
        result = self.label_failed_ip(result, _("查询采集器版本失败"))

        # 脚本执行错误的IP标为未知状态
        hosts_unknown += result["failed"]

        for host in result["success"]:
            # 比对版本信息
            version_info = host["log_content"].strip()
            if version_info == self.get_collector_version():
                hosts_not_required.append(host)
            else:
                hosts_required.append(host)

        return hosts_not_required, hosts_required, hosts_unknown

    @staticmethod
    def version_str_to_tuple(version_string):
        """
        将版本号字符串转化为元祖，用于比较
        """
        return tuple([int(num) for num in version_string.split(".")])

    def upgrade_or_install(self, hosts):
        if self.install_way == CollectorInstallWay.BUILD_IN:
            return {
                "success": hosts,
                "pending": [],
                "failed": [],
            }

        if self.install_way == CollectorInstallWay.ZIP_FILE:
            hosts_update_not_required, hosts_update_required, hosts_update_unknown = self.check_update_required(hosts)
            hosts_deploy_required = hosts_update_required + hosts_update_unknown
            self.deploy(hosts_deploy_required)
            upgrade_result = self.upgrade(hosts_update_required)
            install_result = self.unzip_and_install(hosts_update_unknown)
            result = {
                "success": hosts_update_not_required + upgrade_result["success"] + install_result["success"],
                "pending": upgrade_result["pending"] + install_result["pending"],
                "failed": upgrade_result["failed"] + install_result["failed"],
            }
            return result

        hosts_to_install = []
        hosts_not_install = []

        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content="cd {setup_path} && ./{collector_name} -v".format(
                setup_path=self.get_linux_setup_path(),
                collector_name=self.get_collector_name(),
            ),
            system_special=dict(
                windows=dict(
                    script_content="@echo off && cd {setup_path} && {collector_name}.exe -v".format(
                        setup_path=self.get_windows_setup_path(),
                        collector_name=self.get_collector_name(),
                    )
                )
            ),
        )
        result = self.label_failed_ip(result, _("查询采集器版本失败"))

        # 脚本执行错误的IP标为未知状态
        hosts_to_install += result["failed"]

        for host in result["success"]:
            # 比对版本信息
            version_info = host["log_content"].strip()
            try:
                if self.version_str_to_tuple(version_info) < self.version_str_to_tuple(self.get_collector_version()):
                    # 版本号小于目标版本号，需要更新
                    hosts_to_install.append(host)
                else:
                    hosts_not_install.append(host)
            except Exception:
                # 版本号获取失败，需要更新
                hosts_to_install.append(host)

        linux_collector_full_name = "{}-{}".format(self.get_collector_name(), self.get_collector_version())
        linux_collector_file_dir = os.path.dirname(self.get_linux_collector_file_path())
        with open(os.path.join(linux_collector_file_dir, linux_collector_full_name), "rb") as fd:
            linux_collector_content = fd.read()

        windows_collector_full_name = "{}-{}.exe".format(self.get_collector_name(), self.get_collector_version())
        windows_collector_file_dir = os.path.dirname(self.get_windows_collector_file_path())
        with open(os.path.join(windows_collector_file_dir, windows_collector_full_name), "rb") as fd:
            windows_collector_content = fd.read()

        move_result = self.job_client.fast_execute_script(
            hosts=hosts_to_install,
            script_content="cd {setup_path} && mv -f {collector_name} {collector_name}.bak".format(
                setup_path=self.get_linux_setup_path(),
                collector_name=self.get_collector_name(),
            ),
            system_special=dict(
                windows=dict(
                    script_content=(
                        "@echo off && cd {setup_path} && move /Y {collector_name}.exe {collector_name}.exe.bak".format(
                            setup_path=self.get_windows_setup_path(),
                            collector_name=self.get_collector_name(),
                        )
                    )
                )
            ),
        )

        logger.info("[move {}]：{}".format(self.get_collector_name(), str(move_result)))

        result = self.job_client.gse_push_file(
            hosts=hosts_to_install,
            path=self.get_linux_setup_path(),
            file_list=[{"file_name": self.get_collector_name(), "content": linux_collector_content}],
            system_special=dict(
                windows=dict(
                    path=self.get_windows_setup_path(),
                    file_list=[
                        {"file_name": "%s.exe" % self.get_collector_name(), "content": windows_collector_content}
                    ],
                )
            ),
        )
        result = self.label_failed_ip(result, _("采集器下发失败"))
        return {
            "success": hosts_not_install + result["success"],
            "pending": [],
            "failed": result["failed"],
        }

    def upgrade_or_install_then_deposit(self, hosts):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def unzip_and_install(self, hosts):
        """
        解压并执行安装程序
        """
        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content=self.get_linux_install_script(),
            system_special=dict(
                windows=dict(
                    script_content=self.get_windows_install_script(),
                ),
                aix=dict(
                    script_content=self.get_aix_install_script(),
                ),
            ),
        )
        result = self.label_failed_ip(result, _("采集器安装失败"))
        return result

    def _execute_deposit(self, hosts, operate_type):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def check_deposit(self, hosts):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def reload_deposit(self, hosts):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def reload_or_restart_process(self, hosts):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def deploy(self, hosts):
        """
        下发采集器
        """
        if os.path.exists(self.get_linux_collector_file_path()):
            with open(self.get_linux_collector_file_path(), "rb") as fd:
                linux_collector_content = fd.read()
        else:
            linux_collector_content = None

        if os.path.exists(self.get_windows_collector_file_path()):
            with open(self.get_windows_collector_file_path(), "rb") as fd:
                windows_collector_content = fd.read()
        else:
            windows_collector_content = None

        result = self.job_client.gse_push_file(
            hosts=hosts,
            path=settings.LINUX_FILE_DOWNLOAD_PATH,
            file_list=[{"file_name": self.get_linux_collector_filename(), "content": linux_collector_content}]
            if linux_collector_content
            else [],
            system_special=dict(
                windows=dict(
                    path=settings.WINDOWS_FILE_DOWNLOAD_PATH,
                    file_list=[
                        {"file_name": self.get_windows_collector_filename(), "content": windows_collector_content}
                    ]
                    if windows_collector_content
                    else [],
                )
            ),
        )
        result = self.label_failed_ip(result, _("采集器下发失败"))
        return result

    def deploy_config_and_deposit(self, hosts, config, is_delete_mode=False):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def deploy_config(self, hosts, config, is_delete_mode=False):
        """
        配置下发
        """
        return dict(success=hosts, pending=[], failed=[])

    def install(self, hosts):
        return self._execute_script_in_setup_path("install", hosts)

    def check(self, hosts):
        return self._execute_script_in_setup_path("check", hosts)

    def reload(self, hosts):
        return self._execute_script_in_setup_path("reload", hosts)

    def restart(self, hosts):
        return self._execute_script_in_setup_path("restart", hosts)

    def start(self, hosts):
        return self._execute_script_in_setup_path("start", hosts)

    def stop(self, hosts):
        return self._execute_script_in_setup_path("stop", hosts)

    def test(self, hosts, cmd_args=None):
        return self._execute_script_in_setup_path("test", hosts, cmd_args, cmd_args)

    def uninstall(self, hosts):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def upgrade(self, hosts):
        linux_cmd_args = posixpath.join(settings.LINUX_FILE_DOWNLOAD_PATH, self.get_linux_collector_filename())
        windows_cmd_args = ntpath.join(settings.WINDOWS_FILE_DOWNLOAD_PATH, self.get_windows_collector_filename())
        aix_cmd_args = ntpath.join(settings.AIX_FILE_DOWNLOAD_PATH, self.get_aix_collector_filename())
        return self._execute_script_in_setup_path("upgrade", hosts, linux_cmd_args, windows_cmd_args, aix_cmd_args)

    def _execute_script_in_setup_path(
        self, script_name, hosts, linux_cmd_args="", windows_cmd_args="", aix_cmd_args=""
    ):
        """
        在采集器路径下执行标准化脚本
        :param hosts: IP列表
        :param script_name: 脚本名称
        :param linux_cmd_args: 命令行参数字符串 for linux
        :param windows_cmd_args: 命令行参数字符串 for windows
        :param aix_cmd_args: 命令行参数字符串 for aix
        """
        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content="cd {setup_path} && ./{script_name}.sh {cmd_args}".format(
                setup_path=self.get_linux_setup_path(), script_name=script_name, cmd_args=linux_cmd_args
            ),
            system_special=dict(
                windows=dict(
                    script_content="cd {setup_path} && {script_name}.bat {cmd_args}".format(
                        setup_path=self.get_windows_setup_path(), script_name=script_name, cmd_args=windows_cmd_args
                    ),
                ),
                aix=dict(
                    script_content="cd {setup_path} && ./{script_name}.sh {cmd_args}".format(
                        setup_path=self.get_aix_setup_path(), script_name=script_name, cmd_args=aix_cmd_args
                    ),
                ),
            ),
        )

        result = self.label_failed_ip(result, _("执行脚本 %s 失败") % script_name)
        return result

    @property
    def install_way(self):
        return CollectorInstallWay.EXE_FILE


pwd = os.path.dirname(os.path.realpath(__file__))


class UptimeCheckCollector(StandardCollector):
    """
    uptimecheckbeat采集器
    """

    # 通用配置
    COLLECTOR_NAME = "uptimecheckbeat"
    COLLECTOR_VERSION = "1.4.10"

    # linux系统配置
    LINUX_COLLECTOR_FILENAME = "uptimecheckbeat-%s-linux.tar.gz" % COLLECTOR_VERSION
    LINUX_COLLECTOR_FILE_PATH = os.path.join(pwd, "linux", LINUX_COLLECTOR_FILENAME)
    LINUX_PROC_NAME = "uptimecheckbeat"

    # windows系统配置
    WINDOWS_COLLECTOR_FILENAME = "uptimecheckbeat-%s-windows.exe" % COLLECTOR_VERSION
    WINDOWS_COLLECTOR_FILE_PATH = os.path.join(pwd, "windows", WINDOWS_COLLECTOR_FILENAME)
    WINDOWS_PROC_NAME = "uptimecheckbeat"

    def get_linux_setup_path(self):
        return posixpath.join(settings.LINUX_GSE_AGENT_PATH, "plugins", "bin")

    def get_linux_conf_path(self):
        return posixpath.join(settings.LINUX_GSE_AGENT_PATH, "plugins", "etc")

    def get_linux_config_name(self):
        return settings.LINUX_UPTIME_CHECK_COLLECTOR_CONF_NAME

    def get_linux_data_path(self):
        return settings.LINUX_PLUGIN_DATA_PATH

    def get_linux_log_path(self):
        return settings.LINUX_PLUGIN_LOG_PATH

    def get_linux_pid_path(self):
        return posixpath.join(settings.LINUX_PLUGIN_PID_PATH, "uptimecheckbeat.pid")

    def get_windows_setup_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "plugins", "bin")

    def get_windows_conf_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "plugins", "etc")

    def get_windows_config_name(self):
        return settings.WINDOWS_UPTIME_CHECK_COLLECTOR_CONF_NAME

    def get_windows_data_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "data")

    def get_windows_log_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "logs")

    def get_windows_pid_path(self):
        return ntpath.join(settings.WINDOWS_GSE_AGENT_PATH, "logs", "uptimecheckbeat.pid")

    def get_windows_output_config(self):
        return {
            "output.gse": {"endpoint": settings.WINDOWS_GSE_AGENT_IPC_PATH},
            "path.logs": self.get_windows_log_path(),
            "path.data": self.get_windows_data_path(),
            "path.pid": ntpath.dirname(self.get_windows_pid_path()),
        }

    def get_linux_output_config(self):
        return {
            "output.gse": {"endpoint": settings.LINUX_GSE_AGENT_IPC_PATH},
            "path.logs": self.get_linux_log_path(),
            "path.data": self.get_linux_data_path(),
            "path.pid": posixpath.dirname(self.get_linux_pid_path()),
        }

    def deploy_config(self, hosts, hosts_config=None):
        """
        配置下发
        :param hosts_config: kv对，host_key: config
        """

        def deploy_config_by_system(system_info, ip_list):
            params = []

            # 由于每台机器的配置各不相同，这里只能对每台主机配置进行更新再逐台下发，这里用到多线程提高执行效率
            for host in ip_list:
                if system_info.bk_os_type == "linux":
                    config_yml = resource.uptime_check.generate_config(
                        {"ip": host["ip"], "output_config": self.get_linux_output_config()}
                    )
                else:
                    config_yml = resource.uptime_check.generate_config(
                        {"ip": host["ip"], "output_config": self.get_windows_output_config()}
                    )

                param = {
                    "ip_list": [host],
                    "bk_biz_id": self.job_client.bk_biz_id,
                    "account": system_info.job_execute_account,
                }
                if system_info.bk_os_type == "linux":
                    param.update(
                        {
                            "file_target_path": self.get_linux_conf_path(),
                            "file_list": [
                                {
                                    "file_name": self.get_linux_config_name(),
                                    "content": base64.b64encode(config_yml).decode("utf-8"),
                                }
                            ],
                        }
                    )
                else:
                    param.update(
                        {
                            "file_target_path": self.get_windows_conf_path(),
                            "file_list": [
                                {
                                    "file_name": self.get_windows_config_name(),
                                    "content": base64.b64encode(config_yml).decode("utf-8"),
                                }
                            ],
                        }
                    )
                params.append(param)

            # 并发请求
            task_results = resource.commons.fast_push_file.bulk_request(params)

            # 任务结果合并
            merged_result = {
                "success": [],
                "pending": [],
                "failed": [],
            }

            for task_result in task_results:
                for status, ip_list in six.iteritems(merged_result):
                    ip_list += task_result[status]

            return merged_result

        result = self.job_client.execute_task_by_system(hosts, task_func=deploy_config_by_system)
        result = self.label_failed_ip(result, _("配置下发失败"))
        return result

    def render_script(self, directory, name, cxt):
        with open(os.path.join(pwd, directory, name), "r", encoding="utf-8") as fd:
            script_tpl = fd.read()
        template = Template(script_tpl)

        return template.render(Context(cxt or {}))

    # 使用jinjia的原因是为了让配置文件的模板适配节点管理的订阅机制
    def render_script_jinjia(self, directory, name, ctx):
        with open(os.path.join(pwd, directory, name), "r", encoding="utf-8") as fd:
            script_tpl = fd.read()
        template = JTemplate(script_tpl)

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

        # 生成配置文件
        test_config_yml = self.generate_uptimecheck_config(task)

        # 生成执行脚本
        test_filename = "test_bkmonitorbeat.yml"
        linux_script_content = self.render_script(
            "linux",
            "test.sh.tpl",
            {
                "divide_symbol": self.get_divide_symbol(),
                "test_config_file_path": posixpath.join(settings.LINUX_FILE_DOWNLOAD_PATH, test_filename),
                "test_config_yml": test_config_yml,
                "setup_path": self.get_linux_setup_path(),
                "download_path": settings.LINUX_FILE_DOWNLOAD_PATH,
            },
        )
        windows_script_content = self.render_script(
            "windows",
            "test.bat.tpl",
            {
                "divide_symbol": self.get_divide_symbol(),
                "test_config_file_path": posixpath.join(settings.WINDOWS_FILE_DOWNLOAD_PATH, test_filename),
                "test_config_yml": test_config_yml,
                "setup_path": self.get_windows_setup_path(),
                "download_path": settings.WINDOWS_FILE_DOWNLOAD_PATH,
            },
        )

        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content=linux_script_content,
            system_special=dict(
                windows=dict(
                    script_content=windows_script_content,
                ),
            ),
        )
        result = self.fetch_content(result)
        result = self.label_failed_ip(result, _("测试任务失败"))

        return result

    def run_test(self, hosts, test_config_filename):
        result = self.job_client.fast_execute_script(
            hosts=hosts,
            script_content=(
                "cd {setup_path} && ./{collector_name} -T -E {collector_name}.mode=check "
                "-E path.pid=/tmp -path.data /tmp -path.logs /tmp -c {test_config_path}".format(
                    setup_path=self.get_linux_setup_path(),
                    collector_name=self.COLLECTOR_NAME,
                    test_config_path=posixpath.join(settings.LINUX_FILE_DOWNLOAD_PATH, test_config_filename),
                )
            ),
            system_special=dict(
                windows=dict(
                    script_content=(
                        "@echo off && cd {setup_path} && {collector_name}.exe -T -E {collector_name}."
                        "mode=check -E path.pid=C:\\Temp -path.logs C:\\Temp -path.data C:\\Temp"
                        " -c {test_config_path}".format(
                            setup_path=self.get_windows_setup_path(),
                            collector_name=self.COLLECTOR_NAME,
                            test_config_path=ntpath.join(settings.WINDOWS_FILE_DOWNLOAD_PATH, test_config_filename),
                        )
                    ),
                )
            ),
        )

        result = self.label_failed_ip(result, _("脚本测试执行失败"))
        return result
