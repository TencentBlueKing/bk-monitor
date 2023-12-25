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

import hashlib
import os
import subprocess
import traceback
from functools import reduce

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import ugettext as _

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.utils.db.fields import ConfigDataField, JsonField, SymmetricJsonField
from common.log import logger
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from core.errors.uptime_check import DeprecatedFunctionError
from monitor.constants import UPTIME_CHECK_DB, UptimeCheckProtocol
from monitor_web.models import OperateRecordModelBase
from monitor_web.tasks import append_metric_list_cache, update_task_running_status


class OperateRecordModel(OperateRecordModelBase):
    class Meta:
        abstract = True


class RolePermission(OperateRecordModel):
    """
    角色权限（被用于iam权限升级）
    """

    biz_id = models.IntegerField("业务ID")
    role = models.CharField("角色", max_length=128)
    permission = models.CharField("权限", max_length=32, default="", blank=True)


# 配置相关使用key-value形式存储
# key的格式: '[dashboard_view_config]:menu_id=1'
class UserConfig(models.Model):
    """用户配置信息"""

    username = models.CharField("用户名", max_length=30)
    key = models.CharField("key", max_length=255)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("用户配置信息")
        unique_together = (("username", "key"),)


class ApplicationConfig(models.Model):
    """业务配置信息"""

    cc_biz_id = models.IntegerField("业务id")
    key = models.CharField("key", max_length=255)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("业务配置信息")
        unique_together = (("cc_biz_id", "key"),)


class GlobalConfig(models.Model):
    """全局配置信息"""

    key = models.CharField("key", max_length=255, unique=True)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("全局配置信息")


NODE_IP_TYPE_CHOICES = [(0, "all"), (4, "IPv4"), (6, "IPv6")]

NODE_IP_TYPE_DICT = {status: desc for (status, desc) in NODE_IP_TYPE_CHOICES}


class UptimeCheckNode(OperateRecordModel):
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    is_common = models.BooleanField("是否为通用节点", default=False, db_index=True)
    biz_scope = JsonField("指定业务可见范围", default=[])
    ip_type = models.IntegerField("IP类型", default=4, choices=NODE_IP_TYPE_CHOICES)
    name = models.CharField("节点名称", max_length=50)

    ip = models.CharField("IP地址", blank=True, null=True, default="", max_length=64)
    bk_host_id = models.IntegerField("主机ID", null=True, blank=True)
    plat_id = models.IntegerField("云区域ID", blank=True, null=True, default=0)
    # 地点改为可选
    location = JsonField("地区", default="{}")
    carrieroperator = models.CharField("外网运营商", max_length=50, blank=True, null=True, default="")

    @property
    def full_table_name(self):
        return "{}_{}_{}".format(self.bk_biz_id, UPTIME_CHECK_DB, "heartbeat")

    @property
    def permission_exempt(self):
        return True

    def set_host_id(self):
        # 补全更新bk_host_id
        if self.bk_host_id:
            return self.bk_host_id
        hosts = api.cmdb.get_host_by_ip(ips=[{"ip": self.ip, "bk_cloud_id": self.plat_id}], bk_biz_id=self.bk_biz_id)
        if hosts:
            UptimeCheckNode.objects.filter(id=self.pk).update(bk_host_id=hosts[0].bk_host_id)
            return hosts[0].bk_host_id
        else:
            logger.info(f"拨测节点{self.name}（{self.ip}|{self.plat_id}）回填host_id失败，不存在对应cmdb主机实例")

    def uninstall_agent(self):
        """
        卸载采集器
        取消采集器gse托管 -> 停止采集器进程 -> 删除配置文件和采集器
        """
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def install_agent(self):
        raise DeprecatedFunctionError(msg=traceback.extract_stack()[-1][2])

    def save(self, update=False, *args, **kwargs):
        """
        保存拨测节点
        :return:
        """
        # 数据验证
        self.validate_data(update)

        super(UptimeCheckNode, self).save(*args, **kwargs)

    def delete(self, force=False, *args, **kwargs):
        """
        删除拨测节点
        """
        if not force:
            # 删除前需要先确保该节点上没有正在执行的拨测任务
            tasks = self.tasks.all()
            task_name = ";".join([task.name for task in tasks if (task.status == task.Status.RUNNING)])
            if len(self.tasks.all()) != 0:
                raise CustomException(_("该节点存在以下运行中的拨测任务：%s，" + _("请先暂停或删除相关联的任务")) % task_name)
        super(UptimeCheckNode, self).delete(*args, **kwargs)

    def validate_data(self, update):
        """
        用于在保存之前对拨测节点进行输入验证
        """
        if is_ipv6_biz(self.bk_biz_id):
            validate_dict = {"bk_host_id": self.bk_host_id}
        else:
            if self.bk_host_id:
                host = api.cmdb.get_host_by_id(bk_biz_id=self.bk_biz_id, bk_host_ids=[self.bk_host_id])
            else:
                host = api.cmdb.get_host_by_ip(ips=[{"ip": self.ip}], bk_biz_id=self.bk_biz_id)
            if host:
                if not host[0].bk_host_id:
                    raise CustomException(_("保存拨测节点失败，主机%(ip)s存在，但无bk_host_id信息".format(**{"ip": self.ip})))
                validate_dict = {"bk_host_id": host[0].bk_host_id}
                # 如果有 ip 数据，则添加到筛选
                if host[0].bk_host_innerip:
                    validate_dict.update(ip=host[0].bk_host_innerip)
            else:
                raise CustomException(
                    _(
                        "保存拨测节点失败，主机%(ip)s不存在：bk_host_id=%(bk_host_id)s".format(
                            **{"ip": self.ip, "bk_host_id": self.bk_host_id}
                        )
                    )
                )
        q_list = [Q(**{k: v}) for k, v in list(validate_dict.items())]
        # 创建操作
        if not update:
            # ip不能重复
            if UptimeCheckNode.objects.filter(
                Q(bk_biz_id=self.bk_biz_id) & reduce(lambda x, y: x | y, q_list)
            ).exists():
                raise CustomException(
                    _("保存拨测节点失败，主机%(ip)s已存在：name=%(name)s")
                    % {"ip": self.bk_host_id if self.bk_host_id else self.ip, "name": self.name}
                )
            # 名称不能重复
            if UptimeCheckNode.objects.filter(name=self.name, bk_biz_id=self.bk_biz_id).exists():
                raise CustomException(_("保存拨测节点失败，节点名称%(name)s已存在") % {"name": self.name})
        # 更新操作
        else:
            # 先获取到已有的数据，再比较具体变更
            try:
                old_uptimecheck_node = UptimeCheckNode.objects.get(pk=self.pk)
            except UptimeCheckNode.DoesNotExist:
                raise CustomException(_("保存拨测节点失败，不存在id为%(id)s的节点") % {"id": self.pk})
            # ip/bk_host_id变更，则新的ip/bk_host_id不能和其他的相同
            if (
                old_uptimecheck_node.bk_host_id != self.bk_host_id or old_uptimecheck_node.ip != self.ip
            ) and UptimeCheckNode.objects.filter(
                Q(bk_biz_id=self.bk_biz_id) & reduce(lambda x, y: x | y, q_list)
            ).exists():
                raise CustomException(
                    _("保存拨测节点失败，主机%(ip)s已存在：name=%(name)s") % {"ip": self.bk_host_id, "name": self.name}
                )
            # 名称变更，则不能和其他的相同
            if (
                old_uptimecheck_node.name != self.name
                and UptimeCheckNode.objects.filter(name=self.name, bk_biz_id=self.bk_biz_id).exists()
            ):
                raise CustomException(_("保存拨测节点失败，节点名称'%(name)s'已存在") % {"name": self.name})

    class Meta:
        verbose_name = _("拨测节点")
        verbose_name_plural = _("拨测节点")

        index_together = [
            ["name", "bk_biz_id"],
        ]

    def get_title(self):
        return _("拨测节点（%s）") % self.name

    def __unicode__(self):
        return self.get_title()


class UptimeCheckTaskSubscription(OperateRecordModel):
    uptimecheck_id = models.IntegerField("拨测任务id", default=0)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    bk_biz_id = models.IntegerField("业务ID", default=0)

    class Meta:
        # 每个任务针对每个业务只能有一个item
        unique_together = (("uptimecheck_id", "bk_biz_id"),)


class UptimeCheckTask(OperateRecordModel):
    class Protocol(object):
        TCP = UptimeCheckProtocol.TCP
        UDP = UptimeCheckProtocol.UDP
        HTTP = UptimeCheckProtocol.HTTP
        ICMP = UptimeCheckProtocol.ICMP

    PROTOCOL_CHOICES = (
        (Protocol.TCP, "TCP"),
        (Protocol.UDP, "UDP"),
        (Protocol.HTTP, "HTTP(S)"),
        (Protocol.ICMP, "ICMP"),
    )

    class Status(object):
        NEW_DRAFT = "new_draft"
        RUNNING = "running"
        STOPED = "stoped"
        STARTING = "starting"
        STOPING = "stoping"
        START_FAILED = "start_failed"
        STOP_FAILED = "stop_failed"

    STATUS_CHOICES = (
        (Status.NEW_DRAFT, _("未保存")),
        (Status.RUNNING, _("运行中")),
        (Status.STOPED, _("未启用")),
        (Status.STARTING, _("启动中")),
        (Status.STOPING, _("停止中")),
        (Status.START_FAILED, _("启动失败")),
        (Status.STOP_FAILED, _("停止失败")),
    )
    permission_exempt = True

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    name = models.CharField("任务名称", max_length=50, db_index=True)
    protocol = models.CharField("协议", choices=PROTOCOL_CHOICES, max_length=10)
    check_interval = models.PositiveIntegerField("拨测周期(分钟)", default=5)
    # 地点变为可选项
    location = JsonField("地区", default="{}")

    nodes = models.ManyToManyField(UptimeCheckNode, verbose_name="拨测节点", related_name="tasks")
    status = models.CharField("当前状态", max_length=20, choices=STATUS_CHOICES, default=Status.NEW_DRAFT)
    config = SymmetricJsonField("拨测配置", null=True, blank=True)

    @property
    def full_table_name(self):
        return "{}_{}_{}".format(self.bk_biz_id, UPTIME_CHECK_DB, self.protocol.lower())

    def delete(self, *args, **kwargs):
        """
        重写拨测任务删除方法
        1、删除前
            首先要清除该拨测任务所关联的监控源、告警策略
        2、删除后
            如果删除一个正在运行中的拨测任务
            需要在任务相关联的节点上重新生成下发最新配置，并执行重载操作
        """
        subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)
        if len(subscriptions) != 0:
            # 删除任务前先删除订阅
            self.delete_subscription()

        pk = self.pk
        super(UptimeCheckTask, self).delete(*args, **kwargs)

        # 在对应的分组中，将此任务剔除
        with transaction.atomic():
            for group in self.groups.all():
                group.tasks.remove(self.id)

        logger.info(_("拨测任务已删除,ID:%d" % pk))

    @property
    def temp_conf_name(self):
        """
        测试流程临时配置文件名
            filename = {bizid}_{pk}_uptimecheckbeat.yml
        """
        return "_".join([str(self.bk_biz_id), str(self.pk), "uptimecheckbeat.yml"])

    def update_subscription(self):
        """
        更新订阅
        更新自身绑定的订阅对象的配置项
        """
        params_list = self.generate_subscription_configs()
        create_params = []
        result_list = []
        # 更新任务信息
        subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)
        delete_map = {}
        for subscription in subscriptions:
            delete_map[subscription.bk_biz_id] = subscription.subscription_id

        # 更新任务信息
        for params in params_list:
            bk_biz_id = params["scope"]["bk_biz_id"]
            # 删除匹配到的biz_id，剩下的就是没有匹配成功的，这些订阅需要删除
            if bk_biz_id in delete_map.keys():
                del delete_map[bk_biz_id]
            subscription_item = subscriptions.filter(bk_biz_id=bk_biz_id)
            # 如果查到了，说明要更新节点管理的id
            if len(subscription_item) != 0:
                params["subscription_id"] = subscription_item[0].subscription_id
                params["run_immediately"] = True
                result = api.node_man.update_subscription(params)
                logger.info(_("订阅任务已更新，订阅ID:%d,任务ID:%d") % (result.get("subscription_id", 0), result.get("task_id", 0)))
                result_list.append(result)
            else:
                # 否则说明要新增订阅
                create_params.append(params)
        # 开始删除
        delete_subscription_ids = []
        for biz_id in delete_map.keys():
            delete_subscription_ids.append(delete_map[biz_id])
        if delete_subscription_ids:
            self.delete_subscription(delete_subscription_ids)

        create_result_list = []
        if create_params:
            create_result_list = self.send_create_subscription(create_params)

        return result_list, create_result_list, delete_subscription_ids

    def delete_subscription(self, subscription_ids=None):
        """
        删除订阅
        先执行switch_off和stop_subscription手动卸载正在运行的拨测任务，最后执行删除操作
        直接执行删除操作会导致拨测配置文件遗留
        """
        self.switch_off_subscription(subscription_ids)
        self.stop_subscription(subscription_ids)
        self.send_delete_subscription(subscription_ids)

    def send_delete_subscription(self, subscription_ids=None):
        """
        执行删除订阅
        """

        if subscription_ids is None:
            subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)
            subscription_ids = [subscription.subscription_id for subscription in subscriptions]
        else:
            subscriptions = UptimeCheckTaskSubscription.objects.filter(
                uptimecheck_id=self.pk, subscription_id__in=subscription_ids
            )
        for subscription_id in subscription_ids:
            api.node_man.delete_subscription(subscription_id=subscription_id)
            logger.info(_("订阅任务已删除，ID:%d") % subscription_id)
        subscriptions.update(is_deleted=True)

    def switch_off_subscription(self, subscription_ids=None):
        """
        关闭订阅
        关闭对自身绑定的订阅的监听，该操作不会立刻执行插件删除操作，若要立刻执行，需要调用stop_subscription
        """
        if subscription_ids is None:
            subscription_ids = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk).values_list(
                "subscription_id", flat=True
            )
        for subscription_id in subscription_ids:
            api.node_man.switch_subscription(subscription_id=subscription_id, action="disable")
            logger.info(_("订阅任务已关闭，ID:%d") % subscription_id)

    def switch_on_subscription(self):
        """
        开启订阅
        启动对自身绑定的订阅的监听,该操作不会立刻执行插件部署操作，若要立刻执行，需要调用start_subscription
        """
        subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)
        for subscription in subscriptions:
            api.node_man.switch_subscription(subscription_id=subscription.subscription_id, action="enable")
            logger.info(_("订阅任务已启动，ID:%d") % subscription.subscription_id)

    def stop_subscription(self, subscription_ids=None):
        """
        停止订阅
        立即执行自身绑定的订阅id的STOP命令
        """
        action_name = "bkmonitorbeat_%s" % self.protocol.lower()
        if subscription_ids is None:
            subscription_ids = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk).values_list(
                "subscription_id", flat=True
            )
        for subscription_id in subscription_ids:
            api.node_man.run_subscription(subscription_id=subscription_id, actions={action_name: "STOP"})
            logger.info(_("订阅任务执行STOP，ID:%d") % subscription_id)

    def start_subscription(self):
        """
        启动订阅
        立即执行自身绑定的订阅id的START命令
        """
        action_name = "bkmonitorbeat_%s" % self.protocol.lower()
        subscriptions = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)
        for subscription in subscriptions:
            api.node_man.run_subscription(subscription_id=subscription.subscription_id, actions={action_name: "START"})
            logger.info(_("订阅任务执行START，ID:%d") % subscription.subscription_id)

    # 外层增加双引号，内层对有双引号的数据增加转义字符
    def add_escape(self, input_string):
        if input_string:
            temp = input_string.replace('"', '\\"')
            return '"%s"' % temp
        return input_string

    def generate_subscription_configs(self):
        """
        生成订阅参数
        读取当前对象的属性，并组装成节点管理的参数
        """
        pk = self.pk
        protocol = self.protocol.lower()
        dataid_map = {
            UptimeCheckProtocol.HTTP: settings.UPTIMECHECK_HTTP_DATAID,
            UptimeCheckProtocol.TCP: settings.UPTIMECHECK_TCP_DATAID,
            UptimeCheckProtocol.UDP: settings.UPTIMECHECK_UDP_DATAID,
            UptimeCheckProtocol.ICMP: settings.UPTIMECHECK_ICMP_DATAID,
        }

        biz_nodes = {}
        # 先遍历收集所有的节点信息，按业务id分组
        for node in self.nodes.values():
            if node["bk_biz_id"] in biz_nodes.keys():
                biz_nodes[node["bk_biz_id"]].append(node)
            else:
                biz_nodes[node["bk_biz_id"]] = [node]

        # 再按业务id生成订阅参数
        available_duration = int(self.config.get("timeout", self.config["period"] * 1000))
        if available_duration > settings.UPTIMECHECK_DEFAULT_MAX_TIMEOUT:
            timeout = available_duration + 5000
        else:
            timeout = settings.UPTIMECHECK_DEFAULT_MAX_TIMEOUT

        params_list = []
        for bk_biz_id in biz_nodes.keys():
            scope = {
                "bk_biz_id": bk_biz_id,
                "object_type": "HOST",
                "node_type": "INSTANCE",
                "nodes": [
                    {"bk_host_id": node["bk_host_id"]}
                    if node.get("bk_host_id")
                    else {"ip": node["ip"], "bk_cloud_id": node["plat_id"], "bk_supplier_id": settings.BK_SUPPLIER_ID}
                    for node in biz_nodes[bk_biz_id]
                ],
            }
            step = {
                "id": "bkmonitorbeat_%s" % protocol,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_%s.conf" % protocol, "version": "latest"}],
                },
                "params": {
                    "context": {
                        "data_id": dataid_map[protocol.upper()],
                        "max_timeout": str(settings.UPTIMECHECK_DEFAULT_MAX_TIMEOUT) + "ms",
                        "tasks": resource.uptime_check.generate_sub_config({"task_id": pk}),
                        "config_hosts": self.config.get("hosts", []),
                        # 针对动态节点的情况, 注意，业务ID必须拿当前task的业务ID：
                        "task_id": pk,
                        "bk_biz_id": self.bk_biz_id,
                        "period": "{}s".format(self.config["period"]),
                        "available_duration": "{}ms".format(available_duration),
                        "timeout": "{}ms".format(timeout),
                        "target_port": self.config.get("port"),
                        "response": self.add_escape(self.config.get("response", "")),
                        "request": self.add_escape(self.config.get("request", "")),
                        "response_format": self.config.get("response_format", "in"),
                        "size": self.config.get("size"),
                        "total_num": self.config.get("total_num"),
                        "max_rtt": "{}ms".format(self.config.get("max_rtt", 3000)),
                    }
                },
            }
            # 这里由于历史原因，与其他协议相比，icmp漏掉了node_id,这里采用label注入的方式补充上
            if protocol.upper() == UptimeCheckProtocol.ICMP:
                step["params"]["context"]["labels"] = {
                    "$for": "cmdb_instance.scope",
                    "$body": {
                        "node_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id "
                        "is iterable and cmdb_instance.host.bk_cloud_id is not string else "
                        "cmdb_instance.host.bk_cloud_id }}:{{ cmdb_instance.host.bk_host_innerip }}",
                    },
                    "$item": "scope",
                }
            params = {
                "scope": scope,
                "steps": [step],
                "run_immediately": True,
            }
            params_list.append(params)

        return params_list

    def create_subscription(self):
        """
        建立订阅
        解析当前对象的属性生成参数列表，并向节点管理发起订阅请求
        """
        params_list = self.generate_subscription_configs()
        result_list = self.send_create_subscription(params_list)
        return result_list

    def send_create_subscription(self, params_list):
        """
        使用传入的参数列表，发送新增请求
        """
        result_list = []
        for params in params_list:
            result = api.node_man.create_subscription(params)
            logger.info(_("订阅任务已创建，ID:%d") % result.get("subscription_id", 0))
            result["bk_biz_id"] = params["scope"]["bk_biz_id"]
            result_list.append(result)
        return result_list

    def deploy(self, enable_strategy=False):
        """
        正式创建任务
        通过向节点管理发起订阅的方式执行任务
        如果当前拨测任务对象没有subscription_id，说明是新增任务流程
        如果已经有subscription_id，说明是更新任务流程
        """
        create_strategy = True if (self.status == self.Status.NEW_DRAFT) else False
        self.status = self.Status.STARTING
        self.save()
        UptimeCheckTaskCollectorLog.objects.filter(task_id=self.id).update(is_deleted=True)
        try:
            if len(UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk)) == 0:
                # 没有订阅id说明为新增任务，此时调用新增订阅接口
                create_result_list = self.create_subscription()
                # 生成新的订阅后，要将其入库存储
                for result in create_result_list:
                    # 遍历生成新的数据
                    UptimeCheckTaskSubscription.objects.create(
                        uptimecheck_id=self.pk, subscription_id=result["subscription_id"], bk_biz_id=result["bk_biz_id"]
                    )
                # 默认打开订阅
                self.switch_on_subscription()
                logger.info(_("新增拨测任务订阅完毕，任务id:%d,新增的订阅信息:%s") % (self.pk, str(create_result_list)))
            else:
                # 存在订阅id说明为旧任务，则需执行以下操作:
                # 1.停止订阅任务
                # 2.更新订阅配置
                # 3.启动订阅任务
                self.switch_off_subscription()
                # 由于订阅任务的特性，
                update_result, create_result_list, delete_list = self.update_subscription()
                # 生成新的订阅后，要将其入库存储
                for result in create_result_list:
                    # 遍历生成新的数据
                    UptimeCheckTaskSubscription.objects.create(
                        uptimecheck_id=self.pk, subscription_id=result["subscription_id"], bk_biz_id=result["bk_biz_id"]
                    )
                self.switch_on_subscription()
                logger.info(
                    _("更新拨测任务订阅完毕，任务id:%d,更新的订阅信息:%s,新增的订阅信息:%s,删除的订阅信息:%s")
                    % (self.pk, str(update_result), str(create_result_list), str(delete_list))
                )
        except Exception as e:
            self.status = self.Status.START_FAILED
            self.save()
            logger.error(_("重启采集器时部分IP失败: %s") % e)
            raise CustomException(_("重启采集器时部分IP失败: %s") % e)
        self.save()
        update_task_running_status.delay(self.pk)
        # if create_strategy:
        #     resource.uptime_check.generate_default_strategy({'task_id': self.pk})

        if enable_strategy or create_strategy:
            resource.uptime_check.switch_strategy_by_task_id(
                {"bk_biz_id": self.bk_biz_id, "task_id": self.pk, "is_enabled": True}
            )

        # 将新拨测任务追加进缓存表中
        result_table_id_list = ["uptimecheck.{}".format(self.protocol.lower())]
        append_metric_list_cache.delay(result_table_id_list)

        return "success"

    def start_task(self):
        """
        启动任务
        """
        # 前置检查是否有运行中的启停任务
        try:
            subscription_ids = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk).values_list(
                "subscription_id", flat=1
            )
            if subscription_ids:
                status_result = api.node_man.subscription_instance_status(subscription_id_list=subscription_ids)[0][
                    "instances"
                ]
                for status in status_result:
                    if status.get("running_task", None):
                        raise CustomException(_("拨测任务启用失败：存在运行中的启停任务，请稍后再试"))
        except BKAPIError as e:
            logger.error(_("拨测任务启停前置检查失败: {}").format(e))
        try:
            if not UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk):
                self.deploy(enable_strategy=True)
            else:
                self.status = self.Status.STARTING
                self.save()
                resource.uptime_check.switch_strategy_by_task_id(
                    {"bk_biz_id": self.bk_biz_id, "task_id": self.pk, "is_enabled": True}
                )
                self.switch_on_subscription()
                self.start_subscription()
        except Exception as e:
            self.status = self.Status.START_FAILED
            self.save()
            raise CustomException(_("拨测任务启用失败：{}") % e.message)

        self.status = self.Status.RUNNING
        self.save()

        return "success"

    def stop_task(self):
        """
        停止任务
        """
        # 前置检查是否有运行中的启停任务
        try:
            subscription_ids = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=self.pk).values_list(
                "subscription_id", flat=1
            )
            status_result = api.node_man.subscription_instance_status(subscription_id_list=subscription_ids)[0][
                "instances"
            ]
            for status in status_result:
                if status.get("running_task", None):
                    raise CustomException(_("拨测任务停用失败：存在运行中的启停任务，请稍后再试"))
        except BKAPIError as e:
            logger.error(_("拨测任务启停前置检查失败: {}").format(e))
        self.status = self.Status.STOPING
        self.save()
        try:
            resource.uptime_check.switch_strategy_by_task_id(
                {"bk_biz_id": self.bk_biz_id, "task_id": self.pk, "is_enabled": False}
            )
            self.switch_off_subscription()
            self.stop_subscription()
        except Exception as e:
            self.status = self.Status.STOP_FAILED
            self.save()
            raise CustomException(_("拨测任务停用失败：%s") % str(e))

        self.status = self.Status.STOPED
        self.save()

        return "success"

    def change_status(self, status):
        """
        更改任务运行状态
        :return:
        """
        if not status:
            raise CustomException(_("更改拨测任务状态：目标状态为空"))
        if status == self.status:
            return "success"
        elif status == self.Status.STOPED:
            return self.stop_task()
        elif status == self.Status.RUNNING:
            return self.start_task()
        else:
            raise CustomException(_("更改拨测任务状态：无效的目标状态：%s") % status)

    class Meta:
        verbose_name = _("拨测任务")
        verbose_name_plural = _("拨测任务")

    def get_timeout(self):
        """
        获取期待响应时间
        """
        return self.config.get("timeout", 3000)

    def get_period(self):
        """
        获取采集周期
        """
        return self.config.get("period", 60)

    def get_title(self):
        return _("拨测任务（%s）") % self.name

    def __unicode__(self):
        return self.get_title()


class UptimeCheckTaskCollectorLog(models.Model):
    """
    下发拨测任务时，获取节点管理中相关节点执行日志
    """

    task_id = models.IntegerField("拨测任务ID")
    error_log = JsonField("错误日志", default="{}")
    is_deleted = models.BooleanField("已删除", default=False)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    nodeman_task_id = models.IntegerField("节点管理任务ID", default=0)


class UptimeCheckGroup(OperateRecordModel):
    """
    拨测任务分组
    """

    name = models.CharField("分组名称", max_length=50)
    tasks = models.ManyToManyField(UptimeCheckTask, verbose_name="拨测任务", related_name="groups")
    logo = models.TextField("图片base64形式", default="", blank=True)
    bk_biz_id = models.IntegerField("业务ID", default=0)
    permission_exempt = True

    # 运行中任务
    # 如果停用分组中关联的某任务，那么被停用的任务既不在分组曲线中显示，也不会参与分组的可用率计算
    @property
    def running_tasks(self):
        return self.tasks.filter(status=UptimeCheckTask.Status.RUNNING)

    class Meta:
        verbose_name = _("拨测分组")
        verbose_name_plural = _("拨测分组")


def generate_upload_path(instance, filename):
    return os.path.join(instance.relative_path, instance.actual_filename)


class UploadedFile(OperateRecordModel):
    original_filename = models.CharField("原始文件名", max_length=255)
    actual_filename = models.CharField("文件名", max_length=255)
    relative_path = models.TextField("文件相对路径")
    file_data = models.FileField("文件内容", upload_to=generate_upload_path)

    @property
    def file_md5(self):
        return hashlib.md5(self.file_data.file.read()).hexdigest()

    @property
    def file_type(self):
        file_command = ["file", "-b", self.file_data.path]
        try:
            stdout, stderr = subprocess.Popen(file_command, stdout=subprocess.PIPE).communicate()
        except Exception as e:
            logger.exception(_("不存在的文件，获取文件类型失败：%s") % e)
            return ""
        return stdout
