# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false

from typing import final

from django.db import models
from django.utils.translation import gettext_lazy as _

from bk_monitor_base.domains.dynamic_group.define import DynamicGroup, DynamicGroupMember
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.db_models import BaseModel


@final
class DynamicGroupORM(BaseModel):
    """
    动态分组
    """

    dynamic_group_id = models.AutoField(_("主键"), primary_key=True)
    dynamic_group_name = models.CharField(_("名称"), max_length=255)
    condition_list = models.JSONField(_("分组条件列表"), default=list)
    object_model_code = models.CharField(_("对象模型英文标识"), max_length=255)
    space_code = models.CharField(_("权限空间code"), max_length=128, default="")
    bk_tenant_id = models.CharField(_("租户ID"), max_length=64, default=DEFAULT_TENANT_ID)

    @final
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        app_label = "base_dynamic_group"
        db_table = "dynamic_group_v2"
        verbose_name = _("动态分组")
        verbose_name_plural = _("动态分组")
        indexes = [
            models.Index(fields=["object_model_code"]),
            models.Index(fields=["space_code"]),
            models.Index(fields=["bk_tenant_id"]),
        ]

    def to_entity(self) -> DynamicGroup:
        return DynamicGroup.model_validate(self)


@final
class DynamicGroupMemberORM(models.Model):
    """
    动态分组成员
    """

    dynamic_group = models.ForeignKey(
        DynamicGroupORM,
        verbose_name=_("动态分组"),
        on_delete=models.CASCADE,
        db_column="dynamic_group_id",
        db_index=True,
    )
    member = models.JSONField(_("分组成员"), default=dict)

    @final
    class Meta:
        app_label = "base_dynamic_group"
        db_table = "dynamic_group_member_v2"
        verbose_name = _("动态分组成员")
        verbose_name_plural = _("动态分组成员")

    def to_entity(self) -> DynamicGroupMember:
        return DynamicGroupMember.model_validate(self)
