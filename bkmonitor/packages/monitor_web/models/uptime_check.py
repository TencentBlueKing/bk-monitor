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


from django.conf import settings
from django.utils.translation import gettext as _

from monitor.models import UptimeCheckGroup as base_UptimeCheckGroup
from monitor.models import UptimeCheckNode as base_UptimeCheckNode
from monitor.models import UptimeCheckTask as base_UptimeCheckTask
from monitor.models import (
    UptimeCheckTaskCollectorLog as base_UptimeCheckTaskCollectorLog,
)


class UptimeCheckNode(base_UptimeCheckNode):
    class Meta:
        proxy = True

    # 监控平台3.3拨测节点使用bkmonitorbeat，通过节点管理安装后，自动拥有拨测能力，
    # 配置拨测任务后，通过节点管理创建订阅并管理拨测任务配置
    # 因此不再需要监控自身维护拨测采集器的安装/卸载
    def uninstall_agent(self):
        pass

    def install_agent(self):
        pass

    @classmethod
    def adapt_new_node_id(cls, bk_biz_id, node_id):
        """
        适配新版的 bk_cloud_id:ip 的拨测节点
        :param bk_biz_id: 业务ID
        :param node_id: 上报的节点ID
        :return: nodes -> list
        """
        nodes = []
        old_format = False
        try:
            # 若还是数字ID, 则说明为旧格式
            node_id = int(node_id)
            if node_id == 0:
                # 老格式（使用订阅下发 bkmonitorbeat，但未上报node_id，因此我们也不知道是哪个拨测节点）
                nodes = list(cls.objects.filter(bk_biz_id=bk_biz_id).values())
            else:
                # 远古格式（通过uptimecheckbeat 上报的数据）
                nodes = list(cls.objects.filter(bk_biz_id=bk_biz_id, id=node_id).values())

            old_format = True

        except ValueError:
            # 适配新格式 bk_cloud_id:ip
            bk_cloud_id, ip = node_id.rsplit(":", 1)
            nodes = list(cls.objects.filter(bk_biz_id=bk_biz_id, plat_id=bk_cloud_id, ip=ip).values())

        finally:
            for node in nodes:
                if old_format:
                    node["name"] = node["name"] + _("bkmonitorbeat(版本低于{}, 请升级)").format(
                        settings.BKMONITORBEAT_SUPPORT_NEW_NODE_ID_VERSION
                    )
                node["id"] = f"{node['plat_id']}:{node['ip']}"
            return nodes


class UptimeCheckTask(base_UptimeCheckTask):
    class Meta:
        proxy = True


class UptimeCheckTaskCollectorLog(base_UptimeCheckTaskCollectorLog):
    class Meta:
        proxy = True


class UptimeCheckGroup(base_UptimeCheckGroup):
    class Meta:
        proxy = True
