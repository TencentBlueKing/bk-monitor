import json
import logging
from typing import Any, ClassVar

from django.db import models
from django.db.models.fields import DateTimeField
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.db import JsonField
from metadata.models.common import BaseModel

from .constants import SPACE_UID_HYPHEN, SYSTEM_USERNAME, SpaceStatus, SpaceTypes
from .managers import SpaceManager, SpaceResourceManager, SpaceTypeManager

logger = logging.getLogger("metadata")


class SpaceType(BaseModel):
    """空间类型
    初始化类型包含 CC、BCS、PaaS、DevOps，允许扩展
    """

    type_id = models.CharField("空间类型英文名称", max_length=64, unique=True)
    type_name = models.CharField("类型中文名称", max_length=64, unique=True)
    description = models.CharField("类型描述", max_length=128, null=True, blank=True)
    allow_merge = models.BooleanField("是否可以合并的", default=True)
    allow_bind = models.BooleanField("是否可以绑定资源", default=True)
    dimension_fields = JsonField(
        "关键校验字段", help_text="需要的校验的关键字段，格式如['project_id', 'cluster_id', 'namespace']", default=[]
    )

    objects = SpaceTypeManager()

    class Meta:
        verbose_name = "空间类型"
        verbose_name_plural = "空间类型信息"


class Space(BaseModel):
    """空间相关信息"""

    # 空间状态
    SPACE_STATUS = (
        (SpaceStatus.NORMAL.value, _lazy("正常")),
        (SpaceStatus.DISABLED.value, _lazy("停用")),
    )

    space_type_id = models.CharField("空间类型 ID", max_length=64)
    space_id = models.CharField("空间 ID", max_length=128, help_text="空间类型下唯一")
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    space_name = models.CharField("空间中文名称", max_length=256, help_text="空间类型下唯一")
    space_code = models.CharField(
        "空间英文名称", max_length=64, blank=True, null=True, help_text="针对容器和研发类型，会多存储存储code这个字段"
    )
    status = models.CharField("空间状态", max_length=32, choices=SPACE_STATUS, default=SpaceStatus.NORMAL.value)
    time_zone = models.CharField("时区", max_length=32, default="Asia/Shanghai", help_text="时区，默认为Asia/Shanghai")
    language = models.CharField("默认语言", max_length=16, default="zh-hans", help_text="使用的语言")
    is_bcs_valid = models.BooleanField("BCS 是否可用", default=False)

    objects: ClassVar[SpaceManager] = SpaceManager()

    class Meta:
        unique_together = (("space_type_id", "space_id"), ("space_type_id", "space_name", "bk_tenant_id"))
        verbose_name = "空间信息"
        verbose_name_plural = "空间信息"

    @property
    def space_uid(self):
        """空间 uid

        格式为：space_type + __ + space_id
        """
        return f"{self.space_type_id}{SPACE_UID_HYPHEN}{self.space_id}"

    def to_dict(self, fields: list | None = None, exclude: list | None = None) -> dict:
        data = {}
        for f in self._meta.concrete_fields + self._meta.many_to_many:
            value = f.value_from_object(self)
            # 属性存在
            if fields and f.name not in fields:
                continue
            # 排除的属性
            if exclude and f.name in exclude:
                continue
            # 时间转换
            if isinstance(f, DateTimeField):
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else None

            data[f.name] = value

        # 添加空间 uid
        data["space_uid"] = self.space_uid
        data["bk_tenant_id"] = self.bk_tenant_id

        return data

    @classmethod
    def bulk_create_space(cls, bk_tenant_id: str, space_type_id: str, space_list: list):
        """批量创建同类型空间"""
        logger.info(
            "bulk_create_space: try to create spaces->[%s] for tenant_id->[%s],space_type_id->[%s]",
            space_list,
            bk_tenant_id,
            space_type_id,
        )
        data = []
        for s in space_list:
            data.append(
                cls(
                    creator=SYSTEM_USERNAME,
                    space_type_id=space_type_id,
                    space_id=s["space_id"],
                    bk_tenant_id=bk_tenant_id,  # 创建记录时需要指定租户
                    space_name=s["space_name"],
                )
            )
        cls.objects.bulk_create(data)

        logger.info(
            "bulk create space successfully, space_type_id: %s, space_list: %s", space_type_id, json.dumps(space_list)
        )

    def get_bk_biz_id(self) -> int:
        if self.space_type_id == SpaceTypes.BKCC.value:
            return int(self.space_id)
        return -self.pk


class SpaceDataSource(BaseModel):
    """空间与数据源关系"""

    space_type_id = models.CharField("空间类型英文名称", max_length=64)
    space_id = models.CharField("Space 英文名称", max_length=128, db_index=True)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    bk_data_id = models.IntegerField("数据源 ID", db_index=True)
    from_authorization = models.BooleanField("是否来源于授权", default=False)

    class Meta:
        unique_together = ("space_type_id", "space_id", "bk_data_id")
        verbose_name = "空间与数据源关系配置"
        verbose_name_plural = "空间与数据源关系配置"


class SpaceResource(BaseModel):
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
    dimension_values: list[dict[str, Any]] = JsonField(
        "关键维度对应的值",
        help_text="关键维度值，格式如[{'project_id': 'testproject', 'cluster_id': 'BCS-K8S-1000', 'namespace': 'test'}]",
        default=[],
    )  # pyright: ignore [reportAssignmentType]

    objects = SpaceResourceManager()

    class Meta:
        unique_together = ("space_type_id", "space_id", "resource_type", "resource_id")
        verbose_name = "空间资源"
        verbose_name_plural = "空间资源详情"


class SpaceStickyInfo(models.Model):
    """
    空间置顶信息
    """

    space_uid_list = JsonField("置顶空间uid列表", default=[])
    username = models.CharField("用户名", max_length=64, db_index=True)


class BkAppSpaceRecord(BaseModel):
    """
    蓝鲸应用-空间授权记录
    """

    record_id = models.BigAutoField(primary_key=True)
    bk_app_code = models.CharField(verbose_name="蓝鲸应用app_code", max_length=255, null=False)
    space_uid = models.CharField(verbose_name="空间UID", max_length=255, null=False)
    is_enable = models.BooleanField(verbose_name="是否启用", default=True)

    class Meta:
        verbose_name = "蓝鲸应用空间授权记录"
        verbose_name_plural = "蓝鲸应用空间授权记录"
        unique_together = ("bk_app_code", "space_uid")


class SpaceTypeToResultTableFilterAlias(models.Model):
    """
    空间类型-结果表 路由自定义过滤条件别名
    """

    space_type = models.CharField("空间类型", max_length=64)
    table_id = models.CharField("结果表名", max_length=128)
    filter_alias = models.CharField("过滤条件别名", max_length=128)
    status = models.BooleanField("是否启用", default=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        # 一个结果表在一个空间类型下只能有一个别名
        unique_together = ("space_type", "table_id")
