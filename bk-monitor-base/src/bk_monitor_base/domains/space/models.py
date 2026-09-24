from typing import Any, final

from django.db import models

from bk_monitor_base.config.all import get_config
from bk_monitor_base.infras.constant import OLD_MONITOR_BACKEND_DB_NAME, SPACE_UID_HYPHEN
from bk_monitor_base.infras.db_models.manger import OldModelManager

from .define import Space, SpaceStatus, SpaceTypeEnum

# 空间模型是否使用旧模型
if get_config().domains.space.use_old_model:
    models_manager: models.Manager[Any] = OldModelManager(default_db_name=OLD_MONITOR_BACKEND_DB_NAME)
    managed = False
else:
    models_manager = models.Manager()
    managed = True


@final
class SpaceModel(models.Model):
    """空间相关信息"""

    # 空间状态
    SPACE_STATUS = (
        (SpaceStatus.NORMAL.value, "正常"),
        (SpaceStatus.DISABLED.value, "停用"),
    )

    space_type_id = models.CharField("空间类型 ID", max_length=64)
    space_id = models.CharField("空间 ID", max_length=128, help_text="空间类型下唯一, BKCC是业务ID，其他类型是项目Code")
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    space_name = models.CharField("空间中文名称", max_length=256, help_text="空间类型下唯一")
    space_code = models.CharField(
        "空间英文名称", max_length=64, blank=True, null=True, help_text="针对容器和研发类型，会多存储存储code这个字段"
    )
    status = models.CharField("空间状态", max_length=32, choices=SPACE_STATUS, default=SpaceStatus.NORMAL.value)
    time_zone = models.CharField("时区", max_length=32, default="Asia/Shanghai", help_text="时区，默认为Asia/Shanghai")
    language = models.CharField("默认语言", max_length=16, default="zh-hans", help_text="使用的语言")
    is_bcs_valid = models.BooleanField("BCS 是否可用", default=False)
    is_global = models.BooleanField("跨业务管理可用", default=False)
    creator = models.CharField("创建者", max_length=64)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    updater = models.CharField("更新者", max_length=64)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    objects = models_manager

    @final
    class Meta:
        db_table = "metadata_space"
        unique_together = (
            ("space_type_id", "space_id"),
            ("space_type_id", "space_name", "bk_tenant_id"),
        )
        verbose_name = "空间信息"
        verbose_name_plural = "空间信息"
        managed = managed

    @property
    def space_uid(self) -> str:
        """空间 uid

        格式为：space_type + __ + space_id
        """
        return f"{self.space_type_id}{SPACE_UID_HYPHEN}{self.space_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_type_id": self.space_type_id,
            "space_id": self.space_id,
            "bk_tenant_id": self.bk_tenant_id,
            "space_name": self.space_name,
            "space_code": self.space_code,
            "status": self.status,
            "time_zone": self.time_zone,
            "language": self.language,
            "is_bcs_valid": self.is_bcs_valid,
            "is_global": self.is_global,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "updater": self.updater,
            "update_time": self.update_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_bk_biz_id(self) -> int:
        """获取蓝鲸业务ID

        BKCC类型的空间，返回 space_id 的整数值
        其他类型的空间，返回 -pk（负数）
        """
        if self.space_type_id == SpaceTypeEnum.BKCC.value:
            return int(self.space_id)
        if self.pk is None:
            raise ValueError(
                f"无法获取非 BKCC 类型空间的 bk_biz_id：空间对象尚未保存到数据库（space_type_id={self.space_type_id}, space_id={self.space_id}）"
            )
        return -self.pk

    def to_space(self) -> Space:
        """转换为空间对象"""
        if not self.bk_tenant_id:
            raise ValueError("bk_tenant_id is required")

        return Space(
            bk_biz_id=self.get_bk_biz_id(),
            uid=self.space_uid,
            bk_tenant_id=self.bk_tenant_id,
            type=SpaceTypeEnum(self.space_type_id),
            name=self.space_name,
            status=SpaceStatus(self.status),
            timezone=self.time_zone,
            language=self.language,
            configs={},
            is_global=self.is_global,
            creator=self.creator,
            create_time=self.create_time,
            updater=self.updater,
            update_time=self.update_time,
        )


@final
class SpaceResource(models.Model):
    """空间资源信息"""

    space_type_id = models.CharField("空间类型英文名称", max_length=64)
    space_id = models.CharField("空间英文名称", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    resource_type = models.CharField("资源类型", max_length=128, help_text="关联的资源类型，必须属于某个空间类型")
    resource_id = models.CharField(
        "关联的资源唯一标识",
        max_length=64,
        blank=True,
        null=True,
        help_text="关联的资源的唯一标识，如关联BCS项目ID，BKCC业务ID等",
    )
    dimension_values = models.TextField(
        "关键维度对应的值",
        help_text="关键维度值，格式如[{'project_id': 'testproject', 'cluster_id': 'BCS-K8S-1000', 'namespace': 'test'}]",
        default="[]",
    )
    creator = models.CharField("创建者", max_length=64)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    updater = models.CharField("更新者", max_length=64)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    objects = models_manager

    @final
    class Meta:
        db_table = "metadata_spaceresource"
        unique_together = ("space_type_id", "space_id", "resource_type", "resource_id")
        verbose_name = "空间资源"
        verbose_name_plural = "空间资源详情"
        managed = managed
