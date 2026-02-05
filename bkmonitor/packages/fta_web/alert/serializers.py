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
from typing import Any

from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.utils.request import get_request
from core.drf_resource import resource
from fta_web.models.alert import AlertFeedback, AlertSuggestion, SearchFavorite


class BaseSearchSerializer(serializers.Serializer):
    """
    搜索请求基础序列化器。

    提供业务 ID 和空间 UID 的通用字段定义及转换逻辑。
    """

    bk_biz_ids = serializers.ListField(label="业务ID", default=None, allow_null=True, child=serializers.IntegerField())
    space_uids = serializers.ListField(
        label="空间UID列表", default=None, allow_null=True, required=False, child=serializers.CharField()
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        验证并处理请求数据。

        如果提供了 space_uids，将其转换为 bk_biz_ids 并与已有的 bk_biz_ids 合并。

        :param attrs: 已验证的属性字典
        :return: 填充了 bk_biz_ids 的处理后属性
        """
        space_uids: list[str] | None = attrs.pop("space_uids", None)
        if not space_uids:
            return super().validate(attrs)

        # 将 space_uids 转换为 bk_biz_ids
        converted_biz_ids: list[int] = [
            bk_biz_id for space_uid in space_uids if (bk_biz_id := space_uid_to_bk_biz_id(space_uid)) != 0
        ]

        # 合并去重 bk_biz_ids
        attrs["bk_biz_ids"] = list(set(converted_biz_ids + (attrs.get("bk_biz_ids") or [])))

        return super().validate(attrs)


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


class AlertSearchSerializer(BaseSearchSerializer):
    status = serializers.ListField(label="状态", required=False, child=serializers.CharField())
    conditions = SearchConditionSerializer(label="搜索条件", many=True, default=[])
    query_string = serializers.CharField(label="查询字符串", default="", allow_blank=True)
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    username = serializers.CharField(required=False, label="负责人")


class ActionSearchSerializer(BaseSearchSerializer):
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
