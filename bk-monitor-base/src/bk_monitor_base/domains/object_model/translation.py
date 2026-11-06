# pyright: reportUnknownMemberType=false

from typing import final

from modeltranslation.translator import TranslationOptions, translator

from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM


@final
class ObjectModelOptions(TranslationOptions):
    fields = ("object_model_name",)


@final
class ObjectModelGroupOptions(TranslationOptions):
    fields = ("object_model_group_name",)


translator.register(ObjectModelORM, ObjectModelOptions)
translator.register(ObjectModelGroupORM, ObjectModelGroupOptions)
