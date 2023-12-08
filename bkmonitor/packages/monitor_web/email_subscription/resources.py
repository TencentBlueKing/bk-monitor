# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from collections import defaultdict
from datetime import datetime

import arrow
from django.apps import apps
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.email_subscription.serializers import (
    ChannelSerializer,
    ContentConfigSerializer,
    FrequencySerializer,
    ScenarioConfigSerializer,
)
from bkmonitor.models import (
    EmailSubscription,
    SubscriptionApplyRecord,
    SubscriptionChannel,
    SubscriptionSendRecord,
)
from bkmonitor.utils.request import get_request
from constants.email_subscription import ChannelEnum, SendModeEnum, SendStatusEnum
from constants.report import StaffChoice
from core.drf_resource import resource
from core.drf_resource.base import Resource
from core.drf_resource.exceptions import CustomException
from packages.monitor_web.email_subscription.constants import SUBSCRIPTION_VARIABLES_MAP

logger = logging.getLogger(__name__)
GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")


def get_send_status(send_records):
    if not send_records:
        return SendStatusEnum.NO_STATUS.value
    for record in send_records:
        if record["send_status"] != SendStatusEnum.SUCCESS.value:
            return SendStatusEnum.FAILED.value
    return SendStatusEnum.SUCCESS.value


def get_send_mode(frequency):
    if frequency["type"] != 1:
        return SendModeEnum.PERIODIC.value
    return SendModeEnum.ONE_TIME.value


class GetSubscriptionListResource(Resource):
    """
    获取订阅列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务id"), required=True)
        search_key = serializers.CharField(required=False, label="搜索关键字", default="", allow_null=True, allow_blank=True)
        query_type = serializers.CharField(required=False, label="查询类型", default="all")
        create_type = serializers.CharField(required=False, label="创建类型", default="manager")
        conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="查询条件")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        page_size = serializers.IntegerField(required=False, default=10, label="每页数量")
        order = serializers.CharField(required=False, label="排序", default="", allow_null=True, allow_blank=True)

    @staticmethod
    def get_request_username():
        return get_request().user.username

    @staticmethod
    def filter_by_search_key(qs, search_key):
        origin_subscription_ids = set(qs.values_list("id", flat=1))
        # 搜索订阅名称
        filter_subscription_ids = set(qs.filter(name__contains=search_key).values_list("id", flat=1))
        # 搜索订阅人
        filter_subscription_ids |= set(
            SubscriptionChannel.objects.filter(
                subscribers__contains={"id": search_key}, subscription_id__in=origin_subscription_ids
            ).values_list("subscription_id", flat=1)
        )

        return qs.filter(id__in=filter_subscription_ids)

    def filter_by_query_type(self, qs, query_type):
        filter_subscription_ids = set()
        subscription_ids = set(qs.values_list("id", flat=1))
        username = self.get_request_username()
        # 已失效订阅列表
        if query_type == "is_invalid":
            for subscription in qs:
                if subscription.is_invalid():
                    filter_subscription_ids.add(subscription.id)
        # 已取消订阅列表
        elif query_type == "is_cancelled":
            filter_subscription_ids = set(
                SubscriptionChannel.objects.filter(
                    subscribers__contains=[{"id": username, "type": StaffChoice.user, "is_enabled": False}],
                    subscription_id__in=subscription_ids,
                ).values_list("subscription_id", flat=1)
            )
        else:
            filter_subscription_ids = subscription_ids

        return qs.filter(id__in=filter_subscription_ids)

    def filter_by_user(self, subscription_qs):
        target_groups = []
        groups_data = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        username = self.get_request_username()
        # 找到用户所属的组别
        for group, usernames in groups_data.items():
            if username in usernames:
                target_groups.append(group)

        # 针对用户所有所属组别生成Q
        total_Q_query = Q()
        Q_receivers_list = [
            Q(subscribers__contains=[{"id": group, "type": StaffChoice.group}]) for group in target_groups
        ]

        Q_user_list = [
            Q(subscribers__contains={"id": username}),
        ]

        for Q_item in Q_receivers_list + Q_user_list:
            total_Q_query |= Q_item

        # 筛选出对应的items
        subscription_ids = list(subscription_qs.values_list("id", flat=1))
        filter_subscription_ids = list(
            SubscriptionChannel.objects.filter(total_Q_query & Q(subscription_id__in=subscription_ids)).values_list(
                "subscription_id", flat=1
            )
        )
        return subscription_qs.filter(id__in=filter_subscription_ids)

    def get_filter_dict_by_conditions(self, conditions: list) -> (dict, dict):
        db_fields = ["send_mode", "scenario"]
        db_filter_dict = defaultdict(list)
        external_filter_dict = defaultdict(list)
        for condition in conditions:
            key = condition["key"].lower()
            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            if key in db_fields:
                query_key = f"{key}__in"
                db_filter_dict[query_key] = value
            else:
                external_filter_dict[key] = value
        return db_filter_dict, external_filter_dict

    def sort_subscriptions(self, subscriptions, order):
        reverse_order = False
        if order.startswith('-'):
            reverse_order = True
            order = order[1:]  # 去掉负号

        sorted_subscriptions = sorted(subscriptions, key=lambda x: x[order] or datetime.min, reverse=reverse_order)
        return sorted_subscriptions

    def fill_external_info(self, subscriptions, external_filter_dict, subscription_channels_map, last_send_record_map):
        new_subscriptions = []
        current_user = self.get_request_username()
        for subscription in subscriptions:
            subscription["channels"] = subscription_channels_map.get(subscription["id"], [])
            subscription["is_self_subscribed"] = True if subscription["create_user"] == current_user else False
            record_info = last_send_record_map[subscription["id"]]
            if record_info:
                subscription["last_send_time"] = record_info["send_time"]
                subscription["send_status"] = get_send_status(record_info["records"])
            else:
                subscription["last_send_time"] = None
                subscription["send_status"] = SendStatusEnum.NO_STATUS.value

            # 过滤conditions中额外字段
            need_filter = False
            for key, value in external_filter_dict.items():
                if not subscription[key] in value:
                    need_filter = True
                    break
            if not need_filter:
                new_subscriptions.append(subscription)

        return new_subscriptions

    def perform_request(self, validated_request_data):
        subscription_qs = EmailSubscription.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        # 根据角色过滤
        if validated_request_data["create_type"] == "self":
            # 当前用户的订阅
            subscription_qs = self.filter_by_user(subscription_qs)
        else:
            # 管理员创建/用户创建的订阅
            is_manager_created = True if validated_request_data["create_type"] == "manager" else False
            subscription_qs = subscription_qs.filter(is_manager_created=is_manager_created)

        # 根据搜索关键字过滤
        if validated_request_data["search_key"]:
            subscription_qs = self.filter_by_search_key(subscription_qs, validated_request_data["search_key"])

        if validated_request_data["query_type"]:
            subscription_qs = self.filter_by_query_type(subscription_qs, validated_request_data["query_type"])

        # 获取订阅最后一次发送记录
        last_send_record_map = defaultdict(lambda: {"send_time": None, "records": []})
        total_Q = Q()
        Q_list = [
            Q(id=subscription_info["id"], send_round=subscription_info["send_round"])
            for subscription_info in list(subscription_qs.values("id", "send_round"))
        ]
        for Q_item in Q_list:
            total_Q |= Q_item
        for record in SubscriptionSendRecord.objects.filter(total_Q).order_by("-send_time").values():
            last_send_record_map[record["subscription_id"]]["records"].append(record)

        db_filter_dict, external_filter_dict = self.get_filter_dict_by_conditions(validated_request_data["conditions"])

        if db_filter_dict:
            subscription_qs = subscription_qs.filter(Q(**db_filter_dict))

        subscriptions = list(subscription_qs.values())
        subscription_ids = list(subscription_qs.values_list("id", flat=1))

        # 获取订阅渠道列表
        subscription_channels_map = defaultdict(list)
        for channel in list(SubscriptionChannel.objects.filter(subscription_id__in=subscription_ids).values()):
            channel.pop("id")
            subscription_id = channel.pop("subscription_id")
            subscription_channels_map[subscription_id].append(channel)

        # 补充订阅信息
        subscriptions = self.fill_external_info(
            subscriptions, external_filter_dict, subscription_channels_map, last_send_record_map
        )

        # 分页
        if validated_request_data.get("page") and validated_request_data.get("page_size"):
            subscriptions = subscriptions[
                (validated_request_data["page"] - 1)
                * validated_request_data["page_size"] : validated_request_data["page"]
                * validated_request_data["page_size"]
            ]

        # 根据排序字段进行排序
        if validated_request_data["order"]:
            subscriptions = self.sort_subscriptions(subscriptions, validated_request_data["order"])

        return subscriptions


class GetSubscriptionResource(Resource):
    """
    获取订阅
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        subscription = EmailSubscription.objects.values().get(id=validated_request_data["subscription_id"])
        subscription["channels"] = list(
            SubscriptionChannel.objects.filter(subscription_id=subscription["id"]).values(
                "channel_name", "is_enabled", "subscribers", "send_text"
            )
        )
        subscription["is_self_subscribed"] = get_request().user.username == subscription["create_user"]
        return subscription


class CloneSubscriptionResource(Resource):
    """
    订阅报表克隆接口
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        subscription_qs = EmailSubscription.objects.filter(id=validated_request_data["subscription_id"])
        if not subscription_qs.exists():
            raise CustomException(
                f"[email_subscription] subscription id: {validated_request_data['subscription_id']} not exists."
            )
        subscription = subscription_qs.values()[0]
        new_name = f'{subscription["name"]}_clone'

        i = 1
        while EmailSubscription.objects.filter(name=new_name):
            new_name = f"{subscription['name']}_clone({i})"  # noqa
            i += 1

        subscription.pop("id")
        subscription["name"] = new_name
        subscription_channels = list(
            SubscriptionChannel.objects.filter(subscription_id=validated_request_data["subscription_id"]).values()
        )
        subscription_channels_to_create = []
        with transaction.atomic():
            new_subscription_obj = EmailSubscription.objects.create(**subscription)
            for channel in subscription_channels:
                channel.pop("id")
                channel["subscription_id"] = new_subscription_obj.id
                subscription_channels_to_create.append(SubscriptionChannel(**channel))
            SubscriptionChannel.objects.bulk_create(subscription_channels_to_create)
        return new_subscription_obj.id


class CreateOrUpdateSubscriptionResource(Resource):
    """
    创建/编辑订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        scenario = serializers.CharField(label="订阅场景", required=True)
        subscriber_type = serializers.CharField(label="订阅人类型", required=True)
        channels = ChannelSerializer(many=True, required=True)
        frequency = FrequencySerializer(required=True)
        content_config = ContentConfigSerializer(required=True)
        scenario_config = ScenarioConfigSerializer(required=True)
        start_time = serializers.IntegerField(label="开始时间", required=False, default=None)
        end_time = serializers.IntegerField(label="结束时间", required=False, default=None)
        is_manager_created = serializers.BooleanField(required=False, default=False)
        is_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        subscription_channels = validated_request_data.pop("channels", [])
        validated_request_data["send_mode"] = get_send_mode(validated_request_data["frequency"])
        frequency = validated_request_data["frequency"]
        if frequency["type"] == 1:
            validated_request_data["start_time"] = arrow.now().timestamp
            validated_request_data["end_time"] = arrow.get(frequency["run_time"]).timestamp
        if validated_request_data.get("id"):
            # 编辑
            try:
                subscription = EmailSubscription.objects.get(id=validated_request_data["id"])
            except EmailSubscription.DoesNotExist:
                raise Exception("subscription_id: %s not found", validated_request_data["id"])
            subscription.__dict__.update(validated_request_data)
            subscription.save()
        else:
            # 创建
            subscription = EmailSubscription(**validated_request_data)
            subscription.save()
        with transaction.atomic():
            # 更新订阅渠道
            SubscriptionChannel.objects.filter(subscription_id=subscription.id).delete()
            subscription_channels_to_create = []
            for channel in subscription_channels:
                channel["subscription_id"] = subscription.id
                subscription_channels_to_create.append(SubscriptionChannel(**channel))
            SubscriptionChannel.objects.bulk_create(subscription_channels_to_create)
        return subscription.id


class DeleteSubscriptionResource(Resource):
    """
    删除订阅
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            EmailSubscription.objects.filter(id=validated_request_data["subscription_id"]).delete()
            SubscriptionChannel.objects.filter(subscription_id=validated_request_data["subscription_id"]).delete()
            return "success"
        except Exception as e:
            logger.exception(e)
            raise CustomException(e)


class SendSubscriptionResource(Resource):
    """
    发送订阅：测试发送/重新发送
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        scenario = serializers.CharField(label="订阅场景", required=False)
        channels = ChannelSerializer(many=True, required=False)
        frequency = FrequencySerializer(required=False)
        content_config = ContentConfigSerializer(required=False)
        scenario_config = ScenarioConfigSerializer(required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False, default=None)
        end_time = serializers.IntegerField(label="结束时间", required=False, default=None)
        is_manager_created = serializers.BooleanField(required=False, default=False)
        is_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        # result = api.monitor.send_subscription(**validated_request_data)
        return "success"


class CancelSubscriptionResource(Resource):
    """
    取消订阅
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        username = get_request().user.username
        try:
            channel = SubscriptionChannel.objects.get(
                subscription_id=validated_request_data["subscription_id"], channel_name=ChannelEnum.USER.value
            )
        except SubscriptionChannel.DoesNotExist:
            raise CustomException(
                f"[email_subscription] subscription id: "
                f"{validated_request_data['subscription_id']} user channel not exists."
            )

        for subscriber in channel.subscribers:
            if subscriber["id"] == username and subscriber["type"] == "user":
                subscriber["is_enabled"] = False
                channel.save()
                return "success"
        channel.subscribers.append({"id": username, "type": StaffChoice.user, "is_enabled": False})
        channel.save()
        return "success"


class GetSendRecordsResource(Resource):
    """
    获取订阅发送记录
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        return list(
            SubscriptionSendRecord.objects.filter(subscription_id=validated_request_data["subscription_id"]).values()
        )


class GetApplyRecordsResource(Resource):
    """
    根据用户获取订阅申请记录
    """

    def perform_request(self, validated_request_data):
        username = get_request().user.username
        return list(SubscriptionApplyRecord.objects.filter(create_user=username).values())


class GetVariablesResource(Resource):
    """
    根据订阅场景获取标题变量列表
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.CharField(label="订阅场景", required=True)

    def perform_request(self, validated_request_data):
        return SUBSCRIPTION_VARIABLES_MAP[validated_request_data["scenario"]]


class GetExistSubscriptionsResource(Resource):
    """
    根据条件获取已存在的订阅
    """

    class RequestSerializer(serializers.Serializer):
        scenario = serializers.CharField(label="订阅场景", required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        # CLUSTERING ONLY
        index_set_id = serializers.IntegerField(required=False)

    def perform_request(self, validated_request_data):
        qs = list(
            EmailSubscription.objects.filter(
                bk_biz_id=validated_request_data["bk_biz_id"], scenario=validated_request_data["scenario"]
            ).values()
        )

        exist_subscription_list = []
        for subscription in qs:
            if validated_request_data["index_set_id"]:
                if subscription["scenario_config"].get("index_set_id", None) == validated_request_data["index_set_id"]:
                    exist_subscription_list.append(subscription)

        return exist_subscription_list
