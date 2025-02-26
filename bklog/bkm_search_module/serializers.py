# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.utils.drf import DateTimeFieldWithEpoch
from bkm_search_module import constants
from bkm_search_module.exceptions import ValidationError


class ScopeSerializer(serializers.Serializer):
    scopeType = serializers.ChoiceField(help_text=_("资源范围类型"), choices=constants.ScopeType.list_choices())
    scopeId = serializers.CharField(help_text=_("资源范围ID"), min_length=1)


class IndexSetListSerializer(serializers.Serializer):
    scopeList = serializers.ListField(help_text=_("要获索引集的资源范围数组"), child=ScopeSerializer(), required=False, default=[])


class SearchConditionOptionsSerializer(serializers.Serializer):
    condition_id = serializers.ListField(
        help_text=_("条件ID数组"), child=serializers.CharField(), required=False, default=[]
    )


class SearchInspectSerializer(serializers.Serializer):
    query_string = serializers.CharField(help_text=_("查询语句"), required=False, default="")


class UserConfigSerializer(serializers.Serializer):
    config = serializers.JSONField(help_text=_("用户配置"), required=False, default=dict)


class SearchAttrSerializer(serializers.Serializer):
    query_string = serializers.CharField(
        help_text=_("查询语句"), required=False, default="", allow_null=True, allow_blank=True
    )
    start_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    end_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=10)
    condition = serializers.DictField(allow_empty=True, required=False, default=dict)
    interval = serializers.CharField(required=False, default="auto", max_length=16)


class SearchFieldsSerializer(serializers.Serializer):
    start_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S", default="")
    end_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S", default="")


class CreateIndexSetFieldsConfigSerializer(serializers.Serializer):
    scope = serializers.CharField(help_text=_("查询场景"), required=False, default="default")
    name = serializers.CharField(help_text=_("字段名称"), required=True)
    display_fields = serializers.ListField(allow_empty=False, child=serializers.CharField())
    sort_list = serializers.ListField(help_text=_("排序规则"), allow_empty=True, child=serializers.ListField())

    def validate_sort_list(self, value):
        for _item in value:
            if len(_item) != 2:
                raise ValidationError(_("sort_list参数格式有误"))

            if _item[1].lower() not in ["desc", "asc"]:
                raise ValidationError(_("排序规则只支持升序asc或降序desc"))
        return value


class UpdateIndexSetFieldsConfigSerializer(serializers.Serializer):
    config_id = serializers.IntegerField(help_text=_("配置ID"), required=True)
    scope = serializers.CharField(help_text=_("字段名称"), required=False, default="default")
    name = serializers.CharField(help_text=_("字段名称"), required=True)
    display_fields = serializers.ListField(allow_empty=False, child=serializers.CharField())
    sort_list = serializers.ListField(help_text=_("排序规则"), allow_empty=True, child=serializers.ListField())

    def validate_sort_list(self, value):
        for _item in value:
            if len(_item) != 2:
                raise ValidationError(_("sort_list参数格式有误"))

            if _item[1].lower() not in ["desc", "asc"]:
                raise ValidationError(_("排序规则只支持升序asc或降序desc"))
        return value


class SearchUserIndexSetConfigSerializer(serializers.Serializer):
    config_id = serializers.IntegerField(help_text=_("配置ID"), required=True)


class DeleteIndexSetConfigSerializer(serializers.Serializer):
    config_id = serializers.IntegerField(help_text=_("配置ID"), required=True)


class LocationSerializer(serializers.Serializer):
    serverIp = serializers.CharField(help_text=_("IP地址"), required=True, allow_blank=True)
    path = serializers.CharField(help_text=_("路径"), required=True)
    gseIndex = serializers.IntegerField(help_text=_("gseIndex"), required=True)
    iterationIndex = serializers.IntegerField(help_text=_("iterationIndex"), required=True)
    dtEventTimeStamp = serializers.CharField(help_text=_("时间戳"), required=True)


class SearchContextSerializer(serializers.Serializer):
    begin = serializers.IntegerField(help_text=_("分页开始位置"), required=True)
    size = serializers.IntegerField(help_text=_("每页数量"), required=True)
    zero = serializers.BooleanField(help_text=_("是否起始为0的位置"), required=True)
    location = LocationSerializer(help_text=_("定位参数"), required=True)


class SearchTailFSerializer(serializers.Serializer):
    size = serializers.IntegerField(help_text=_("每页数量"), required=True)
    zero = serializers.BooleanField(help_text=_("是否起始为0的位置"), required=True)
    location = LocationSerializer(help_text=_("定位参数"), required=True)


class DownLoadUrlSeaializer(serializers.Serializer):
    query_string = serializers.CharField(
        help_text=_("查询语句"), required=False, default="", allow_null=True, allow_blank=True
    )
    start_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    end_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=10)
    condition = serializers.DictField(allow_empty=True, required=False, default=dict)
    export_fields = serializers.ListField(help_text=_("导出字段"), required=False, default=[])


class ExportSerializer(serializers.Serializer):
    cache_key = serializers.CharField(help_text=_("缓存key"), required=True)
