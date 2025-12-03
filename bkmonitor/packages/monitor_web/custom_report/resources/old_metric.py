"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

import arrow
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.custom_report import CustomValidationLabelError
from monitor_web.custom_report.serializers import CustomTSGroupingRuleSerializer
from monitor_web.models.custom_report import CustomTSGroupingRule, CustomTSTable

logger = logging.getLogger(__name__)


class ModifyCustomTimeSeriesDesc(Resource):
    """
    修改自定义时序描述信息
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        desc = serializers.CharField(max_length=1024, default="", label="描述信息")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = CustomTSTable
            fields = "__all__"

    @atomic()
    def perform_request(self, validated_request_data):
        time_series_obj = CustomTSTable.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        ).first()
        if not time_series_obj:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        time_series_obj.desc = validated_request_data["desc"]
        time_series_obj.save()
        return time_series_obj


class GetCustomTimeSeriesLatestDataByFields(Resource):
    """
    查询自定义时序数据最新的一条数据
    """

    class RequestSerializer(serializers.Serializer):
        class MetricSerializer(serializers.Serializer):
            scope_name = serializers.CharField(label=_("分组名称"), allow_blank=True, default="")
            name = serializers.CharField(label=_("指标名称"))

        result_table_id = serializers.CharField(required=True, label="结果表ID")
        fields_list = serializers.ListField(label="字段列表", default=[])

        def validate(self, attrs):
            fields_list = []
            for _field in attrs.get("fields_list", []):
                if isinstance(_field, str):
                    fields_list.append(_field)
                else:
                    s = self.MetricSerializer(data=_field)
                    s.is_valid(raise_exception=True)
                    fields_list.append(s.validated_data["name"])
            attrs["metrics"] = fields_list
            return super().validate(attrs)

    def perform_request(self, validated_request_data):
        # TODO: 修改响应格式
        result_table_id = validated_request_data["result_table_id"]
        fields_list = validated_request_data["fields_list"] or []
        fields_list = [str(i) for i in fields_list]

        result = {}
        field_values, latest_time = self.get_latest_data(table_id=result_table_id, fields_list=fields_list)
        result["fields_value"] = field_values
        result["last_time"] = latest_time
        result["table_id"] = result_table_id
        return result

    @classmethod
    def get_latest_data(cls, table_id, fields_list):
        if not fields_list:
            return {}, None

        now_timestamp = int(time.time())
        data = api.unify_query.query_data_by_table(
            table_id=table_id,
            keys=fields_list,
            start_time=now_timestamp - 300,
            end_time=now_timestamp,
            limit=1,
            slimit=0,
        )

        result = {}
        latest_time = ""

        if data["series"]:
            for row in data["series"]:
                for point in row["values"]:
                    for key, value in zip(row["columns"], point):
                        if key == "time" or key in result or value is None:
                            continue

                        if key in ["value", "metric_value"] and row["metric_name"]:
                            result[row["metric_name"]] = value
                            continue

                        result[key] = value

                for key, value in zip(row["group_keys"], row["group_values"]):
                    if key in result or value is None:
                        continue
                    result[key] = value

                if row["values"]:
                    time_value = row["values"][-1][0]
                    if latest_time < time_value:
                        latest_time = time_value

        if latest_time:
            latest_time = arrow.get(latest_time).timestamp
        else:
            latest_time = None
        return result, latest_time


class ModifyCustomTsGroupingRuleList(Resource):
    """
    修改全量自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        group_list = serializers.ListField(label="分组列表", child=CustomTSGroupingRuleSerializer(), default=[])

    def perform_request(self, validated_request_data):
        # 校验分组名称唯一
        group_names = {}
        for group in validated_request_data["group_list"]:
            if group_names.get(group["name"]):
                raise CustomValidationLabelError(msg=_("自定义指标分组名{}不可重复").format(group["name"]))
            group_names[group["name"]] = group

        # 清除残余分组记录
        grouping_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
        grouping_rules.exclude(name__in=list(group_names.keys())).delete()

        # 更新已存在的分组
        for grouping_rule in grouping_rules:
            should_save = False
            new_grouping_rule = group_names.pop(grouping_rule.name, {})
            if grouping_rule.manual_list != new_grouping_rule.get("manual_list", []):
                grouping_rule.manual_list = new_grouping_rule.get("manual_list", [])
                should_save = True
            if grouping_rule.auto_rules != new_grouping_rule.get("auto_rules", []):
                grouping_rule.auto_rules = new_grouping_rule.get("auto_rules", [])
                should_save = True

            if should_save:
                grouping_rule.save()
        # 创建不存在的分组
        CustomTSGroupingRule.objects.bulk_create(
            [
                CustomTSGroupingRule(time_series_group_id=validated_request_data["time_series_group_id"], **grouping)
                for _, grouping in group_names.items()
            ],
            batch_size=200,
        )
        return resource.custom_report.group_custom_ts_item(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        )


class GroupCustomTSItem(Resource):
    """
    分组匹配自定义时序指标
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, validated_request_data):
        table = CustomTSTable.objects.get(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        )
        if not table:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        # 分组匹配现存指标
        groups = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )

        table.renew_metric_labels(groups, delete=False, clean=True)

        return resource.custom_report.custom_ts_grouping_rule_list(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
