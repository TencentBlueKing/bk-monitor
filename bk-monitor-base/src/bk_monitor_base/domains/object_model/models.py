# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false

from typing import final

from django.conf import settings
from django.db import models
from django.db.models import ForeignKey
from django.utils.translation import gettext_lazy as _
from typing_extensions import override

from bk_monitor_base.domains.object_model.define import ObjectModel, ObjectModelGroup, ObjectModelUsageRecord
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.i18n.language import get_language


@final
class ObjectModelGroupORM(models.Model):
    """
    对象模型分组
    """

    object_model_group_id = models.AutoField(_("主键"), primary_key=True)
    bk_tenant_id = models.CharField(
        _("租户ID"),
        max_length=256,
        default=DEFAULT_TENANT_ID,
        db_index=True,
        help_text=_("租户标识，用于多租户数据隔离"),
    )
    parent_object_model_group = ForeignKey("self", verbose_name=_("父级分组"), on_delete=models.PROTECT, null=True)
    object_model_group_code = models.CharField(_("分组code"), max_length=255)
    object_model_group_name = models.CharField(_("分组名称"), max_length=255)
    is_default = models.BooleanField(_("是否内置"))

    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    created_by = models.CharField(_("创建人"), max_length=100, blank=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)
    updated_by = models.CharField(_("修改人"), max_length=100, blank=True)

    @final
    class Meta:
        db_table = "object_model_group_v2"
        verbose_name = _("对象模型分组")
        verbose_name_plural = _("对象模型分组")
        unique_together = [
            ("bk_tenant_id", "object_model_group_code"),
            ("bk_tenant_id", "parent_object_model_group", "object_model_group_name"),
        ]

    @property
    def level(self) -> int:
        """分组层级"""
        return 2 if self.parent_object_model_group else 1

    @property
    def object_model_group_name_i18n(self) -> dict[str, str]:
        """对象模型分组名称多语言"""
        object_model_group_name_i18n: dict[str, str] = {}
        for lang in settings.LANGUAGES:
            language = get_language(code=lang[0])
            field_name = language.format_db_field_key("object_model_group_name")
            value = getattr(self, field_name, None)
            if value is not None:
                object_model_group_name_i18n[language.frontend_code] = value
        return object_model_group_name_i18n

    def to_entity(self) -> ObjectModelGroup:
        return ObjectModelGroup.model_validate(self)


class DatasourceChoice(models.TextChoices):
    """
    对象模型数据来源
    """

    CMDB = "cmdb"  # cmdb
    CUSTOM = "custom"  # 自定义
    LEGACY = "legacy"  # 兼容旧子对象模型数据


@final
class ObjectModelORM(models.Model):
    """
    对象模型
    """

    class RelateTypeChoice(models.TextChoices):
        """
        对象模型关联类型
        """

        APM = "APM"  # 提供给APM使用
        LEGACY = "LEGACY"  # 兼容旧子对象模型数据
        EMPTY = ""  # 未关联

    object_model_id = models.AutoField(_("主键"), primary_key=True)
    bk_tenant_id = models.CharField(
        _("租户ID"),
        max_length=256,
        default=DEFAULT_TENANT_ID,
        db_index=True,
        help_text=_("租户标识，用于多租户数据隔离"),
    )
    object_model_code = models.CharField(_("对象模型英文标识"), max_length=255)
    object_model_name = models.CharField(_("对象模型名称"), max_length=255)
    object_model_group = models.ForeignKey(
        ObjectModelGroupORM, verbose_name=_("对象模型分组"), on_delete=models.PROTECT
    )
    is_default = models.BooleanField(_("是否内置"), default=False)
    datasource = models.CharField(_("实例来源"), choices=DatasourceChoice.choices, max_length=32)

    # cmdb公共字段
    bk_cmdb_obj_id = models.CharField(_("cmdb模型id"), default="", max_length=255)
    display_fields = models.JSONField(_("标识展示字段"), default=list)
    inst_display_name = models.CharField(verbose_name=_("实例展示名"), max_length=128, default="")

    # DatasourceChoice.CMDB 映射字段相关
    host_related_field = models.CharField(_("运行主机关联字段"), default="", max_length=255)
    operator_fields = models.JSONField(_("负责人字段"), default=list)
    topo_related_field = models.CharField(_("IP映射字段"), default="", max_length=255)
    port_field = models.CharField(_("端口映射字段"), default="", max_length=255)

    # DatasourceChoice.CUSTOM 关联字段相关
    custom_model_field = models.CharField(_("自定义模型字段"), default="", max_length=255)
    model_related_field = models.CharField(_("关联模型字段"), default="", max_length=255)

    # 对象模型关联相关
    related_model_type = models.CharField(
        verbose_name=_("关联类型"),
        max_length=8,
        choices=RelateTypeChoice.choices,
        default=RelateTypeChoice.EMPTY,
    )
    related_model_code = models.CharField(_("关联模型标识"), default="", max_length=255, blank=True)
    ar_dimensionality = models.CharField(_("apm唯一标识列表"), max_length=64, default="")

    # 对象模型属性配置
    attribute_config = models.JSONField(_("对象模型属性配置"), default=dict)

    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    created_by = models.CharField(_("创建人"), max_length=100, blank=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)
    updated_by = models.CharField(_("修改人"), max_length=100, blank=True)

    @final
    class Meta:
        db_table = "object_model_v2"
        verbose_name = _("对象模型")
        verbose_name_plural = _("对象模型")
        unique_together = [
            ("bk_tenant_id", "object_model_code"),
            ("bk_tenant_id", "object_model_name"),
        ]

    @property
    def object_model_name_i18n(self) -> dict[str, str]:
        """对象模型名称多语言"""
        object_model_name_i18n: dict[str, str] = {}
        for lang in settings.LANGUAGES:
            language = get_language(code=lang[0])
            field_name = language.format_db_field_key("object_model_name")
            value = getattr(self, field_name, None)
            if value is not None:
                object_model_name_i18n[language.frontend_code] = value
        return object_model_name_i18n

    @override
    def save(self, *args, **kwargs):
        from bk_monitor_base.domains.object_model.define import AttributeConfig

        if isinstance(self.attribute_config, AttributeConfig):
            self.attribute_config = self.attribute_config.model_dump()
        super().save(*args, **kwargs)

    def to_entity(self) -> ObjectModel:
        return ObjectModel.model_validate(self)


@final
class ObjectModelUsageRecordORM(models.Model):
    """
    对象模型引用记录
    """

    id = models.BigAutoField(_("ID"), primary_key=True, auto_created=True)
    bk_tenant_id = models.CharField(
        _("租户ID"),
        max_length=256,
        default=DEFAULT_TENANT_ID,
        db_index=True,
        help_text=_("租户标识，用于多租户数据隔离"),
    )
    object_model = models.ForeignKey(to=ObjectModelORM, on_delete=models.PROTECT, verbose_name=_("监控对象ID"))
    app_id = models.CharField(_("关联SaasID"), max_length=64)
    app_name = models.CharField(_("关联Saas名称"), max_length=64)
    module_id = models.CharField(_("关联模块ID"), max_length=255)
    module_name = models.CharField(_("关联模块名称"), max_length=255)
    inst_id = models.CharField(_("关联实例ID"), max_length=255)
    inst_name = models.CharField(_("关联实例名称"), max_length=255)

    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    created_by = models.CharField(_("创建人"), max_length=100, blank=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)
    updated_by = models.CharField(_("修改人"), max_length=100, blank=True)

    @final
    class Meta:
        db_table = "object_model_usage_record_v2"
        verbose_name = _("对象模型引用记录")
        verbose_name_plural = _("对象模型引用记录")
        unique_together = ("bk_tenant_id", "object_model", "app_id", "module_id", "inst_id")

    def to_entity(self) -> ObjectModelUsageRecord:
        return ObjectModelUsageRecord.model_validate(self)
