"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from rest_framework.fields import empty

from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.utils.request import get_request_tenant_id
from constants.result_table import RT_TABLE_NAME_WORD_EXACT
from core.unit import UNITS

PATTERN = re.compile(r"^[_a-zA-Z][a-zA-Z0-9_]*$")


class StrictCharField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.update({"trim_whitespace": False})
        super().__init__(**kwargs)


class MetricJsonSerializer(serializers.Serializer):
    class FieldsSerializer(serializers.Serializer):
        description = StrictCharField(required=True, allow_blank=True, label="字段描述")
        type = serializers.ChoiceField(required=True, choices=["string", "double", "int"], label="字段类型")
        monitor_type = serializers.ChoiceField(required=True, choices=["dimension", "metric"], label="指标类型")
        unit = StrictCharField(required=False, allow_blank=True, label="单位")
        name = serializers.CharField(required=True, label="字段名")
        conversion = StrictCharField(required=False, label="换算单位")
        is_diff_metric = serializers.BooleanField(default=False, label="是否为差值指标")
        is_active = serializers.BooleanField(default=True, label="是否启用")
        source_name = serializers.CharField(default="", allow_blank=True, label="原指标名")
        dimensions = serializers.ListField(required=False, label="聚合维度", allow_empty=True)
        is_manual = serializers.BooleanField(required=False, default=True, label="是否手动添加")

        def validate_unit(self, value):
            if value not in self.support_unit:
                return "none"
            return value

        @cached_property
        def support_unit(self):
            units = []
            for units_value in UNITS.values():
                for value in units_value.values():
                    units.append(value.gid)
            return units

    table_name = serializers.RegexField(required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", label="表名")
    table_desc = StrictCharField(required=True, label="表描述")
    fields = FieldsSerializer(required=True, many=True, label="指标项")
    rule_list = serializers.ListField(required=False, label="自动分组校验规则")


class MetricJsonBaseSerializer(serializers.Serializer):
    metric_json = serializers.ListField(label="指标配置", default=[], child=MetricJsonSerializer())

    def validate_metric_json(self, value):
        if not value:
            return value

        metric_name_list = []
        table_name_list = []

        new_value = []
        for value_detail in value:
            # 允许默认分组为空
            if not value_detail.get("fields", "") and value_detail.get("table_name", "") == "group_default":
                table_name_list.append(value_detail["table_name"])
                new_value.append(value_detail)
                continue

            # 如果分组为空，则跳过
            if not value_detail.get("fields"):
                continue

            new_value.append(value_detail)

            dimension_name_list = []
            for field_detail in value_detail["fields"]:
                if field_detail["monitor_type"] == "metric":
                    metric_name_list.append(field_detail["name"])
                if field_detail["monitor_type"] == "dimension":
                    dimension_name_list.append(field_detail["name"])
                if value_detail.get("rule_list") and not field_detail.get("is_manual"):
                    is_match = False
                    for i in value_detail["rule_list"]:
                        pattern = re.compile(i)
                        res = pattern.match(field_detail["name"])
                        if res:
                            is_match = True
                            break
                    if not is_match:
                        raise serializers.ValidationError(_("名称不符合分组规则:{}".format(field_detail["name"])))

            # 维度去重
            dimension_dict = dict().fromkeys(dimension_name_list, True)
            value_detail["fields"] = list(
                filter(
                    lambda x: dimension_dict.pop(x["name"], False) or x["monitor_type"] != "dimension",
                    value_detail["fields"],
                )
            )

            intersection = set(metric_name_list) & set(dimension_name_list)
            if intersection:
                raise serializers.ValidationError(_("指标和维度不允许重名,重名内容:{}".format(intersection)))

            if value_detail["table_name"].upper() in RT_TABLE_NAME_WORD_EXACT:
                raise serializers.ValidationError(_("表名不允许与保留关键字重名"))

            table_name_list.append(value_detail["table_name"])

        if len(metric_name_list) != len(set(metric_name_list)):
            raise serializers.ValidationError(_("指标维度中指标名不允许重名"))
        if len(table_name_list) != len(set(table_name_list)):
            raise serializers.ValidationError(_("指标维度中表名不允许重名"))

        return new_value


class StringSplitListField(serializers.ListField):
    """
    字符串列表类型
    允许两种格式：
    1. 纯列表: ["A", "B", "C"]
    2. 字符串: "A,B,C"
    """

    def __init__(self, sep, *args, **kwargs):
        self.sep = sep
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        result = data.split(self.sep) if isinstance(data, str) else data
        return super().to_internal_value([item for item in result if item])


class BkBizIdSerializer(serializers.Serializer):
    space_uid = serializers.CharField(required=False, label="空间UID")
    bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    def validate(self, attrs):
        # bk_biz_id与space_uid至少需要存在一个
        if not attrs.get("bk_biz_id") and not attrs.get("space_uid"):
            raise serializers.ValidationError(_("bk_biz_id or space_uid must be provided"))

        # 如果没有bk_biz_id就根据space_uid获取bk_biz_id
        if not attrs.get("bk_biz_id"):
            attrs["bk_biz_id"] = space_uid_to_bk_biz_id(attrs["space_uid"])

        if not attrs["bk_biz_id"]:
            raise serializers.ValidationError(_("space_uid is invalid"))
        return attrs


class TenantIdField(serializers.CharField):
    """
    租户ID字段
    如果传入的值为空，则使用当前请求的租户ID
    """

    def __init__(self, *args, prefer_request_tenant=True, **kwargs):
        kwargs["required"] = False

        super().__init__(*args, **kwargs)
        self._allow_blank = kwargs.get("allow_blank", False)
        self.allow_blank = True
        self.prefer_request_tenant = prefer_request_tenant

    def run_validation(self, data=empty):
        # 如果传入的值为空，则使用当前请求的租户ID
        if self.prefer_request_tenant or not data or data is empty:
            request_tenant_id = get_request_tenant_id(peaceful=True)
            if request_tenant_id:
                data = request_tenant_id

        # 如果租户ID为空，则抛出异常
        if (not data or data is empty) and not self._allow_blank:
            raise ValidationError(_("tenant_id is required"))

        return super().run_validation(data)


class TenantSerializer(serializers.Serializer):
    """
    租户序列化器
    当需要使用租户ID时，可以通过该序列化器获取租户ID
    1. 如果传入bk_tenant_id，则直接返回
    2. 如果存在 request，则通过 request 获取租户ID
    3. 如果传入bk_biz_id/space_uid，则通过业务ID/空间UID获取租户ID
    """

    bk_tenant_id = TenantIdField(label="租户ID", allow_blank=True)

    def validate(self, attrs):
        # 如果租户ID不为空，则直接返回
        if attrs.get("bk_tenant_id"):
            return attrs

        # 如果没有租户ID，则通过业务/空间获取租户ID
        if not attrs.get("bk_biz_id") and not attrs.get("space_uid"):
            raise ValidationError(_("bk_tenant_id or bk_biz_id must be provided"))

        # 通过业务ID获取租户ID
        space: Space | None = SpaceApi.get_space_detail(
            bk_biz_id=attrs.get("bk_biz_id") or 0, space_uid=attrs.get("space_uid") or ""
        )
        if not space:
            raise ValidationError("cannot find space by bk_biz_id: {}".format(attrs["bk_biz_id"]))
        attrs["bk_tenant_id"] = space.bk_tenant_id

        return attrs
