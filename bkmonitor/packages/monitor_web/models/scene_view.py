"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum

from django.db import models
from django.db.transaction import atomic
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.utils.translation import gettext as _


class I18nJSONField(models.JSONField):
    """支持国际化 lazy 对象的 JSONField，自动将 Promise 对象转换为字符串"""

    def get_prep_value(self, value):
        if value is None:
            return value

        # 递归处理 lazy 对象
        def convert(obj):
            if isinstance(obj, Promise):
                return force_str(obj)
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list | tuple):
                return [convert(item) for item in obj]
            return obj

        return super().get_prep_value(convert(value))


class SceneModel(models.Model):
    """
    场景
    """

    unique_id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField("业务ID")
    id = models.CharField("场景ID", max_length=32)
    name = models.CharField("名称", max_length=64)
    data_range = I18nJSONField("数据范围", default=list)
    view_order = I18nJSONField("视图顺序", default=dict)

    class Meta:
        verbose_name_plural = verbose_name = "场景"
        unique_together = (("bk_biz_id", "id"),)


class SceneViewModel(models.Model):
    """
    场景视图

    场景视图目前分为两层
    1. 一层为overview类型，有列表，概览页
    2. 一层为detail类型，有各种对象详情页，页面存在固定引用的对象详情变量，有目标选择器。
    逻辑上允许两层各自添加页签。
    """

    class SceneViewType(Enum):
        auto = _("平铺")
        custom = _("自定义")

    unique_id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField("业务ID")
    scene_id = models.CharField("场景ID", max_length=128)
    id = models.CharField("视图ID", max_length=32)
    name = models.CharField("名称", max_length=64)
    variables = I18nJSONField("变量配置", default=list)
    type = models.CharField(
        "视图类型", max_length=16, choices=(("overview", _("概览")), ("detail", _("详情"))), blank=True
    )
    mode = models.CharField(
        "模式", max_length=16, default=SceneViewType.auto.name, choices=[(t.name, t.value) for t in SceneViewType]
    )
    order = I18nJSONField("排序配置(平铺模式专用)", default=list)
    panels = I18nJSONField("图表配置", default=list)
    list = I18nJSONField("列表页配置", default=list)
    options = I18nJSONField("配置项", default=dict)

    class Meta:
        verbose_name_plural = verbose_name = "场景视图"
        unique_together = (("bk_biz_id", "scene_id", "type", "id"),)
        index_together = (("bk_biz_id", "scene_id", "type", "id"),)

    @atomic(using="default")
    def update_order(self, index: int = None):
        """
        更新视图排序配置
        """

        record, _ = SceneViewOrderModel.objects.select_for_update().get_or_create(
            bk_biz_id=self.bk_biz_id, scene_id=self.scene_id, type=self.type
        )
        order_config: list = record.config

        # 取出view_id
        try:
            old_index = order_config.index(self.id)
            # 如果顺序未发生变化，直接退出
            if old_index == index:
                return
            order_config.pop(old_index)
        except ValueError:
            pass

        # 插入view_id
        if index is None:
            order_config.append(self.id)
        else:
            order_config.insert(index, self.id)
        record.save()


class SceneViewOrderModel(models.Model):
    """
    场景视图排序配置
    """

    bk_biz_id = models.IntegerField("业务ID")
    scene_id = models.CharField("场景ID", max_length=32)
    type = models.CharField("类型", max_length=16, choices=(("overview", _("概览")), ("detail", _("详情"))), blank=True)
    config = I18nJSONField("排序配置", default=list)

    class Meta:
        verbose_name_plural = verbose_name = "场景视图排序"
        unique_together = (("bk_biz_id", "scene_id", "type"),)
        index_together = (("bk_biz_id", "scene_id", "type"),)
