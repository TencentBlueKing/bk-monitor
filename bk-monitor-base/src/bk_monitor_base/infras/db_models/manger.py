from typing import Any, cast

from django.db import models
from typing_extensions import override

# 存储旧模型数据库名称的模型类属性名
_OLD_DB_NAME_ATTR = "_old_db_name"


class OldModelManager(models.Manager):
    """旧模型管理器

    可以指定默认数据库，用于访问旧模型数据库。

    设计说明：
        Django 在处理 M2M 关联（如 prefetch_related）时，会通过
        ``create_forward_many_to_many_manager`` 动态生成 ManyRelatedManager 子类，
        并调用 ``super().__init__()`` 而不传任何参数。若 ``__init__`` 要求必填参数，
        则会在 prefetch 阶段抛出 TypeError。

        为兼容 Django 的这一内部机制，``default_db_name`` 改为可选参数（默认 None）。
        数据库名称同时通过 ``contribute_to_class`` 写入模型类属性 ``_old_db_name``，
        这样 Django 自动创建的关联 manager 的 ``get_queryset`` 也能通过
        ``self.model._old_db_name`` 取到正确的数据库名，确保 M2M 关联查询
        （如 ``task.nodes.all()``）仍路由到旧模型数据库。
    """

    def __init__(self, default_db_name: str | None = None) -> None:
        super().__init__()
        self._default_db_name: str | None = default_db_name
        # 兼容 Django Manager 内部：直接设置 _db 以支持 using() 链式调用
        if default_db_name:
            self._db: str | None = default_db_name

    @override
    def contribute_to_class(self, model: type[models.Model], name: str) -> None:
        """将数据库名称写入模型类，供关联 manager 查找。

        Django 自动生成的 ManyRelatedManager 也继承自本类，但实例化时不传
        ``default_db_name``，所以 ``self._default_db_name`` 为 None。
        通过模型类属性作为后备，确保关联 manager 也能路由到正确的数据库。
        """
        super().contribute_to_class(model, name)
        if self._default_db_name:
            setattr(model, _OLD_DB_NAME_ATTR, self._default_db_name)

    @override
    def get_queryset(self):
        """重写 get_queryset 以使用指定的数据库。

        优先使用实例级 ``_default_db_name``（直接实例化时已设置），
        其次回退到模型类属性 ``_old_db_name``（Django 自动生成的关联 manager 走此路径）。
        """
        queryset = cast(models.QuerySet[Any], super().get_queryset())
        db_name = self._default_db_name or getattr(self.model, _OLD_DB_NAME_ATTR, None)  # pyright: ignore[reportUnknownArgumentType]
        if db_name:
            queryset = queryset.using(db_name)
        return queryset
