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
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _

from bkmonitor.utils.db import JsonField

from .models import OperateRecordModel


class OperateRecord(models.Model):
    biz_id = models.IntegerField("业务cc_id", default=0)
    config_type = models.CharField("配置类型", max_length=32)
    config_id = models.IntegerField("操作config_id")
    config_title = models.CharField("配置标题", default="", max_length=512)
    operator = models.CharField("操作人", max_length=32)
    operator_name = models.CharField("操作人昵称", default="", max_length=32)
    operate = models.CharField("具体操作", max_length=32)
    operate_time = models.DateTimeField("操作时间", auto_now_add=True)
    data = models.TextField("数据(JSON)")
    data_ori = models.TextField("修改前数据(JSON)", default="{}")
    operate_desc = models.TextField("操作说明", default="")

    class Meta:
        verbose_name = _("操作记录")
        verbose_name_plural = _("操作记录")


class DataGenerateConfig(OperateRecordModel):
    """
    记录数据处理过程
    biz_id: 业务
    collector_id: 采集表id
    template_id: 模板id
    template_args: 模版参数
    project_id: 子项目ID
    job_id: 对应的作业ID
    """

    STATUS_CHOICES = (
        ("starting", _("启动中")),
        ("running", _("正在运行")),
        ("stopping", _("停止中")),
        ("not running", _("未启动")),
    )

    biz_id = models.IntegerField("业务ID")
    collector_id = models.IntegerField("关联数据接入配置")
    template_id = models.IntegerField("模版ID")
    template_args = models.TextField("模版参数")
    project_id = models.IntegerField("子项目ID")
    job_id = models.CharField("对应的作业ID", max_length=32)
    bksql = models.TextField("bksql描述", default="")
    status = models.CharField("作业状态", max_length=16, default="starting", choices=STATUS_CHOICES)


class DataCollector(OperateRecordModel):
    """
    记录通过监控系统接入的数据来源及配置信息
    biz_id: 业务
    source_type: 数据库 / log / msdk / tqos
    collector_config: 采集数据需要用到的配置信息
    data_set: 数据基简称
    data_id: 数据id
    data_description: 数据描述
    data_type: 数据类型 在线==
    """

    biz_id = models.IntegerField("业务ID")
    source_type = models.CharField("数据源类型", max_length=32)
    collector_config = models.TextField("数据接入配置信息")
    data_id = models.IntegerField("下发data id")
    data_type = models.CharField("数据类型", max_length=32)
    data_set = models.CharField("db_name+table_name", max_length=225)
    data_description = models.TextField("数据描述", null=True)

    def __str__(self):
        return "{}: {}".format(self.id, self.biz_id)


class MonitorHostSticky(models.Model):
    """
    主机基础性能列表置顶信息
    """

    plat_id = models.IntegerField("平台ID", null=True)
    host = models.CharField("主机IP", max_length=128, null=True, db_index=True)
    cc_biz_id = models.CharField("cc业务id", max_length=30)


class ScenarioMenu(OperateRecordModel):
    """
    左侧场景菜单
    """

    SYSTEM_MENU_CHOICES = (
        ("", _("用户自定义")),
        ("favorite", _("关注")),
        ("default", _("默认分组")),
    )
    system_menu = models.CharField("系统菜单栏", choices=SYSTEM_MENU_CHOICES, max_length=32, default="", blank=True)
    biz_id = models.CharField("业务ID", max_length=100)

    menu_name = models.CharField("菜单名", max_length=255)
    menu_index = models.IntegerField("菜单顺序", default=999)

    class Meta:
        verbose_name = _("左侧菜单")
        verbose_name_plural = _("左侧菜单")

    @property
    def name(self):
        return self.menu_name


class MonitorLocation(OperateRecordModel):
    """
    监控映射
    """

    biz_id = models.CharField("业务ID", max_length=100)

    menu_id = models.IntegerField("菜单id")
    monitor_id = models.IntegerField("监控id")
    graph_index = models.IntegerField("图表所在栏目位置", default=9999999)
    width = models.IntegerField("宽度", default=6)

    class Meta:
        verbose_name = _("监控映射")
        verbose_name_plural = _("监控映射")


class DashboardMenu(OperateRecordModel):
    # 仪表盘菜单
    biz_id = models.IntegerField("业务ID")
    name = models.CharField("仪表盘名称", max_length=32, default="")


class DashboardView(OperateRecordModel):
    # 仪表盘视图
    GRAPH_TYPE_CHOICES = (
        ("time", _("时间序列")),
        ("top", _("TOP排行")),
        ("status", _("状态值")),
    )
    biz_id = models.IntegerField("业务ID")
    name = models.CharField("视图名称", max_length=128, default="")
    graph_type = models.CharField("图表类型", max_length=32, choices=GRAPH_TYPE_CHOICES)
    metrics = models.TextField("指标项")
    symbols = models.TextField("标记")


class DashboardMenuLocation(OperateRecordModel):
    # 仪表盘上图表link
    view_index = models.IntegerField("视图展示顺序", default=999)
    view_size = models.IntegerField("视图大小", default=12)
    view = models.ForeignKey(DashboardView, verbose_name="仪表盘视图", related_name="locations", on_delete=models.CASCADE)
    menu = models.ForeignKey(DashboardMenu, verbose_name="仪表盘菜单", on_delete=models.CASCADE)


class ServiceAuthorization(models.Model):
    SERVICE_TYPE_CHOICES = [
        ("charts", _("图表")),
    ]

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)
    expire_time = models.DateTimeField("过期时间", null=True, default=None)

    name = models.CharField("名称", max_length=128, null=True, blank=True)
    enable = models.BooleanField("启用", default=True)
    cc_biz_id = models.CharField("cc业务id", max_length=30)
    service_type = models.CharField("服务类型", max_length=30, choices=SERVICE_TYPE_CHOICES)
    service_id = models.CharField("服务id", max_length=30)
    domain = models.TextField("命名空间", null=True, blank=True)
    access_token = models.CharField("授权码", max_length=128, null=False, default=None)

    extra = models.TextField("扩展选项", null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.domain:
            self.domain = ""

        if not self.extra:
            self.extra = "{}"
        return super(ServiceAuthorization, self).save(*args, **kwargs)


class HostProperty(models.Model):
    property = models.CharField("属性", max_length=32)
    property_display = models.CharField("属性展示名称", max_length=32)
    required = models.BooleanField("必选", default=False)
    selected = models.BooleanField("勾选", default=False)
    is_deleted = models.BooleanField("已删除", default=False)
    index = models.FloatField("排列顺序", default=0)

    def field_index(self):
        return self.index or self.id

    def refresh_index(self):
        return {"name": self.property_display, "required": self.required, "index": self.field_index()}


class HostPropertyConf(OperateRecordModel):
    biz_id = models.IntegerField("业务ID")
    property_list = models.TextField("属性列表")


class MetricConf(models.Model):
    # tsdb指标配置
    category = models.CharField("指标大类", max_length=32)
    metric = models.CharField("指标id", max_length=128)
    metric_type = models.CharField("指标分类", max_length=128)
    description = models.CharField("指标说明", max_length=128)
    display = models.TextField("指标详细展示")
    index = models.FloatField("指标顺序index", default=0)

    # 单位转换
    conversion = models.FloatField("换算除数", default=1.0)
    conversion_unit = models.CharField("转换单位", max_length=32, default="", blank=True)

    @property
    def metric_index(self):
        return self.id if self.index == 0 else self.index


class MetricMonitor(OperateRecordModel):
    # 指标监控项
    view_id = models.IntegerField("仪表盘视图id")
    metric_id = models.CharField("指标id", max_length=36)
    monitor_id = models.IntegerField("监控项id")


class Application(models.Model):
    cc_biz_id = models.IntegerField(unique=True)

    name = models.CharField(
        max_length=128,
    )

    groups = models.ManyToManyField(
        Group,
        through="ApplicationGroupMembership",
    )

    def __unicode__(self):
        return "#{} {}".format(self.cc_biz_id, self.name)


class ApplicationGroupMembership(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("application", "group")


class CollectorConfig(OperateRecordModel):
    """
    采集配置抽象类
    """

    class Meta:
        abstract = True


class ScriptCollectorConfig(CollectorConfig):
    """
    新脚本采集
    """

    class ScriptType(object):
        FILE = "file"
        CMD = "cmd"

    class Status(object):
        DRAFT = "draft"
        SAVED = "saved"

    CHARSET_CHOICES = (
        ("UTF8", "UTF8"),
        ("GBK", "GBK"),
    )

    SCRIPT_TYPE_CHOICES = (
        (ScriptType.FILE, _("脚本")),
        (ScriptType.CMD, _("命令行")),
    )

    SCRIPT_EXT_CHOICES = (
        ("shell", "shell"),
        ("bat", "bat"),
        ("python", "python"),
        ("perl", "perl"),
        ("powershell", "powershell"),
        ("vbs", "vbs"),
        ("custom", _("自定义")),
    )

    STATUS_CHOICES = (
        (Status.DRAFT, _("新建未保存")),
        (Status.SAVED, _("已保存")),
    )

    bk_biz_id = models.IntegerField("业务ID")
    data_id = models.IntegerField("创建的data id", null=True, blank=True)

    name = models.CharField("数据表名", max_length=30)
    description = models.CharField("数据表中文含义", max_length=15)
    charset = models.CharField("字符集", max_length=20, choices=CHARSET_CHOICES)
    fields = JsonField("字段信息(json)")

    script_type = models.CharField("脚本类型", max_length=20, choices=SCRIPT_TYPE_CHOICES, default="file")
    script_ext = models.CharField("脚本格式", max_length=20, choices=SCRIPT_EXT_CHOICES, default="shell")
    params_schema = JsonField("脚本参数模型", null=True)
    script_run_cmd = models.TextField("启动命令（脚本模式）", null=True, blank=True)
    script_content_base64 = models.TextField("脚本内容", null=True, blank=True)
    start_cmd = models.TextField("启动命令（命令行模式）", null=True, blank=True)

    collect_interval = models.PositiveIntegerField("采集周期(分钟)", default=1)
    raw_data_interval = models.PositiveIntegerField("原始数据保存周期(天)", default=30)

    status = models.CharField("当前状态", max_length=20, choices=STATUS_CHOICES, default=Status.DRAFT)

    class Meta:
        verbose_name = _("脚本采集配置")


class CollectorInstance(OperateRecordModel):
    """
    实例配置抽象类
    """

    INSTANCE_TYPE_CHOICES = (
        ("host", _("主机")),
        ("topo", _("拓扑")),
    )

    type = models.CharField("实例类型", max_length=20, default="host", choices=INSTANCE_TYPE_CHOICES)
    bk_biz_id = models.IntegerField("业务ID")
    ip = models.CharField("主机IP", max_length=30, null=True, blank=True)
    bk_cloud_id = models.IntegerField("云区域ID", null=True, blank=True)
    bk_obj_id = models.CharField("拓扑对象ID", max_length=50, null=True, blank=True)
    bk_inst_id = models.IntegerField("拓扑对象实例ID", null=True, blank=True)

    class Meta:
        abstract = True


class ScriptCollectorInstance(CollectorInstance):
    """
    采集实例
    """

    config = models.ForeignKey(
        ScriptCollectorConfig, verbose_name="配置", related_name="instances", on_delete=models.CASCADE
    )
    params = JsonField("脚本执行参数")

    class Meta:
        verbose_name = _("脚本采集实例")


class ShellCollectorParamsMixin(models.Model):
    """脚本采集参数模版"""

    CHARSET_CHOICES = (
        ("UTF8", "UTF8"),
        ("GBK", "GBK"),
    )

    # 通用参数
    biz_id = models.IntegerField("业务ID")

    data_id = models.IntegerField("创建的data id", null=True, blank=True)
    rt_id = models.CharField("结果表名", null=True, blank=True, max_length=100)

    # 第一步 - 定义表结构
    table_name = models.CharField("数据表名", max_length=30)
    table_desc = models.CharField("数据表中文含义", max_length=15)
    charset = models.CharField("字符集", max_length=20, choices=CHARSET_CHOICES)
    fields = JsonField("字段信息(json)")

    # 第二步 - 编写采集脚本
    shell_content = models.TextField("脚本内容", null=True)

    # 第三步 - 选择服务器
    ip_list = JsonField("IP列表(json)", null=True, blank=True)
    scope = JsonField("大区信息(json)", null=True, blank=True)

    # 第五步 - 设置采集周期
    collect_interval = models.PositiveIntegerField("采集周期(分钟)", default=1)
    raw_data_interval = models.PositiveIntegerField("原始数据保存周期(天)", default=30)
    trend_data_interval = models.PositiveIntegerField("趋势数据保存周期(天)", default=90)

    class Meta:
        abstract = True


class ShellCollectorConfig(ShellCollectorParamsMixin, OperateRecordModel):
    """脚本采集配置"""

    class Status(object):
        NEW_DRAFT = "new draft"
        EDIT_DRAFT = "edit draft"
        SAVED = "saved"
        DELETE_FAILED = "delete failed"

    STATUS_CHOICES = (
        (Status.NEW_DRAFT, _("新建未保存")),
        (Status.EDIT_DRAFT, _("编辑未保存")),
        (Status.SAVED, _("已保存")),
        (Status.DELETE_FAILED, _("删除失败")),
    )

    STEP_CHOICES = (
        (1, _("定义表结构")),
        (2, _("编写采集脚本")),
        (3, _("选择服务器")),
        (4, _("下发采集测试")),
        (5, _("设置采集周期")),
        (6, _("完成")),
    )

    status = models.CharField("当前状态", max_length=20, choices=STATUS_CHOICES, default=Status.NEW_DRAFT)
    step = models.IntegerField("当前步骤(1-6)", choices=STEP_CHOICES, default=2)

    class Meta:
        verbose_name = _("脚本采集配置")
        verbose_name_plural = _("脚本采集配置")
        ordering = ("-create_time",)


class ShellCollectorDepositTask(ShellCollectorParamsMixin, OperateRecordModel):
    """脚本采集托管任务"""

    class Status(object):
        CREATED = "created"
        RUNNING = "running"
        SUCCESS = "success"
        FAILED = "failed"
        EXCEPTION = "exception"

    STATUS_CHOICES = (
        (Status.CREATED, _("任务创建成功")),
        (Status.RUNNING, _("任务正在执行")),
        (Status.SUCCESS, _("任务执行成功")),
        (Status.FAILED, _("任务执行失败")),
        (Status.EXCEPTION, _("任务执行过程异常")),
    )

    class Process(object):
        READY = "ready"
        CREATE_DATASET = "create dataset"
        CREATE_RT = "create rt"
        SET_ETL_TEMPLATE = "set etl template"
        DEPLOY_TSDB = "deploy_tsdb"
        START_DISPATCH = "start dispatch"
        START_DEPOSIT_TASK = "start deposit task"
        # WAIT_DEPOSIT_TASK = "wait deposit task"
        STOP_OLD_DEPOSIT_TASK = "stop old deposit task"
        FINISHED = "finished"

    PROCESS_CHOICES = (
        (Process.READY, _("任务就绪")),
        (Process.CREATE_RT, _("检查并创建结果表")),
        (Process.CREATE_DATASET, _("检查并创建DataSet")),
        (Process.SET_ETL_TEMPLATE, _("检查并生成清洗配置")),
        (Process.DEPLOY_TSDB, _("检查并创建TSDB")),
        (Process.START_DISPATCH, _("启动入库程序")),
        (Process.START_DEPOSIT_TASK, _("创建脚本托管任务")),
        # (Process.WAIT_DEPOSIT_TASK, _(u"等待脚本托管任务执行结果")),
        (Process.STOP_OLD_DEPOSIT_TASK, _("取消老版本配置的IP托管")),
        (Process.FINISHED, _("任务流程完成")),
    )

    config = models.ForeignKey(
        ShellCollectorConfig, verbose_name="所属配置", related_name="tasks", on_delete=models.CASCADE
    )

    status = models.CharField("任务状态", choices=STATUS_CHOICES, max_length=50, default=Status.CREATED)

    process = models.CharField("任务当前流程", choices=PROCESS_CHOICES, max_length=50, default=Process.READY)

    result_data = JsonField("任务执行结果(JSON)")
    ex_data = models.TextField("任务异常信息")

    class Meta:
        verbose_name = _("脚本采集托管任务")
        get_latest_by = "update_time"


class ExporterCollectorParamsMixin(models.Model):
    """
    脚本采集参数模版

    一些字段格式
    indices = [
        {
            "table_name": "xxx",
            "table_desc": "yyy",
            "fields": [
                {
                    "name": "test123",
                    "description": "xxx",
                    "unit": "%",
                    "monitor_type": "dimension", # "dimension" or "metric",
                    "type": "double", # "long", "double" or "string"
                }
            ]
        }
    ]

    config_schema = [
        {
            "name": "xxx",
            "description": "desc",
            "type": "text", # "text" or "file",
            "mode": "env", # "env" or "cmd"
            "default": "default_value"
        }
    ]

    config = {
        "execute": {
            "env": {
                "xxx": "yyy"
            },
            "cmd": {
                "aaa": "bbb"
            }
        },
        "collect": {
            "host": "127.0.0.1",
            "port": "8080"
        }
    }

    exporter_file = {
        "origin_file_name": "xxx",  # 用户上传的原文件名
        "file_id": 1234,            # 文件ID
        "file_type": "xxxxx",       # 文件信息
        "file_name": "xxxxxx",      # 真实存储的文件名
        "md5": "xxxxxx",            # 文件的md5
    }

    config_file = [
        {
            "origin_file_name": "xxx",  # 用户上传的原文件名
            "file_id": 1234,            # 文件ID
            "file_type": "xxxxx",       # 文件信息
            "file_name": "xxxxxx",      # 真实存储的文件名
            "md5": "xxxxxx",            # 文件的md5
        }
    ]
    """

    TSDB_NAME = "exporter"

    CHARSET_CHOICES = (
        ("UTF8", "UTF8"),
        ("GBK", "GBK"),
    )

    OS_FIELD_MAPPING = {
        "linux": "exporter_file_info",
        "windows": "windows_exporter_file_info",
        "aix": "aix_exporter_file_info",
    }

    # 通用参数
    biz_id = models.IntegerField("业务ID")

    data_id = models.IntegerField("创建的data id", null=True, blank=True)
    rt_id_list = JsonField("虚拟结果表名(列表)", default=[])
    parent_rt_id = models.CharField("实体结果表名", null=True, blank=True, max_length=100)

    # 第一步 - 导入组件
    component_name = models.CharField("组件名称", max_length=15)
    component_name_display = models.CharField("组件中文含义", max_length=128)
    component_desc = models.TextField("组件详细描述(md)", default="", blank=True)

    indices = JsonField("指标项(json)", default=[])
    exporter_id = models.IntegerField("Exporter ID", default=0)
    exporter_file_info = JsonField("上传的Exporter文件信息(Linux)", null=True, blank=True)
    windows_exporter_file_info = JsonField("上传的Exporter文件信息(Windows)", null=True, blank=True)
    aix_exporter_file_info = JsonField("上传的Exporter文件信息(AIX)", null=True, blank=True)

    logo = models.TextField("logo的base64编码", default="", blank=True)
    logo_small = models.TextField("小logo的base64编码", default="", blank=True)

    charset = models.CharField("字符集", max_length=20, choices=CHARSET_CHOICES, default="UTF8")

    config_schema = JsonField("配置模型(json)", default=[])

    # 第二步 - 选择服务器
    ip_list = JsonField("IP列表(json)", default=[])
    scope = JsonField("大区信息(json)", null=True, blank=True)

    # 第三步 - 填写字段
    cleaned_config_data = JsonField("参数填写配置", null=True, blank=True)
    config = JsonField("参数配置", default={})
    config_files_info = JsonField("上传的配置文件详情列表", null=True, blank=True)

    # 第五步 - 设置采集周期
    collect_interval = models.PositiveIntegerField("采集周期(分钟)", default=1)
    raw_data_interval = models.PositiveIntegerField("原始数据保存周期(天)", default=30)
    trend_data_interval = models.PositiveIntegerField("趋势数据保存周期(天)", default=90)

    class Meta:
        abstract = True


class ExporterComponent(ExporterCollectorParamsMixin, CollectorConfig):
    """
    Exporter自定义组件配置
    """

    class Status(object):
        DRAFT = "DRAFT"
        SAVED = "SAVED"

    STATUS_CHOICES = (
        (Status.DRAFT, _("未保存")),
        (Status.SAVED, _("已保存")),
    )

    is_internal = models.BooleanField("是否为内置组件", default=False)
    version = models.CharField("组件版本号（仅限内置组件）", blank=True, default="", max_length=30)

    status = models.CharField("当前状态", max_length=20, choices=STATUS_CHOICES, default=Status.DRAFT)

    class Meta:
        verbose_name = _("自定义组件")
        verbose_name_plural = _("自定义组件")


class ExporterDepositTask(ExporterCollectorParamsMixin, OperateRecordModel):
    """
    自定义组件Exporter托管任务
    """

    class Status(object):
        CREATED = "CREATED"
        RUNNING = "RUNNING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        EXCEPTION = "EXCEPTION"

    STATUS_CHOICES = (
        (Status.CREATED, _("任务创建成功")),
        (Status.RUNNING, _("任务正在执行")),
        (Status.SUCCESS, _("任务执行成功")),
        (Status.FAILED, _("任务执行失败")),
        (Status.EXCEPTION, _("任务执行过程异常")),
    )

    class Process(object):
        READY = "READY"
        CREATE_DATASET = "CREATE_DATASET"
        CREATE_RT = "CREATE_RT"
        SET_ETL_TEMPLATE = "SET_ETL_TEMPLATE"
        DEPLOY_TSDB = "DEPLOY_TSDB"
        START_DISPATCH = "START_DISPATCH"
        START_DEPOSIT_TASK = "START_DEPOSIT_TASK"
        WAIT_DEPOSIT_TASK = "WAIT_DEPOSIT_TASK"
        STOP_OLD_DEPOSIT_TASK = "STOP_OLD_DEPOSIT_TASK"
        FINISHED = "FINISHED"

    PROCESS_CHOICES = (
        (Process.READY, _("任务就绪")),
        (Process.CREATE_RT, _("检查并创建结果表")),
        (Process.CREATE_DATASET, _("检查并创建DataSet")),
        (Process.SET_ETL_TEMPLATE, _("检查并生成清洗配置")),
        (Process.DEPLOY_TSDB, _("检查并创建TSDB")),
        (Process.START_DISPATCH, _("启动入库程序")),
        (Process.START_DEPOSIT_TASK, _("正在托管exporter")),
        (Process.STOP_OLD_DEPOSIT_TASK, _("取消老版本配置的IP托管")),
        (Process.FINISHED, _("任务流程完成")),
    )

    component = models.ForeignKey(
        ExporterComponent, verbose_name="所属组件", related_name="tasks", on_delete=models.CASCADE
    )

    status = models.CharField("任务状态", choices=STATUS_CHOICES, max_length=50, default=Status.CREATED)

    process = models.CharField("任务当前流程", choices=PROCESS_CHOICES, max_length=50, default=Process.READY)

    result_data = JsonField("任务执行结果(JSON)")
    ex_data = models.TextField("任务异常信息")

    class Meta:
        verbose_name = _("Exporter托管任务")
        get_latest_by = "update_time"


class ComponentCategory(models.Model):
    display_name = models.CharField("分类显示名称", max_length=50, unique=True)

    class Meta:
        verbose_name = _("组件分类")
        verbose_name_plural = _("组件分类")
        ordering = ["id"]


class ComponentCategoryRelationship(models.Model):
    category = models.ForeignKey(
        ComponentCategory, null=True, verbose_name="所属分类", related_name="components", on_delete=models.CASCADE
    )
    is_internal = models.BooleanField("是否为内置组件", default=False)
    component_name = models.CharField("组件名称（内置组件专用）", null=True, blank=True, max_length=32)
    exporter_component = models.OneToOneField(
        ExporterComponent,
        null=True,
        related_name="relative_category",
        verbose_name="自定义组件（非内置组件专用）",
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = _("组件分类关系")
        verbose_name_plural = _("组件分类关系")


class ComponentImportTask(OperateRecordModel):
    class Status(object):
        CREATED = "CREATED"
        RUNNING = "RUNNING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        EXCEPTION = "EXCEPTION"

    STATUS_CHOICES = (
        (Status.CREATED, _("任务创建成功")),
        (Status.RUNNING, _("任务正在执行")),
        (Status.SUCCESS, _("任务执行成功")),
        (Status.EXCEPTION, _("任务执行过程异常")),
    )

    class Process(object):
        READY = "READY"
        UNZIP_FILE = "UNZIP_FILE"
        CHECK_COMPONENT_NAME = "CHECK_COMPONENT_NAME"
        CHECK_INDEX_FILE = "CHECK_INDEX_FILE"
        CHECK_CONFIG_FILE = "CHECK_CONFIG_FILE"
        CHECK_COMPONENT_DESC = "CHECK_COMPONENT_DESC"
        PROCESS_LOGO = "PROCESS_LOGO"
        CHECK_EXPORTER_FILE = "CHECK_EXPORTER_FILE"
        SAVE_COMPONENT = "SAVE_COMPONENT"
        FINISHED = "FINISHED"

    PROCESS_CHOICES = (
        (Process.READY, _("任务就绪")),
        (Process.UNZIP_FILE, _("解压文件")),
        (Process.CHECK_COMPONENT_NAME, _("校验组件名称")),
        (Process.CHECK_COMPONENT_DESC, _("校验组件描述")),
        (Process.CHECK_INDEX_FILE, _("校验指标项文件")),
        (Process.CHECK_CONFIG_FILE, _("校验配置项文件")),
        (Process.PROCESS_LOGO, _("读取并压缩LOGO")),
        (Process.CHECK_EXPORTER_FILE, _("校验二进制exporter")),
        (Process.SAVE_COMPONENT, _("保存组件配置")),
        (Process.FINISHED, _("任务流程完成")),
    )

    biz_id = models.IntegerField("业务ID")

    process_data = JsonField("任务流程中间数据(json)", null=True, blank=True)
    result_data = JsonField("任务执行结果(JSON)", null=True, blank=True)
    ex_data = models.TextField("任务异常信息", null=True, blank=True)

    status = models.CharField("任务状态", choices=STATUS_CHOICES, max_length=50, default=Status.CREATED)
    process = models.CharField("任务当前流程", choices=PROCESS_CHOICES, max_length=50, default=Process.READY)

    class Meta:
        verbose_name = _("组件导入任务")
        verbose_name_plural = _("组件导入任务")


class LogCollector(CollectorConfig):
    """
    日志接入配置
    """

    TSDB_NAME = "slog"
    permission_exempt = True

    class Status(object):
        STARTING = "create"
        NORMAL = "normal"
        STOPPING = "stop"
        STOPPED = "stopped"

    STATUS_CHOICES = (
        (Status.STARTING, _("启用中")),
        (Status.STOPPING, _("停用中")),
        (Status.NORMAL, _("正常")),
        (Status.STOPPED, _("停用")),
    )

    biz_id = models.IntegerField("业务id")
    data_id = models.CharField("数据源ID", max_length=100, default="")
    result_table_id = models.CharField("结果表ID", max_length=100, default="")
    data_set = models.CharField("数据源表名", max_length=100)
    data_desc = models.CharField("数据源中文名", max_length=100)
    data_encode = models.CharField("字符编码", max_length=30)
    sep = models.CharField("数据分隔符", max_length=30)
    log_path = models.TextField("日志路径")
    fields = JsonField("字段配置")
    ips = JsonField("采集对象ip列表")
    conditions = JsonField("采集条件")
    file_frequency = models.CharField("日志生成频率", max_length=30)

    class Meta:
        verbose_name = _("日志接入配置")
        verbose_name_plural = _("日志接入配置")


class LogCollectorHost(OperateRecordModel):
    permission_exempt = True

    class Status(object):
        STARTING = "create"
        NORMAL = "normal"
        STOPPING = "stop"
        STOPPED = "stopped"
        EXCEPTION = "exception"

    STATUS_CHOICES = (
        (Status.STARTING, _("启用中")),
        (Status.NORMAL, _("正常")),
        (Status.STOPPING, _("停用中")),
        (Status.STOPPED, _("停用")),
        (Status.EXCEPTION, _("异常")),
    )
    log_collector = models.ForeignKey(
        LogCollector, verbose_name="所属采集器", related_name="hosts", on_delete=models.CASCADE
    )
    ip = models.CharField("采集对象IP", max_length=20)
    plat_id = models.IntegerField("平台ID", default=0)
    status = models.CharField("数据上报状态", max_length=20, default=Status.STARTING, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ["log_collector", "ip", "plat_id"]
        verbose_name = _("日志接入主机状态")
        verbose_name_plural = _("日志接入主机状态")


class IndexColorConf(models.Model):
    """性能指标颜色配置"""

    range = models.CharField("取值区间", max_length=20)
    color = models.CharField("颜色", max_length=10)
    slug = models.CharField("方案标签", max_length=32)
