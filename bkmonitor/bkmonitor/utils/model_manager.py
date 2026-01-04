"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import time

from django.conf import settings
from django.db import connections, models
from django.db.models import Value, signals
from django.db.models.sql import InsertQuery
from django.db.utils import OperationalError

from bkmonitor.utils.user import get_global_user


def close_all_django_db_connections():
    for conn in connections.all():
        if not conn.in_atomic_block:
            conn.close_if_unusable_or_obsolete()


class AutoConnManagerMixin:
    def __init__(self, *args, **kwargs):
        self.time = time.time()
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if settings.DATABASE_CONNECTION_AUTO_CLEAN_INTERVAL:
            interval = time.time() - self.time
            if interval > settings.DATABASE_CONNECTION_AUTO_CLEAN_INTERVAL:
                close_all_django_db_connections()
                self.time = time.time()

        return super().get_queryset()


class IgnoreBlurInsertMixin:
    @classmethod
    def _compiler_as_sql_hacker(cls, compiler):
        def as_sql(*args, **kwargs):
            return [(sql.replace("INSERT", "INSERT IGNORE", 1), value) for sql, value in raw_as_sql(*args, **kwargs)]

        raw_as_sql = compiler.as_sql
        compiler.as_sql = as_sql
        return as_sql

    def ignore_blur_create_with_fields(self, objs, fields):
        query = InsertQuery(self.model)
        query.insert_values(fields, objs)
        compiler = query.get_compiler(self.db)
        self._compiler_as_sql_hacker(compiler)
        compiler.execute_sql(False)

    def _ignore_blur_create(self, objs, batch_size=None):
        fields = [f for f in self.model._meta.concrete_fields if not isinstance(f, models.AutoField)]
        obj_length = len(objs)
        batch_size = batch_size or obj_length
        for chunked_objs in (objs[i : i + batch_size] for i in range(0, obj_length, batch_size)):
            self.ignore_blur_create_with_fields(chunked_objs, fields)

    def ignore_blur_create(self, objs, batch_size=None):
        try:
            if batch_size is None:
                batch_size = 200
            self._ignore_blur_create(objs, batch_size)
        except OperationalError:
            # Try again when "Lost connection" or "MySQL server has gone away"
            close_all_django_db_connections()
            self._ignore_blur_create(objs, batch_size)


class ModelManager(
    AutoConnManagerMixin,
    IgnoreBlurInsertMixin,
    models.Manager,
):
    pass


class Model(models.Model):
    objects = ModelManager()

    class Meta:
        abstract = True


class RecordModelManager(ModelManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=Value(0))

    def create(self, *args, **kwargs):
        kwargs.update({"create_user": get_global_user() or "unknown"})
        return super().create(*args, **kwargs)


class AbstractRecordModel(models.Model):
    is_enabled = models.BooleanField(
        "是否启用",
        default=True,
    )
    is_deleted = models.BooleanField(
        "是否删除",
        default=False,
    )
    create_user = models.CharField(
        "创建人",
        max_length=32,
        default="",
        blank=True,
    )
    create_time = models.DateTimeField(
        "创建时间",
        auto_now_add=True,
        blank=True,
    )
    update_user = models.CharField(
        "最后修改人",
        max_length=32,
        default="",
        blank=True,
    )
    update_time = models.DateTimeField(
        "最后修改时间",
        auto_now=True,
        blank=True,
    )

    objects = RecordModelManager()
    # 保存原始的 manager ，以做特殊数据查找时使用。现在有的 objects ，会对 is_deleted 做过滤
    origin_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        username = get_global_user() or "unknown"
        self.update_user = username
        if self.pk is None:
            self.create_user = username
        return super().save(*args, **kwargs)

    def delete(self, hard=False, *args, **kwargs):
        if hard:
            return super().delete(*args, **kwargs)

        signals.pre_delete.send(sender=self.__class__, instance=self)
        username = get_global_user() or "unknown"
        self.__class__.objects.filter(pk=self.pk, is_deleted=Value(0)).update(
            is_deleted=True, is_enabled=False, update_user=username, update_time=datetime.datetime.now()
        )

        signals.post_delete.send(sender=self.__class__, instance=self)
