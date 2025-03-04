# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import datetime
import re
import time

import arrow
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.exceptions import ValidationError
from apps.log_desensitize.constants import DesensitizeOperator, DesensitizeRuleStateEnum
from apps.log_desensitize.handlers.desensitize_operator import OPERATOR_MAPPING
from apps.log_esquery.constants import WILDCARD_PATTERN
from apps.log_search.constants import (
    ExportFileType,
    FavoriteListOrderType,
    FavoriteType,
    FavoriteVisibleType,
    IndexSetType,
    InstanceTypeEnum,
    QueryMode,
    SearchMode,
    SearchScopeEnum,
    TagColor,
    TemplateType,
)
from apps.log_search.models import LogIndexSetData, ProjectInfo, Scenario
from apps.log_unifyquery.constants import FIELD_TYPE_MAP
from apps.utils.drf import DateTimeFieldWithEpoch
from apps.utils.local import get_local_param
from apps.utils.lucene import EnhanceLuceneAdapter
from bkm_space.serializers import SpaceUIDField

HISTORY_MAX_DAYS = 7


class PageSerializer(serializers.Serializer):
    """
    分页序列化器
    """

    page = serializers.IntegerField(label=_("页码"), default=1)
    pagesize = serializers.IntegerField(label=_("分页大小"), default=10)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInfo
        fields = ["project_id", "project_name", "bk_biz_id", "bk_app_code", "time_zone", "description"]


class ResultTableListSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(label=_("接入场景"))
    bk_biz_id = serializers.IntegerField(label=_("业务ID"), required=False)
    storage_cluster_id = serializers.IntegerField(label=_("集群ID"), required=False)
    result_table_id = serializers.CharField(label=_("索引"), required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        scenario_id = attrs["scenario_id"]
        if scenario_id in [Scenario.BKDATA, Scenario.LOG] and not attrs.get("bk_biz_id"):
            raise ValidationError(_("业务ID不能为空"))

        if scenario_id == Scenario.ES and not attrs.get("storage_cluster_id"):
            raise ValidationError(_("数据源ID不能为空"))

        return attrs


class ResultTableTraceMatchSerializer(serializers.Serializer):
    indices = serializers.ListField(label=_("索引列表"))
    scenario_id = serializers.CharField(label=_("接入场景"))
    storage_cluster_id = serializers.IntegerField(label=_("数据源ID"), required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        scenario_id = attrs["scenario_id"]
        indices = attrs.get("indices")
        if scenario_id == Scenario.ES and not attrs.get("storage_cluster_id"):
            raise ValidationError(_("数据源ID不能为空"))
        if scenario_id not in [Scenario.ES] and not indices:
            raise ValidationError(_("indices不能为空"))
        return attrs


class ResultTableDetailSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(label=_("接入场景"))
    storage_cluster_id = serializers.IntegerField(label=_("数据源ID"), required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        scenario_id = attrs["scenario_id"]
        if scenario_id == Scenario.ES and not attrs.get("storage_cluster_id"):
            raise ValidationError(_("数据源ID不能为空"))

        return attrs


class ResultTableAdaptSerializer(serializers.Serializer):
    class IndexSerializer(serializers.Serializer):
        index = serializers.CharField(required=True)
        time_field = serializers.CharField(required=False, allow_null=True, allow_blank=True)
        time_field_type = serializers.ChoiceField(
            choices=["date", "long"], required=False, allow_null=True, allow_blank=True
        )

    scenario_id = serializers.CharField(label=_("接入场景"))
    storage_cluster_id = serializers.CharField(label=_("存储集群ID"), required=False, allow_blank=True, allow_null=True)
    basic_index = IndexSerializer(label=_("源索引"), required=False)
    basic_indices = serializers.ListField(label=_("源索引"), child=IndexSerializer(), required=False)
    append_index = IndexSerializer(label=_("待追加的索引"))

    def validate(self, attrs):
        attrs = super().validate(attrs)

        scenario_id = attrs["scenario_id"]
        if scenario_id == Scenario.ES and not attrs.get("storage_cluster_id"):
            raise ValidationError(_("数据源ID不能为空"))

        # 第三方ES必须传入时间字段和类型
        basic_indices = attrs.get("basic_indices", [])
        if scenario_id == Scenario.ES and basic_indices:
            for basic_index in basic_indices:
                if not basic_index.get("time_field"):
                    raise ValidationError(_("源索引时间字段不能为空"))
                if not basic_index.get("time_field_type"):
                    raise ValidationError(_("源索引时间字段类型不能为空"))
        append_index = attrs.get("append_index")
        if scenario_id == Scenario.ES:
            if not append_index.get("time_field"):
                raise ValidationError(_("待追加索引时间字段不能为空"))
            if not append_index.get("time_field_type"):
                raise ValidationError(_("待追加索引时间字段类型不能为空"))

        return attrs


class DesensitizeConfigSerializer(serializers.Serializer):
    """
    脱敏配置序列化器
    """

    rule_id = serializers.IntegerField(label=_("脱敏规则ID"), required=False)
    match_pattern = serializers.CharField(
        label=_("匹配模式"), required=False, allow_null=True, allow_blank=True, default=""
    )
    operator = serializers.ChoiceField(label=_("脱敏算子"), choices=DesensitizeOperator.get_choices(), required=False)
    params = serializers.DictField(label=_("脱敏配置参数"), required=False)
    state = serializers.ChoiceField(
        label=_("规则状态"),
        required=False,
        choices=DesensitizeRuleStateEnum.get_choices(),
        default=DesensitizeRuleStateEnum.ADD.value,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("rule_id") and not attrs.get("operator"):
            raise ValidationError(_("脱敏算子不能为空"))

        if attrs.get("operator"):
            # 获取算子对象
            desensitize_cls = OPERATOR_MAPPING.get(attrs.get("operator"))

            if not desensitize_cls:
                raise ValidationError(_("{}脱敏算子类型暂未支持").format(attrs.get("operator")))

            if not attrs.get("params"):
                return attrs

            desensitize_serializer = desensitize_cls.ParamsSerializer(data=attrs.get("params"), many=False)

            # 脱敏参数校验
            desensitize_serializer.is_valid(raise_exception=True)

            data = desensitize_serializer.validated_data

            # 赋值
            attrs["params"] = dict(data)

        return attrs


class DesensitizeConfigsSerializer(serializers.Serializer):
    field_name = serializers.CharField(label=_("字段名"), required=True)
    rules = serializers.ListField(child=DesensitizeConfigSerializer(), required=True, allow_empty=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        rules = attrs.get("rules")
        field_name = attrs.get("field_name")
        rule_ids = list()
        for rule in rules:
            rule_id = rule.get("rule_id")
            if rule_id and rule_id in rule_ids:
                raise ValidationError(_("【{}】字段绑定了多个相同的规则ID").format(field_name))
            if rule_id:
                rule_ids.append(rule_id)

        return attrs


class CreateOrUpdateDesensitizeConfigSerializer(serializers.Serializer):
    field_configs = serializers.ListField(child=DesensitizeConfigsSerializer(), required=True)
    text_fields = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        field_configs = attrs.get("field_configs")
        field_names = list()
        for config in field_configs:
            if config["field_name"] in field_names:
                raise ValidationError(_("【{}】字段存在多个脱敏配置").format(config["field_name"]))
            else:
                field_names.append(config["field_name"])
        return attrs


class DesensitizeConfigStateSerializer(serializers.Serializer):
    index_set_ids = serializers.ListField(child=serializers.IntegerField(), required=True)


class IndexSetAddTagSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField(label=_("标签ID"), required=True)


class IndexSetDeleteTagSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField(label=_("标签ID"), required=True)


class CreateIndexSetTagSerializer(serializers.Serializer):
    name = serializers.CharField(label=_("标签名称"), max_length=255, required=True)
    color = serializers.ChoiceField(
        label=_("标签颜色"), choices=TagColor.get_choices(), default=TagColor.GREEN.value, required=False
    )


class KeywordSerializer(serializers.Serializer):
    """
    检索关键词序列化, 针对keyword为必须的时候, 继承该类
    """

    keyword = serializers.CharField(label=_("检索关键词"), required=True, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["keyword"].strip() == "":
            attrs["keyword"] = WILDCARD_PATTERN
            return attrs

        enhance_lucene_adapter = EnhanceLuceneAdapter(query_string=attrs["keyword"])
        attrs["keyword"] = enhance_lucene_adapter.enhance()
        return attrs


class SearchAttrSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务ID"), required=False, default=None)
    search_mode = serializers.ChoiceField(
        label=_("检索模式"), required=False, choices=SearchMode.get_choices(), default=SearchMode.UI.value
    )
    ip_chooser = serializers.DictField(default={}, required=False)
    addition = serializers.ListField(allow_empty=True, required=False, default="")

    start_time = DateTimeFieldWithEpoch(required=False)
    end_time = DateTimeFieldWithEpoch(required=False)
    time_range = serializers.CharField(required=False, default=None)
    from_favorite_id = serializers.IntegerField(required=False, default=0)

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=10)

    aggs = serializers.DictField(required=False, default=dict)

    # 支持用户自定义排序
    sort_list = serializers.ListField(required=False, allow_null=True, allow_empty=True, child=serializers.ListField())

    is_scroll_search = serializers.BooleanField(label=_("是否scroll查询"), required=False, default=False)

    scroll_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    is_return_doc_id = serializers.BooleanField(label=_("是否返回文档ID"), required=False, default=False)

    is_desensitize = serializers.BooleanField(label=_("是否脱敏"), required=False, default=True)

    track_total_hits = serializers.BooleanField(label=_("是否统计总数"), required=False, default=False)

    # 自定义索引列表 Eg. -> "2_bklog.0001,2_bklog.0002"
    custom_indices = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("keyword") and attrs["keyword"].strip() == "":
            attrs["keyword"] = WILDCARD_PATTERN
        # 校验sort_list
        if attrs.get("sort_list"):
            for sort_info in attrs.get("sort_list"):
                field_name, order = sort_info
                if order not in ["desc", "asc"]:
                    raise ValidationError(_("字段名【{}】的排序规则指定错误, 支持('desc', 降序）,('asc', 升序）").format(field_name))
        return attrs


class OriginalSearchAttrSerializer(serializers.Serializer):
    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=3, max_value=10)


class UnionConfigSerializer(serializers.Serializer):
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=True)
    begin = serializers.IntegerField(required=False, default=0)
    is_desensitize = serializers.BooleanField(label=_("是否脱敏"), required=False, default=True)


class UnionSearchAttrSerializer(SearchAttrSerializer):
    union_configs = serializers.ListField(
        label=_("联合检索参数"), required=True, allow_empty=False, child=UnionConfigSerializer()
    )
    index_set_ids = serializers.ListField(label=_("索引集列表"), required=False, default=[])

    def validate(self, attrs):
        attrs = super().validate(attrs)

        attrs["index_set_ids"] = sorted([config["index_set_id"] for config in attrs.get("union_configs", [])])

        return attrs


class UnionSearchFieldsSerializer(serializers.Serializer):
    start_time = DateTimeFieldWithEpoch(required=False)
    end_time = DateTimeFieldWithEpoch(required=False)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=True, allow_empty=False, child=serializers.IntegerField()
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["index_set_ids"] = sorted(attrs.get("index_set_ids", []))

        return attrs


class UserSearchHistorySerializer(serializers.Serializer):
    start_time = DateTimeFieldWithEpoch(required=False)
    end_time = DateTimeFieldWithEpoch(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        # 最多查询7天数据,如果开始时间或者结束时间为空，查询最近7天数据
        if start_time and end_time:
            days = (end_time - start_time).days
            if days > HISTORY_MAX_DAYS:
                raise ValidationError(_("最大只支持查询7天数据"))
        else:
            time_zone = get_local_param("time_zone")
            attrs["end_time"] = arrow.get(int(time.time())).to(time_zone).strftime("%Y-%m-%d %H:%M:%S%z")
            attrs["start_time"] = (
                datetime.datetime.strptime(attrs["end_time"], "%Y-%m-%d %H:%M:%S%z")
                - datetime.timedelta(days=HISTORY_MAX_DAYS)
            ).strftime("%Y-%m-%d %H:%M:%S%z")
        return attrs


class SearchIndexSetScopeSerializer(serializers.Serializer):
    """
    获取索引集所属项目
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)


class IndexSetFieldsConfigBaseSerializer(serializers.Serializer):
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=False)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=False, child=serializers.IntegerField(), default=[]
    )
    index_set_type = serializers.ChoiceField(
        label=_("索引集类型"), required=False, choices=IndexSetType.get_choices(), default=IndexSetType.SINGLE.value
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs["index_set_type"] == IndexSetType.SINGLE.value and not attrs.get("index_set_id"):
            raise serializers.ValidationError(_("索引集ID不能为空"))
        elif attrs["index_set_type"] == IndexSetType.UNION.value and not attrs.get("index_set_ids"):
            raise serializers.ValidationError(_("索引集ID列表不能为空"))
        elif attrs["index_set_type"] == IndexSetType.UNION.value:
            # 对index_set_ids排序处理  这里主要是为了兼容前端传递索引集列表ID顺序不一致问题 [1,2]  [2,1] ->[1,2]
            attrs["index_set_ids"] = sorted(attrs["index_set_ids"])

        return attrs


class CreateIndexSetFieldsConfigSerializer(IndexSetFieldsConfigBaseSerializer):
    name = serializers.CharField(label=_("字段名称"), required=True)
    display_fields = serializers.ListField(allow_empty=False, child=serializers.CharField())
    sort_list = serializers.ListField(label=_("排序规则"), allow_empty=True, child=serializers.ListField())

    def validate(self, attrs):
        attrs = super().validate(attrs)

        for _item in attrs["sort_list"]:
            if len(_item) != 2:
                raise ValidationError(_("sort_list参数格式有误"))

            if _item[1].lower() not in ["desc", "asc"]:
                raise ValidationError(_("排序规则只支持升序asc或降序desc"))

        return attrs


class UpdateIndexSetFieldsConfigSerializer(CreateIndexSetFieldsConfigSerializer):
    config_id = serializers.IntegerField(label=_("配置ID"), required=True)


class IndexSetFieldsConfigListSerializer(IndexSetFieldsConfigBaseSerializer):
    scope = serializers.CharField(label=_("搜索类型"), required=False, default=SearchScopeEnum.DEFAULT.value)


class SearchUserIndexSetConfigSerializer(IndexSetFieldsConfigBaseSerializer):
    config_id = serializers.IntegerField(label=_("配置ID"), required=True)


class SearchUserIndexSetDeleteConfigSerializer(serializers.Serializer):
    config_id = serializers.IntegerField(label=_("配置ID"), required=True)


class SearchUserIndexSetOptionHistorySerializer(serializers.Serializer):
    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    index_set_type = serializers.ChoiceField(
        label=_("索引集类型"), required=False, choices=IndexSetType.get_choices(), default=IndexSetType.SINGLE.value
    )


class SearchUserIndexSetOptionHistoryDeleteSerializer(serializers.Serializer):
    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    index_set_type = serializers.ChoiceField(
        label=_("索引集类型"), required=False, choices=IndexSetType.get_choices(), default=IndexSetType.SINGLE.value
    )
    history_id = serializers.IntegerField(label=_("历史记录ID"), required=False)
    is_delete_all = serializers.BooleanField(label=_("是否删除用户当前空间下所有历史记录"), required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if not attrs["is_delete_all"] and not attrs.get("history_id"):
            raise ValidationError(_("历史记录ID不能为空"))

        return attrs


class SearchExportSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务id"), required=True)
    keyword = serializers.CharField(label=_("搜索关键字"), required=False, allow_null=True, allow_blank=True)
    time_range = serializers.CharField(label=_("时间范围"), required=False)
    start_time = DateTimeFieldWithEpoch(label=_("起始时间"), required=True)
    end_time = DateTimeFieldWithEpoch(label=_("结束时间"), required=True)
    ip_chooser = serializers.DictField(label=_("检索IP条件"), required=False, default={})
    addition = serializers.ListField(label=_("搜索条件"), required=False)
    begin = serializers.IntegerField(label=_("检索开始 offset"), required=True)
    size = serializers.IntegerField(label=_("检索结果大小"), required=True)
    interval = serializers.CharField(label=_("匹配规则"), required=False)
    export_fields = serializers.ListField(label=_("导出字段"), required=False, default=[])
    is_desensitize = serializers.BooleanField(label=_("是否脱敏"), required=False, default=True)
    file_type = serializers.ChoiceField(
        label=_("下载文件类型"), required=False, choices=ExportFileType.get_choices(), default=ExportFileType.LOG.value
    )
    # 自定义索引列表 Eg. -> "2_bklog.0001,2_bklog.0002"
    custom_indices = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")


class UnionSearchSearchExportSerializer(SearchExportSerializer):
    index_set_ids = serializers.ListField(label=_("联合检索索引集ID列表"), child=serializers.IntegerField(), required=True)

    def validate(self, attrs):
        attrs["index_set_ids"] = sorted(attrs["index_set_ids"])

        return attrs


class GetExportHistorySerializer(serializers.Serializer):
    page = serializers.IntegerField(label=_("页码"))
    pagesize = serializers.IntegerField(label=_("页面大小"))
    show_all = serializers.BooleanField(label=_("是否展示业务全量导出历史"))
    bk_biz_id = serializers.IntegerField(label=_("业务id"))


class UnionSearchGetExportHistorySerializer(serializers.Serializer):
    page = serializers.IntegerField(label=_("页码"))
    pagesize = serializers.IntegerField(label=_("页面大小"))
    show_all = serializers.BooleanField(label=_("是否展示业务全量导出历史"))
    index_set_ids = serializers.CharField(label=_("联合检索索引集ID列表"))
    bk_biz_id = serializers.IntegerField(label=_("业务id"))

    def validate(self, attrs):
        # 索引集ID格式校验
        index_set_ids = attrs["index_set_ids"].split(",")

        for index_set_id in index_set_ids:
            try:
                int(index_set_id)
            except ValueError:
                raise ValidationError(_("索引集ID类型错误"))
        return attrs


class UnionSearchHistorySerializer(serializers.Serializer):
    index_set_ids = serializers.CharField(label=_("联合检索索引集ID列表"))

    def validate(self, attrs):
        # 索引集ID格式校验
        index_set_ids = attrs["index_set_ids"].split(",")

        for index_set_id in index_set_ids:
            try:
                int(index_set_id)
            except ValueError:
                raise ValidationError(_("索引集ID类型错误"))
        return attrs


class SourceDetectSerializer(serializers.Serializer):
    es_host = serializers.CharField(label=_("ES HOST"))
    es_port = serializers.IntegerField(label=_("ES 端口"))
    es_user = serializers.CharField(label=_("ES 用户"), allow_blank=True, required=False)
    es_password = serializers.CharField(label=_("ES 密码"), allow_blank=True, required=False)


class HostIpListSerializer(serializers.Serializer):
    """
    主机ip序列化
    """

    ip = serializers.CharField(label=_("主机IP"), max_length=15)
    bk_cloud_id = serializers.IntegerField(label=_("云区域ID"), required=False)


class HostInstanceByIpListSerializer(serializers.Serializer):
    """
    根据ip列表获取主机实例序列化
    """

    ip_list = HostIpListSerializer(many=True)


class TopoSerializer(serializers.Serializer):
    """
    获取拓扑序列化
    """

    instance_type = serializers.ChoiceField(label=_("实例类型"), choices=InstanceTypeEnum.get_choices(), required=False)
    remove_empty_nodes = serializers.BooleanField(label=_("是否删除空节点"), required=False)


class NodeListParamSerializer(serializers.Serializer):
    """
    节点列表参数序列化
    """

    bk_inst_id = serializers.IntegerField(label=_("实例id"))
    bk_inst_name = serializers.CharField(label=_("实例名称"), max_length=64)
    bk_obj_id = serializers.CharField(label=_("类型id"), max_length=64)
    bk_biz_id = serializers.IntegerField(label=_("业务id"))


class NodeListSerializer(serializers.Serializer):
    """
    节点列表序列化
    """

    node_list = NodeListParamSerializer(many=True)


class CreateFavoriteSerializer(serializers.Serializer):
    """
    创建收藏序列化
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    name = serializers.CharField(label=_("收藏组名"), max_length=256, required=True)
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=False)
    group_id = serializers.IntegerField(label=_("收藏组ID"), required=False)
    visible_type = serializers.ChoiceField(choices=FavoriteVisibleType.get_choices(), required=True)
    search_mode = serializers.ChoiceField(
        label=_("检索模式"), required=False, choices=SearchMode.get_choices(), default=SearchMode.UI.value
    )
    ip_chooser = serializers.DictField(default={}, required=False)
    addition = serializers.ListField(allow_empty=True, required=False, default="")
    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    search_fields = serializers.ListField(required=False, child=serializers.CharField(), default=[])
    is_enable_display_fields = serializers.BooleanField(required=False, default=False)
    display_fields = serializers.ListField(required=False, child=serializers.CharField(), default=[])
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=False, child=serializers.IntegerField(), default=[]
    )
    index_set_type = serializers.ChoiceField(
        label=_("索引集类型"), required=False, choices=IndexSetType.get_choices(), default=IndexSetType.SINGLE.value
    )
    favorite_type = serializers.ChoiceField(
        label=_("收藏类型"), required=False, choices=FavoriteType.get_choices(), default=FavoriteType.SEARCH.value
    )
    chart_params = serializers.JSONField(label=_("图表相关参数"), default=dict, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["is_enable_display_fields"] and not attrs["display_fields"]:
            raise serializers.ValidationError(_("同时显示字段开启时, 显示字段不能为空"))

        if attrs["index_set_type"] == IndexSetType.SINGLE.value and not attrs.get("index_set_id"):
            raise serializers.ValidationError(_("索引集ID不能为空"))
        elif attrs["index_set_type"] == IndexSetType.UNION.value and not attrs.get("index_set_ids"):
            raise serializers.ValidationError(_("索引集ID列表不能为空"))
        elif attrs["index_set_type"] == IndexSetType.UNION.value:
            # 对index_set_ids排序处理  这里主要是为了兼容前端传递索引集列表ID顺序不一致问题 [1,2]  [2,1] ->[1,2]
            attrs["index_set_ids"] = sorted(attrs["index_set_ids"])

        return attrs


class UpdateFavoriteSerializer(serializers.Serializer):
    """
    修改收藏序列化
    """

    name = serializers.CharField(label=_("收藏组名"), max_length=256, required=False)
    group_id = serializers.IntegerField(label=_("收藏组ID"), required=False, default=0)
    visible_type = serializers.ChoiceField(choices=FavoriteVisibleType.get_choices(), required=False)
    search_mode = serializers.ChoiceField(
        label=_("检索模式"), required=False, choices=SearchMode.get_choices(), default=SearchMode.UI.value
    )
    ip_chooser = serializers.DictField(default={}, required=False)
    addition = serializers.ListField(allow_empty=True, required=False, default="")
    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    search_fields = serializers.ListField(required=False, child=serializers.CharField(), default=[])
    is_enable_display_fields = serializers.BooleanField(required=False, default=False)
    display_fields = serializers.ListField(required=False, child=serializers.CharField(), default=[])
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=False)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=False, child=serializers.IntegerField(), default=[]
    )
    index_set_type = serializers.ChoiceField(
        label=_("索引集类型"), required=False, choices=IndexSetType.get_choices(), default=IndexSetType.SINGLE.value
    )


class BatchUpdateFavoriteChildSerializer(UpdateFavoriteSerializer):
    id = serializers.IntegerField(label=_("收藏ID"), required=True)


class BatchUpdateFavoriteSerializer(serializers.Serializer):
    """
    批量修改收藏序列化
    """

    params = serializers.ListField(required=True, child=BatchUpdateFavoriteChildSerializer())


class BatchDeleteFavoriteSerializer(serializers.Serializer):
    """
    批量删除收藏序列化
    """

    id_list = serializers.ListField(required=True, child=serializers.IntegerField())


class FavoriteListSerializer(serializers.Serializer):
    """
    获取收藏
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    order_type = serializers.ChoiceField(
        label=_("排序方式"),
        choices=FavoriteListOrderType.get_choices(),
        required=False,
        default=FavoriteListOrderType.UPDATED_AT_DESC.value,
    )


class CreateFavoriteGroupSerializer(serializers.Serializer):
    """
    创建组名序列化
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    name = serializers.CharField(label=_("收藏组名"), max_length=256)


class UpdateFavoriteGroupSerializer(serializers.Serializer):
    """
    修改组名序列化
    """

    name = serializers.CharField(label=_("收藏组名"), max_length=256)


class UpdateFavoriteGroupOrderSerializer(serializers.Serializer):
    """
    修改组名序列化
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    group_order = serializers.ListField(label=_("收藏组顺序"), child=serializers.IntegerField())


class FavoriteUnionSearchListSerializer(serializers.Serializer):
    """
    联合检索获取收藏组合列表
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)


class CreateFavoriteUnionSearchSerializer(serializers.Serializer):
    """
    联合检索组合收藏创建序列化
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
    name = serializers.CharField(label=_("收藏组合名"), max_length=256)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=True, allow_empty=False, child=serializers.IntegerField()
    )


class UpdateFavoriteUnionSearchSerializer(serializers.Serializer):
    """
    联合检索组合收藏更新序列化
    """

    name = serializers.CharField(label=_("收藏组合名"), max_length=256)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=True, allow_empty=False, child=serializers.IntegerField()
    )


class GetSearchFieldsSerializer(KeywordSerializer):
    """获取检索语句中的字段序列化"""

    pass


class GenerateQueryParam(serializers.Serializer):
    value = serializers.CharField(label=_("替换的值"), required=True)
    pos = serializers.IntegerField(label=_("字段坐标"), required=True)


class GenerateQuerySerializer(KeywordSerializer):
    """
    生成Query中查询字段序列化
    """

    params = serializers.ListField(required=False, default=[], label=_("替换Query请求参数"), child=GenerateQueryParam())


class InspectFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField(label=_("字段名称"), required=False, allow_null=True, allow_blank=True)
    field_type = serializers.CharField(label=_("字段类型"), required=False, allow_null=True, allow_blank=True)
    is_analyzed = serializers.BooleanField(label=_("是否分词"), required=False, default=False)


class InspectSerializer(KeywordSerializer):
    """
    语法检查以及转换序列化
    """

    fields = serializers.ListField(required=False, default=[], label=_("字段列表"), child=InspectFieldSerializer())


class FavoriteGroupListSerializer(serializers.Serializer):
    """
    获取收藏组
    """

    space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)


class BcsWebConsoleSerializer(serializers.Serializer):
    """
    获取bcs容器管理页面url序列化
    """

    cluster_id = serializers.CharField(label=_("集群id"), required=True)
    container_id = serializers.CharField(label=_("容器id"), required=True)


class TemplateTopoSerializer(serializers.Serializer):
    template_type = serializers.ChoiceField(label=_("模版类型"), choices=TemplateType.get_choices())


class TemplateSerializer(serializers.Serializer):
    bk_inst_ids = serializers.CharField(label=_("下载任务ID列表"))
    template_type = serializers.ChoiceField(label=_("模版类型"), choices=TemplateType.get_choices())

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # 数据库中字段名为 task_id
        task_list = attrs["bk_inst_ids"].split(",")
        for task_id in task_list:
            if not re.findall(r"^\d+", task_id):
                raise serializers.ValidationError(_("类型错误,请输入正确的整型数组"))
        return attrs


class DynamicGroupSerializer(serializers.Serializer):
    dynamic_group_id_list = serializers.ListField(label=_("动态分组ID列表"), child=serializers.CharField(label=_("动态分组ID")))


class HostInfoSerializer(serializers.Serializer):
    cloud_id = serializers.IntegerField(help_text=_("云区域 ID"), required=False)
    ip = serializers.IPAddressField(help_text=_("IPv4 协议下的主机IP"), required=False, protocol="ipv4")
    host_id = serializers.IntegerField(help_text=_("主机 ID，优先取 `host_id`，否则取 `ip` + `cloud_id`"), required=False)

    def validate(self, attrs):
        if not ("host_id" in attrs or ("ip" in attrs and "cloud_id" in attrs)):
            raise serializers.ValidationError(_("参数校验失败: 请传入 host_id 或者 cloud_id + ip"))
        return attrs


class GetDisplayNameSerializer(serializers.Serializer):
    """
    获取展示字段名称序列化
    """

    host_list = serializers.ListField(child=HostInfoSerializer(), default=[])


class ESRouterListSerializer(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间ID")
    scenario_id = serializers.CharField(required=False, label="数据源类型")
    page = serializers.IntegerField(label=_("分页"), required=True)
    pagesize = serializers.IntegerField(label=_("分页大小"), required=True)


class QueryFieldBaseSerializer(serializers.Serializer):
    """
    字段分析查询序列化
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"), required=True)
    index_set_ids = serializers.ListField(label=_("索引集列表"), required=True, child=serializers.IntegerField())
    result_table_ids = serializers.ListField(
        label=_("结果表ID列表"), required=False, child=serializers.CharField(), default=list
    )
    agg_field = serializers.CharField(label=_("字段名"), required=False)

    # filter条件，span选择器等
    addition = serializers.ListField(allow_empty=True, required=False, default="")
    host_scopes = serializers.DictField(default={}, required=False)
    ip_chooser = serializers.DictField(default={}, required=False)

    # 时间选择器字段
    start_time = serializers.IntegerField(required=True)
    end_time = serializers.IntegerField(required=True)
    time_range = serializers.CharField(required=False, default=None)

    # 关键字填充条
    keyword = serializers.CharField(allow_null=True, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["result_table_ids"] = []
        result_table_ids = list(
            LogIndexSetData.objects.filter(index_set_id__in=attrs["index_set_ids"]).values_list(
                "result_table_id", flat=True
            )
        )
        if result_table_ids:
            attrs["result_table_ids"] = result_table_ids
        return attrs


class FetchTopkListSerializer(QueryFieldBaseSerializer):
    """
    获取字段topk计数列表序列化
    """

    limit = serializers.IntegerField(label=_("topk限制条数"), required=False, default=5)


class FetchValueListSerializer(QueryFieldBaseSerializer):
    """
    获取字段值列表序列化
    """

    limit = serializers.IntegerField(label=_("字段值限制个数"), required=False, default=10)


class FetchStatisticsInfoSerializer(QueryFieldBaseSerializer):
    """
    获取字段统计信息
    """

    field_type = serializers.ChoiceField(required=True, choices=list(FIELD_TYPE_MAP.keys()))


class FetchStatisticsGraphSerializer(QueryFieldBaseSerializer):
    """
    获取字段统计图表
    """

    field_type = serializers.ChoiceField(required=True, choices=list(FIELD_TYPE_MAP.keys()))
    max = serializers.FloatField(label=_("最大值"), required=False)
    min = serializers.FloatField(label=_("最小值"), required=False)
    threshold = serializers.IntegerField(label=_("去重数量阈值"), required=False, default=10)
    limit = serializers.IntegerField(label=_("top条数"), required=False, default=5)
    distinct_count = serializers.IntegerField(label=_("去重条数"), required=False)


class UserIndexSetCustomConfigSerializer(serializers.Serializer):
    index_set_id = serializers.IntegerField(label=_("索引集ID"), required=False)
    index_set_ids = serializers.ListField(
        label=_("索引集ID列表"), required=False, allow_empty=False, child=serializers.IntegerField()
    )
    index_set_type = serializers.ChoiceField(label=_("索引集类型"), required=True, choices=IndexSetType.get_choices())
    index_set_config = serializers.JSONField(label=_("索引集字段宽度配置"), required=True)

    def validate(self, attrs):
        index_set_id = attrs.get('index_set_id')
        index_set_ids = attrs.get('index_set_ids')
        index_set_type = attrs.get('index_set_type')

        if index_set_type == IndexSetType.SINGLE.value and not index_set_id:
            raise serializers.ValidationError(_("参数校验失败: index_set_id 必须被提供"))
        elif index_set_type == IndexSetType.UNION.value and not index_set_ids:
            raise serializers.ValidationError(_("参数校验失败: index_set_ids 必须被提供"))
        return attrs


class ChartSerializer(serializers.Serializer):
    sql = serializers.CharField(label=_("sql语句"), required=True)
    start_time = serializers.IntegerField(required=True)
    end_time = serializers.IntegerField(required=True)
    query_mode = serializers.ChoiceField(
        label=_("查询模式"), required=False, choices=QueryMode.get_choices(), default=QueryMode.SQL.value
    )


class SearchConditionSerializer(serializers.Serializer):
    field = serializers.CharField(label=_("字段名"), required=True)
    operator = serializers.CharField(label=_("操作符"), required=True)
    value = serializers.ListField(label=_("值"), required=True)


class UISearchSerializer(serializers.Serializer):
    sql = serializers.CharField(label=_("sql"), required=False)
    addition = serializers.ListField(
        required=False,
        default=list,
        child=SearchConditionSerializer(label=_("搜索条件"), required=False),
    )


class QueryStringSerializer(serializers.Serializer):
    addition = serializers.ListField(
        required=True,
        child=SearchConditionSerializer(label=_("搜索条件"), required=True),
    )


class UserCustomConfigSerializer(serializers.Serializer):
    """
    用户自定义配置
    """

    custom_config = serializers.JSONField(label=_("自定义配置"), required=True)


class UserSearchSerializer(serializers.Serializer):
    """
    用户最近查询的索引集
    """

    username = serializers.CharField(label=_("用户名"), required=True)
    space_uid = serializers.CharField(label=_("空间唯一标识"), required=False)
    start_time = DateTimeFieldWithEpoch(label=_("开始时间"), required=False)
    end_time = DateTimeFieldWithEpoch(label=_("结束时间"), required=False)
    limit = serializers.IntegerField(label=_("限制条数"), required=True)


class UserFavoriteSerializer(serializers.Serializer):
    """
    用户收藏的索引集
    """

    username = serializers.CharField(label=_("用户名"), required=True)
    space_uid = serializers.CharField(label=_("空间唯一标识"), required=False)
    limit = serializers.IntegerField(label=_("限制条数"), required=False)


class StorageUsageSerializer(serializers.Serializer):
    """
    索引集存储量
    """

    bk_biz_id = serializers.IntegerField(label=_("业务ID"), required=True)
    index_set_ids = serializers.ListField(label=_("索引集列表"), required=True, child=serializers.IntegerField())
