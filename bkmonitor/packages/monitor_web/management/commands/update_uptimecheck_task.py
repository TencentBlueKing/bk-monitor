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


import base64
import ntpath
import posixpath
import time

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import gettext as _

from bkmonitor.utils.common_utils import host_key, logger
from bkmonitor.utils.local import local
from core.drf_resource import api
from monitor.models import UptimeCheckNode, UptimeCheckTask

BASE_PATH_WINDOWS = settings.WINDOWS_GSE_AGENT_PATH
BASE_PATH_LINUX = settings.LINUX_GSE_AGENT_PATH
PLUGIN_PATH_LINUX = posixpath.join(BASE_PATH_LINUX, "plugins")
PLUGIN_PATH_WINDOWS = ntpath.join(BASE_PATH_WINDOWS, "plugins")
BIN_PATH_LINUX = posixpath.join(PLUGIN_PATH_LINUX, "bin")
BIN_PATH_WINDOWS = ntpath.join(PLUGIN_PATH_WINDOWS, "bin")
CONF_PATH_LINUX = posixpath.join(PLUGIN_PATH_LINUX, "etc")
CONF_PATH_WINDOWS = ntpath.join(PLUGIN_PATH_WINDOWS, "etc")
OLD_CONF = "uptimecheckbeat.conf"
BACKUP_CONF = "uptimecheckbeat.conf.task.bk"
EMPTY_CONF_LINUX = "/tmp/uptimecheckbeat.conf.empty"
EMPTY_CONF_WINDOWS = "c:\\temp\\uptimecheckbeat.conf.empty"
SCRIPT_PATH_LINUX = "{base}/packages/monitor_web/management/commands/script/mv_uptimecheck_linux".format(
    base=settings.BASE_DIR
)
SCRIPT_PATH_WINDOWS = "{base}/packages/monitor_web/management/commands/script/mv_uptimecheck_windows".format(
    base=settings.BASE_DIR
)


class Command(BaseCommand):
    def __init__(self):
        self.timestamp = 0
        self.os_type_dict = {}
        super(Command, self).__init__(self)

    def make_script_linux(self, node):
        f = open(SCRIPT_PATH_LINUX, "r")
        script_template = f.read()
        script_content = script_template.format(
            bin_path=BIN_PATH_LINUX,
            conf_path=CONF_PATH_LINUX,
            old_conf=OLD_CONF,
            backup_conf=BACKUP_CONF,
            empty_conf=EMPTY_CONF_LINUX,
            timestamp=self.timestamp,
            bk_biz_id=node.bk_biz_id,
            bk_cloud_id=node.plat_id,
            node_id=node.pk,
        )
        return script_content

    def make_script_windows(self, node):
        f = open(SCRIPT_PATH_WINDOWS, "r")
        script_template = f.read()
        script_content = script_template.format(
            bin_path=BIN_PATH_WINDOWS,
            conf_path=CONF_PATH_WINDOWS,
            old_conf=OLD_CONF,
            backup_conf=BACKUP_CONF,
            empty_conf=EMPTY_CONF_WINDOWS,
            timestamp=self.timestamp,
            bk_biz_id=node.bk_biz_id,
            bk_cloud_id=node.plat_id,
            node_id=node.pk,
        )
        return script_content

    def do_job(self, node, script_content, script_type, account):
        bk_biz_id = node.bk_biz_id
        script_content = base64.b64encode(script_content.encode("utf-8"))
        ip_list = [{"ip": node.ip, "bk_cloud_id": node.plat_id}]

        info = api.job.fast_execute_script(
            bk_biz_id=bk_biz_id,
            script_content=script_content.decode("utf-8"),
            script_type=script_type,
            ip_list=ip_list,
            account=account,
        )
        is_finished = False
        while not is_finished:
            time.sleep(3)
            result = api.job.get_job_instance_log(job_instance_id=info["job_instance_id"], bk_biz_id=bk_biz_id)
            is_finished = result[0].get("is_finished", False)
        if result[0]["status"] == 3 and result[0]["step_results"][0]["ip_status"] == 9:
            logger.info("节点%s拨测配置文件迁移完成" % host_key(ip=ip_list[0]["ip"], bk_cloud_id=ip_list[0]["bk_cloud_id"]))
            print(_("节点%s拨测配置文件迁移完成") % host_key(ip=ip_list[0]["ip"], bk_cloud_id=ip_list[0]["bk_cloud_id"]))
        else:
            logger.error("节点拨测配置文件迁移失败：%s" % result)
            print(_("节点拨测配置文件迁移失败：%s") % result)

    def get_system_by_node(self, nodes):
        bk_bik_id_list = list({node.bk_biz_id for node in nodes})
        host_list = []
        for i in bk_bik_id_list:
            ip_list = [{"ip": node.ip, "bk_cloud_id": node.plat_id} for node in nodes if node.bk_biz_id == i]
            host_list += api.cmdb.get_host_by_ip(ips=ip_list, bk_biz_id=i)
        return host_list

    # 逻辑：用空配置代替原uptimecheckbeat.conf配置，旧配置容错备份
    def move_old_conf(self, node):
        # bk_os_type	string	操作系统类型	1:Linux;2:Windows;3:AIX
        if self.os_type_dict[host_key(ip=node.ip, plat_id=node.plat_id)] == "1":
            script_content = self.make_script_linux(node)
            self.do_job(node, script_content, 1, "root")
        elif self.os_type_dict[host_key(ip=node.ip, plat_id=node.plat_id)] == "2":
            script_content = self.make_script_windows(node)
            self.do_job(node, script_content, 5, "system")
        elif self.os_type_dict[host_key(ip=node.ip, plat_id=node.plat_id)] == "3":
            pass
        else:
            print("unknown os type")

    def handle(self, **kwargs):
        self.timestamp = int(time.time())
        # 增加认证
        local.bk_username = "admin"
        # 获取所有node信息
        nodes = UptimeCheckNode.objects.all()
        host_list = self.get_system_by_node(nodes)
        for host in host_list:
            self.os_type_dict[host_key(ip=host.ip, plat_id=host.bk_cloud_id)] = host.bk_os_type
        for node in nodes:
            if host_key(ip=node.ip, plat_id=node.plat_id) in list(self.os_type_dict.keys()):
                # 逐个node获取task信息，过滤出旧拨测任务
                # 判断旧拨测的方案：订阅id为0，存在且状态为正常运行的任务
                tasks = node.tasks.filter(subscription_id=0, status=UptimeCheckTask.Status.RUNNING)
                for task in tasks:
                    #  对每个node下的任务调用deploy进行更新
                    task.deploy()
                    logger.info("任务 %s 增加订阅流程，创建订阅任务ID:%d" % (task.id, task.subscription_id))
                    print("任务 %s 增加订阅流程，创建订阅任务ID:%d" % (task.id, task.subscription_id))
                # 逐个node迁移旧拨测配置文件
                self.move_old_conf(node)
            else:
                logger.info("不存在节点%s对应的主机，请联系节点管理进行处理" % host_key(ip=node.ip, plat_id=node.plat_id))
                print(_("不存在节点%s对应的主机，请联系节点管理进行处理") % host_key(ip=node.ip, plat_id=node.plat_id))
