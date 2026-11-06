import time

from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _


class BaseQuerySet(QuerySet):
    def soft_delete(self):
        return super().update(is_deleted=True)

    def update(self, *args, **kwargs):
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = int(time.time() * 1000)
        return super().update(**kwargs)


class BaseManager(models.Manager):
    def get_queryset(self):
        return BaseQuerySet(self.model).filter(is_deleted=False)


class BaseModel(models.Model):
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    created_by = models.CharField(_("创建人"), max_length=100, blank=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)
    updated_by = models.CharField(_("修改人"), max_length=100, blank=True)

    class Meta:
        abstract = True


class SoftDeleteBaseModel(BaseModel):
    is_deleted = models.BooleanField(_("是否删除"), default=False)
    objects = BaseManager()
    origin_objects = models.Manager()

    def save(self, *args, **kwargs):
        self.updated_at = int(time.time() * 1000)
        if "update_fields" in kwargs and "updated_at" not in kwargs:
            kwargs["update_fields"].append("updated_at")
        super(BaseModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True


class TimeInfoMixin(models.Model):
    """
    Add time fields to another models.
    """

    class Meta:
        verbose_name = "时间相关字段"
        abstract = True

    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("修改时间", auto_now=True)


class MaintainerInfoMixin(models.Model):
    """
    Add maintainer fields to another models.
    """

    class Meta:
        verbose_name = "维护者相关字段"
        abstract = True

    created_by = models.CharField("创建者", max_length=32, default="")
    updated_by = models.CharField("更新者", max_length=32, default="")
