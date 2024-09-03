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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apps.log_clustering.constants import (
    AGGS_FIELD_PREFIX,
    DEFULT_FILTER_NOT_CLUSTERING_OPERATOR,
    OwnerConfigEnum,
    PatternEnum,
    RemarkConfigEnum,
    StrategiesAlarmLevelEnum,
    StrategiesType,
)
from apps.utils.drf import DateTimeFieldWithEpoch


class PatternSearchSerlaizer(serializers.Serializer):
    host_scopes = serializers.DictField(default={}, required=False)
    addition = serializers.ListField(allow_empty=True, required=False, default=[])
    start_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    end_time = DateTimeFieldWithEpoch(required=False, format="%Y-%m-%d %H:%M:%S")
    time_range = serializers.CharField(required=False, default="customized")
    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    size = serializers.IntegerField(required=False, default=10000)
    pattern_level = serializers.CharField(default=PatternEnum.LEVEL_05)
    show_new_pattern = serializers.BooleanField(required=True)
    year_on_year_hour = serializers.IntegerField(required=False, default=0, min_value=0)
    group_by = serializers.ListField(required=False, default=[])
    filter_not_clustering = serializers.BooleanField(required=False, default=True)

    remark_config = serializers.ChoiceField(choices=RemarkConfigEnum.get_choices(), default=RemarkConfigEnum.ALL.value)
    owner_config = serializers.ChoiceField(choices=OwnerConfigEnum.get_choices(), default=OwnerConfigEnum.ALL.value)
    owners = serializers.ListField(child=serializers.CharField(), required=False, default=[])

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["filter_not_clustering"]:
            attrs["addition"].append(
                {
                    "field": "{}_{}".format(AGGS_FIELD_PREFIX, attrs["pattern_level"]),
                    "operator": DEFULT_FILTER_NOT_CLUSTERING_OPERATOR,
                    "value": "",
                }
            )
        return attrs


class FilerRuleSerializer(serializers.Serializer):
    fields_name = serializers.CharField(required=False)
    op = serializers.CharField(required=False)
    value = serializers.CharField(required=False)
    logic_operator = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ClusteringConfigSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField()
    clustering_fields = serializers.CharField()
    filter_rules = serializers.ListField(child=FilerRuleSerializer(), required=False)
    min_members = serializers.IntegerField(required=False)
    predefined_varibles = serializers.CharField(required=False, allow_blank=True)
    delimeter = serializers.CharField(required=False, allow_blank=True)
    max_log_length = serializers.IntegerField(required=False)
    is_case_sensitive = serializers.IntegerField(required=False)
    new_cls_strategy_enable = serializers.BooleanField(default=False)
    normal_strategy_enable = serializers.BooleanField(default=False)


class ClusteringDebugSerializer(serializers.Serializer):
    input_data = serializers.CharField()
    predefined_varibles = serializers.CharField()


class SetRemarkSerializer(serializers.Serializer):
    signature = serializers.CharField()
    remark = serializers.CharField()
    origin_pattern = serializers.CharField(allow_blank=True, allow_null=True)
    groups = serializers.DictField(default=dict)


class UpdateRemarkSerializer(serializers.Serializer):
    signature = serializers.CharField()
    old_remark = serializers.CharField()
    new_remark = serializers.CharField()
    create_time = serializers.IntegerField()
    origin_pattern = serializers.CharField(allow_blank=True, allow_null=True)
    groups = serializers.DictField(default=dict)


class DeleteRemarkSerializer(serializers.Serializer):
    signature = serializers.CharField()
    remark = serializers.CharField()
    create_time = serializers.IntegerField()
    origin_pattern = serializers.CharField(allow_blank=True, allow_null=True)
    groups = serializers.DictField(default=dict)


class SetOwnerSerializer(serializers.Serializer):
    signature = serializers.CharField()
    owners = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    origin_pattern = serializers.CharField(allow_blank=True, allow_null=True)
    groups = serializers.DictField(default=dict)


class UpdateGroupFieldsSerializer(serializers.Serializer):
    group_fields = serializers.ListField(child=serializers.CharField(), allow_empty=True, default=list)


class UserGroupsSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), label=_("用户组ID"), required=False, default=[])


class StrategySerializer(serializers.Serializer):
    level = serializers.ChoiceField(label=_("告警级别"), choices=StrategiesAlarmLevelEnum.get_choices())
    user_groups = serializers.ListField(child=serializers.IntegerField(), label=_("告警组"))


class NewClsStrategySerializer(StrategySerializer):
    interval = serializers.IntegerField(label=_("告警间隔"))
    threshold = serializers.IntegerField(label=_("告警阈值"))


class StrategyTypeSerializer(serializers.Serializer):
    strategy_type = serializers.ChoiceField(
        label=_("告警策略"), choices=[StrategiesType.NEW_CLS_strategy, StrategiesType.NORMAL_STRATEGY]
    )


class NormalStrategySerializer(StrategySerializer):
    sensitivity = serializers.IntegerField(label=_("敏感度"))


class SubscriberSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField(required=False)
    is_enabled = serializers.BooleanField()


class ChannelSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    subscribers = SubscriberSerializer(many=True)
    channel_name = serializers.CharField()
    send_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ScenarioConfigSerializer(serializers.Serializer):
    # Clustering
    index_set_id = serializers.IntegerField()
    is_show_new_pattern = serializers.BooleanField()
    pattern_level = serializers.CharField()
    log_display_count = serializers.IntegerField()
    year_on_year_change = serializers.CharField()
    year_on_year_hour = serializers.IntegerField()
    generate_attachment = serializers.BooleanField()


class FrequencySerializer(serializers.Serializer):
    type = serializers.IntegerField(required=True, label="频率类型")
    day_list = serializers.ListField(required=False, label="几天")
    week_list = serializers.ListField(required=False, label="周几")
    hour = serializers.FloatField(required=False, label="小时频率")
    run_time = serializers.CharField(required=False, label="运行时间", allow_blank=True)

    class DataRangeSerializer(serializers.Serializer):
        time_level = serializers.CharField(required=True, label="数据范围时间等级")
        number = serializers.IntegerField(required=True, label="数据范围时间")

    data_range = DataRangeSerializer(required=False)


class ContentConfigSerializer(serializers.Serializer):
    title = serializers.CharField()
    is_link_enabled = serializers.BooleanField()


class CreateOrUpdateReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=True)
    bk_biz_id = serializers.IntegerField(required=True)
    scenario = serializers.CharField(label="订阅场景", required=True)
    subscriber_type = serializers.CharField(label="订阅人类型", required=True)
    channels = ChannelSerializer(many=True, required=True)
    frequency = FrequencySerializer(required=True)
    content_config = ContentConfigSerializer(required=True)
    scenario_config = ScenarioConfigSerializer(required=True)
    start_time = serializers.IntegerField(label="开始时间", required=False, default=None, allow_null=True)
    end_time = serializers.IntegerField(label="结束时间", required=False, default=None, allow_null=True)
    is_manager_created = serializers.BooleanField(required=False, default=False)
    is_enabled = serializers.BooleanField(required=False, default=True)


class GetExistReportsSerlaizer(serializers.Serializer):
    scenario = serializers.CharField(label="订阅场景", required=True)
    query_type = serializers.CharField(required=False, label="查询类型")
    bk_biz_id = serializers.IntegerField(required=True)
    index_set_id = serializers.IntegerField(required=True)


class GetReportVariablesSerlaizer(serializers.Serializer):
    scenario = serializers.CharField(label="订阅场景", required=True)


class SendReportSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    bk_biz_id = serializers.IntegerField(required=False)
    scenario = serializers.CharField(label="订阅场景", required=False)
    channels = ChannelSerializer(many=True, required=False)
    frequency = FrequencySerializer(required=False)
    content_config = ContentConfigSerializer(required=False)
    scenario_config = ScenarioConfigSerializer(required=False)
    start_time = serializers.IntegerField(label="开始时间", required=False, default=None, allow_null=True)
    end_time = serializers.IntegerField(label="结束时间", required=False, default=None, allow_null=True)
    is_manager_created = serializers.BooleanField(required=False, default=False)
    is_enabled = serializers.BooleanField(required=False, default=True)
