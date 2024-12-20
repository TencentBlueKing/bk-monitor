# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import gettext as _


class AlarmApplication(models.Model):
    """
    第三方告警接入表
    """

    METHOD_CHOICE = (
        ("get", "GET"),
        ("post", "POST"),
    )

    # 应用ID，密钥
    source_type = models.CharField("告警源标识", max_length=64)
    cc_biz_id = models.IntegerField("业务编码", db_index=True)
    app_name = models.CharField("应用名称", max_length=255)
    # 开关项
    is_enabled = models.BooleanField("是否启用", default=True)
    # 自定义监控配置项
    app_url = models.TextField("拉取告警地址", blank=True, null=True, default="")
    app_method = models.CharField("请求类型", max_length=10, blank=True, null=True, choices=METHOD_CHOICE, default="get")

    class Meta:
        managed = False
        db_table = "fta_solutions_app_alarmapplication"


class AlarmType(models.Model):
    """
    告警类型表
    """

    cc_biz_id = models.IntegerField("业务编码", db_index=True)
    is_enabled = models.BooleanField("是否启用", default=True)
    source_type = models.CharField("告警来源", max_length=128, db_index=True)
    alarm_type = models.CharField("告警类型", max_length=128, db_index=True)
    pattern = models.CharField("匹配模式", max_length=128)
    description = models.TextField("描述", blank=True)
    match_mode = models.IntegerField(
        "匹配类型",
        default=0,
        choices=(
            (0, _("字符串")),
            (1, _("正则表达式")),
            (2, _("通配符")),
        ),
    )
    scenario = models.CharField("告警类型分类", max_length=128, default="", blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    class Meta:
        db_table = "fta_solutions_app_alarmtype"
        managed = False


class Solution(models.Model):
    """自愈套餐"""

    cc_biz_id = models.IntegerField("业务编码", db_index=True)
    solution_type = models.CharField("套餐类型", max_length=128, default="customized")
    codename = models.CharField("英文名称代号", max_length=128, blank=True, null=True)
    title = models.CharField("全名", max_length=512)
    config = models.TextField("配置(JSON)", null=True, blank=True)

    # 待弃用
    creator = models.CharField("创建者", max_length=255)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32)
    is_deleted = models.BooleanField("是否删除", default=False)

    class Meta:
        db_table = "fta_solutions_app_solution"
        managed = False


class AlarmDef(models.Model):
    """告警定义"""

    is_enabled = models.BooleanField("是否启用", default=False)
    is_deleted = models.BooleanField("是否删除", default=False)
    category = models.CharField("告警类型", max_length=32, default="default")
    cc_biz_id = models.IntegerField("业务编码", db_index=True)
    alarm_type = models.CharField("告警类型", max_length=128)
    tnm_attr_id = models.TextField("TNM特性ID", default="", blank=True, null=True)
    reg = models.CharField("正则过滤", max_length=255, default="", blank=True, null=True)
    process = models.CharField("进程名称", max_length=255, default="", blank=True, null=True)
    module = models.TextField(
        "Module",
        default="",
        blank=True,
    )
    topo_set = models.TextField(
        "Set",
        default="",
        blank=True,
    )
    set_attr = models.TextField(
        "Set属性",
        default="",
        blank=True,
    )
    idc = models.TextField(
        "IDC",
        default="",
        blank=True,
    )
    device_class = models.TextField("DeviceClass", default="", blank=True)
    responsible = models.CharField("额外通知人", max_length=255, blank=True, null=True)
    title = models.CharField("全名", max_length=128, blank=True, null=True)
    description = models.TextField("备注", blank=True, null=True)
    ok_notify = models.BooleanField("成功后是否通知", default=True)
    notify = models.TextField("通知配置", default="{}")
    solution_id = models.IntegerField(null=True, blank=True, db_index=True)
    timeout = models.IntegerField("超时时长", default=40)

    # 新告警源的字段
    source_type = models.CharField("告警源", max_length=32, blank=True, null=True, default="TNM")
    alarm_attr_id = models.CharField("告警在来源系统的特征ID", max_length=128, null=True, blank=True)
    # 保存 cc 相关属性的名称，页面显示时不用再调用接口查询
    set_names = models.TextField("Set名称", default="", blank=True)
    module_names = models.TextField("Module名称", default="", blank=True)
    topo_names = models.TextField("自由拓扑结构的名称", default="{}", blank=True)

    # 运营数据添加字段
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    create_user = models.CharField("创建人", max_length=32, default="")
    update_user = models.CharField("修改人", max_length=32, default="")

    include_biz_ids = models.TextField("启用业务", default="", blank=True, null=True)
    add_from = models.CharField("方案来源", max_length=10, default="user")

    class Meta:
        db_table = "fta_solutions_app_alarmdef"
        managed = False
