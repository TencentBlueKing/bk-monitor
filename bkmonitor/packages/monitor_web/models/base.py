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
import datetime

from django.db import models
from django.db.models import signals

from bkmonitor.utils.user import get_global_user


class OperateManagerBase(models.Manager):
    def get_queryset(self):
        return super(OperateManagerBase, self).get_queryset().filter(is_deleted=False)


class OperateRecordModelBase(models.Model):
    objects = OperateManagerBase()
    origin_objects = models.Manager()

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    class Meta:
        abstract = True

    def save(self, not_update_user=False, *args, **kwargs):
        """
        :param not_update_user: 不要重写用户信息
        :param args:
        :param kwargs:
        :return:
        """
        if not_update_user:
            return super(OperateRecordModelBase, self).save(*args, **kwargs)
        username = get_global_user() or "unknown"
        self.update_user = username
        if not self.create_user:
            self.create_user = username
        return super(OperateRecordModelBase, self).save(*args, **kwargs)

    def delete(self, hard=False, *args, **kwargs):
        """
        :param: hard: 是否为硬删除
        删除方法，不会删除数据
        而是通过标记删除字段 is_deleted 来软删除
        update 方法不触发 save 或者 delete 方法，因此也不会发出任何信号，所以手动将 pre_delete 和 post_delete 信号发出去
        """
        if hard:
            return super(OperateRecordModelBase, self).delete(*args, **kwargs)

        signals.pre_delete.send(sender=self.__class__, instance=self)
        username = get_global_user() or "unknown"

        if hasattr(self, "is_enabled"):
            # 如果 model 有 is_enabled 字段，则软删除字段之时，也将其禁用
            self.__class__.objects.filter(pk=self.pk, is_deleted=False).update(
                is_deleted=True, is_enabled=False, update_user=username, update_time=datetime.datetime.now()
            )
        else:
            self.__class__.objects.filter(pk=self.pk, is_deleted=False).update(
                is_deleted=True, update_user=username, update_time=datetime.datetime.now()
            )

        signals.post_delete.send(sender=self.__class__, instance=self)

    @property
    def show_update_time(self):
        return self.update_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_title(self):
        return ""
