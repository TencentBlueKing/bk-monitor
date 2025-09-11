"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.utils.request import get_request
from core.drf_resource import resource
from fta_web.models.alert import AlertFeedback, AlertSuggestion, SearchFavorite


class SearchFavoriteSerializer(serializers.ModelSerializer):
    params = serializers.JSONField()

    class Meta:
        model = SearchFavorite
        fields = ["id", "name", "search_type", "params", "create_user", "create_time", "update_user", "update_time"]


class SearchConditionSerializer(serializers.Serializer):
    key = serializers.CharField(label="匹配字段")
    value = serializers.ListField(label="匹配值")
    method = serializers.ChoiceField(
        label="匹配方法", choices=["eq", "neq", "include", "exclude", "gt", "gte", "lt", "lte"], default="eq"
    )
    condition = serializers.ChoiceField(label="复合条件", choices=["and", "or", ""], default="")


class AlertIDField(serializers.CharField):
    def run_validation(self, *args, **kwargs):
        value = super().run_validation(*args, **kwargs)
        try:
            AlertDocument.parse_timestamp_by_id(value)
        except Exception:
            raise ValidationError(_("'{id}' 不是合法的告警ID").format(id=value))
        return value


class ActionIDField(serializers.CharField):
    def run_validation(self, *args, **kwargs):
        value = super().run_validation(*args, **kwargs)
        try:
            ActionInstanceDocument.parse_timestamp_by_id(value)
        except Exception:
            raise ValidationError(_("'{id}' 不是合法的处理记录ID").format(id=value))
        return value


class AllowedBizIdsField(serializers.ListField):
    child = serializers.IntegerField()

    def __init__(self, iam_action, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iam_action = iam_action

    def run_validation(self, *args, **kwargs):
        value = super().run_validation(*args, **kwargs)
        req = get_request(peaceful=True)
        if not req:
            # 如果上下文没有请求对象，可能是shell调试状态，就不做校验了
            return value
        return resource.space.get_bk_biz_ids_by_user(req.user)


class AlertSearchSerializer(serializers.Serializer):
    bk_biz_ids = serializers.ListField(label="业务ID", default=None, allow_null=True, child=serializers.IntegerField())
    status = serializers.ListField(label="状态", required=False, child=serializers.CharField())
    conditions = SearchConditionSerializer(label="搜索条件", many=True, default=[])
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    username = serializers.CharField(required=False, label="负责人")


class ActionSearchSerializer(serializers.Serializer):
    bk_biz_ids = serializers.ListField(label="业务ID", default=None, allow_null=True)
    alert_ids = serializers.ListField(label="告警ID", required=False, child=AlertIDField())
    status = serializers.ListField(label="状态", required=False, child=serializers.CharField())
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)
    conditions = SearchConditionSerializer(label="搜索条件", many=True, default=[])
    username = serializers.CharField(required=False, label="负责人")


class EventSearchSerializer(serializers.Serializer):
    alert_id = AlertIDField(label="告警ID")
    ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)


class AlertSuggestionSerializer(serializers.ModelSerializer):
    metric = serializers.JSONField()
    conditions = serializers.JSONField()

    class Meta:
        model = AlertSuggestion
        exclude = ["is_enabled", "is_deleted"]


class AlertFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertFeedback
        exclude = ["is_enabled", "is_deleted"]
