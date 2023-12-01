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

import copy
import datetime
import logging
from collections import defaultdict

from django.apps import apps
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.action.serializers.report import (
    FrequencySerializer,
    ReceiverSerializer,
    ReportChannelSerializer,
    ReportContentSerializer,
    StaffSerializer,
)
from bkmonitor.models import (
    ChannelEnum,
    EmailSubscription,
    Strategy,
    SubscriptionSendRecord,
)
from bkmonitor.models.base import ReportContents, ReportItems
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request
from constants.report import GroupId, StaffChoice
from core.drf_resource import CacheResource, api, resource
from core.drf_resource.base import Resource
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger(__name__)
GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")


class GetSubscriptionListResource(Resource):
    """
    获取订阅列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务id"), required=True)
        search_key = serializers.CharField(required=False, label="搜索关键字")
        query_type = serializers.CharField(required=False, label="查询类型", default="all")
        create_type = serializers.CharField(required=False, label="创建类型", default="manager")
        conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="查询条件")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        page_size = serializers.IntegerField(required=False, default=10, label="每页数量")
        order = serializers.CharField(required=False, label="排序", default=None)

    @staticmethod
    def get_request_user():
        return get_request().user

    def filter_by_user(self, qs, request_user):
        target_groups = []
        groups_data = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        username = request_user.username
        is_superuser = request_user.is_superuser
        if is_superuser:
            return qs
            # 找到用户所属的组别
        for group, usernames in groups_data.items():
            if username in usernames:
                target_groups.append(group)

        # 针对用户所有所属组别生成Q
        total_Q_query = Q()
        Q_receivers_list = [
            Q(receivers__contains=[{"id": group, "type": StaffChoice.group}]) for group in target_groups
        ]

        Q_managers_list = [Q(managers__contains=[{"id": group, "type": StaffChoice.group}]) for group in target_groups]

        Q_user_list = [
            Q(receivers__contains=[{"id": username, "type": StaffChoice.user, "is_enabled": True}]),
            Q(managers__contains=[{"id": username, "type": StaffChoice.user}]),
        ]

        for Q_item in Q_receivers_list + Q_managers_list + Q_user_list:
            total_Q_query |= Q_item

        # 筛选出对应的items
        return qs.filter(total_Q_query)

    def filter_by_conditions(self, qs, conditions):
        field_mapping = {
            "send_mode": "send_mode",
            "send_status": "send_status",
            "scenario": "scenario",
            "is_self_subscribed": "is_self_subscribed",
        }

        filter_dict = defaultdict(list)
        for condition in conditions:
            key = condition["key"].lower()
            key = field_mapping.get(key, key)
            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            filter_dict[key].extend(value)

        # 对条件进行判定
        return qs

    def perform_request(self, validated_request_data):
        subscription_qs = EmailSubscription.objects.filter(validated_request_data["bk_biz_id"]).order_by(
            validated_request_data.get("order", "-update_time")
        )

        if validated_request_data["create_type"] == "self":
            # 根据当前用户过滤
            request_user = self.get_request_user()
            subscription_qs = self.filter_by_user(subscription_qs, request_user)
        else:
            # 根据订阅创建人类型过滤：管理员创建/用户创建
            is_manager_created = True if validated_request_data["query_type"] == "manager" else False
            subscription_qs = subscription_qs.filter(is_manager_created=is_manager_created)

        # 根据过滤条件过滤
        if validated_request_data["conditions"]:
            subscription_qs = self.filter_by_conditions(subscription_qs, validated_request_data["conditions"])

        # 分页
        if validated_request_data.get("page") and validated_request_data.get("page_size"):
            subscription_qs = subscription_qs[
                (validated_request_data["page"] - 1)
                * validated_request_data["page_size"] : validated_request_data["page"]
                * validated_request_data["page_size"]
            ]

        subscription_qs = list(subscription_qs.values())
        # 补充用户最后一次发送时间
        # 取最近1000条发送状态数据
        user_last_send_time = defaultdict(dict)
        for record in (
            SubscriptionSendRecord.objects.filter(channel_name=ChannelEnum.USER).order_by("-send_time").values()[:1000]
        ):
            for receiver in record["send_result"]["receivers"]:
                if receiver not in user_last_send_time[record["subscription_id"]]:
                    user_last_send_time[record["subscription_id"]][receiver] = record["send_time"]

        for subscription in subscription_qs:
            for receiver in subscription["receivers"]:
                if user_last_send_time.get(subscription["id"], {}).get(receiver["id"]):
                    receiver["last_send_time"] = user_last_send_time[subscription["id"]].get(receiver["id"])
            subscription["channels"] = subscription["channels"] or []

        return subscription_qs


class GetSubscriptionResource(Resource):
    """
    获取订阅
    """

    class RequestSerializer(serializers.Serializer):
        subscription_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        # username = get_request().user.username

        subscription = EmailSubscription.objects.get(id=validated_request_data["subscription_id"])

        return model_to_dict(subscription)


class ReportCloneResource(Resource):
    """
    订阅报表克隆接口
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        report_item = ReportItems.objects.filter(id=validated_request_data["report_item_id"]).values()
        if not report_item:
            raise CustomException(f"[mail_report] item id: {validated_request_data['report_item_id']} not exists.")
        report_item = report_item[0]
        new_mail_title = f'{report_item["mail_title"]}_copy'

        # 判断重名
        i = 1
        while ReportItems.objects.filter(mail_title=new_mail_title):
            new_mail_title = f"{new_mail_title}({i})"  # noqa
            i += 1

        report_item.pop("id")
        report_item["mail_title"] = new_mail_title
        report_content_to_create = []
        report_contents = list(
            ReportContents.objects.filter(report_item=validated_request_data["report_item_id"]).values()
        )

        with transaction.atomic():
            created_item = ReportItems.objects.create(**report_item)
            for content in report_contents:
                content.pop("id")
                content["report_item"] = created_item.id
                report_content_to_create.append(ReportContents(**content))
            ReportContents.objects.bulk_create(report_content_to_create)
        return True


class ReportCreateOrUpdateResource(Resource):
    """
    创建/编辑订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=False)
        mail_title = serializers.CharField(required=False, max_length=512)
        receivers = ReceiverSerializer(many=True, required=False)
        channels = ReportChannelSerializer(many=True, required=False)
        managers = StaffSerializer(many=True, required=False)
        frequency = FrequencySerializer(required=False)
        report_contents = ReportContentSerializer(many=True, required=False)
        is_enabled = serializers.BooleanField(required=False)
        # 是否发送链接，敏感原因，默认关闭
        is_link_enabled = serializers.BooleanField(required=False, default=True)

    def fetch_group_members(self, staff_list, staff_type):
        """
        获取组别内的所有人员，并充填回去
        :param staff_list: 人员列表
        :param staff_type: 人员类型, 可选：[manager, receiver]
        :return: 充填完组内人员的列表
        """
        group_list = {group_data["id"]: group_data["children"] for group_data in resource.report.group_list()}
        exists_groups = [staff["id"] for staff in staff_list if staff["type"] == StaffChoice.group]

        # 如果是已去除的组别里的人员，删除掉此数据
        staff_list = [staff for staff in staff_list if not staff.get("group") or staff["group"] in exists_groups]

        staff_list_members = [staff["id"] for staff in staff_list if staff["type"] == StaffChoice.user]
        new_staff_list = staff_list
        for staff in staff_list:
            # 只有组类型的数据才需要填充人员
            if not staff.get("type"):
                continue
            members = group_list.get(staff["id"], [])
            for member in members:
                if member in staff_list_members:
                    # 已存在相关用户记录，跳过
                    continue
                data = {"id": member, "name": member, "group": staff["id"], "type": StaffChoice.user}
                if staff_type == "receiver":
                    data["is_enabled"] = True
                new_staff_list.append(data)
        return new_staff_list

    def perform_request(self, validated_request_data):
        current_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if validated_request_data.get("report_item_id"):
            # 编辑则提取订阅项
            report_item = ReportItems.objects.filter(id=validated_request_data["report_item_id"])
            if not report_item:
                raise CustomException(_("此订阅不存在"))

            # 更新参数
            update_args = copy.deepcopy(validated_request_data)

            # 如果更改了接收者和管理者
            if validated_request_data.get("receivers"):
                receivers = self.fetch_group_members(validated_request_data["receivers"], "receiver")
                # 补充用户被添加进来的时间
                for receiver in receivers:
                    if "create_time" not in receiver:
                        receiver["create_time"] = current_time
                update_args["receivers"] = receivers

            if validated_request_data.get("managers"):
                update_args["managers"] = self.fetch_group_members(validated_request_data["managers"], "manager")

            update_args.pop("report_item_id")
            if validated_request_data.get("report_contents"):
                update_args.pop("report_contents")

            update_args["last_send_time"] = None
            report_item.update(**update_args)
            report_item = report_item.first()
        else:
            # 创建
            report_item = ReportItems()
            create_info = {"create_time": current_time, "last_send_time": ""}
            # 人员信息补充
            receivers = self.fetch_group_members(validated_request_data["receivers"], "receiver")
            for receiver in receivers:
                receiver.update(create_info)
            for channel in validated_request_data["channels"]:
                for subscribe in channel["subscribers"]:
                    subscribe.update(create_info)
            report_item.mail_title = validated_request_data["mail_title"]
            report_item.receivers = receivers
            report_item.managers = self.fetch_group_members(validated_request_data["managers"], "manager")
            report_item.frequency = validated_request_data["frequency"]
            report_item.channels = validated_request_data["channels"]
            if validated_request_data.get("is_enabled") is not None:
                report_item.is_enabled = validated_request_data["is_enabled"]
            report_item.is_link_enabled = validated_request_data["is_link_enabled"]
            report_item.save()
        with transaction.atomic():
            # 如果需要修改子内容
            if validated_request_data.get("report_contents"):
                ReportContents.objects.filter(report_item=report_item.id).delete()
                report_contents = []
                for content in validated_request_data["report_contents"]:
                    report_contents.append(
                        ReportContents(
                            report_item=report_item.id,
                            content_title=content["content_title"],
                            content_details=content["content_details"],
                            row_pictures_num=content["row_pictures_num"],
                            graphs=content["graphs"],
                        )
                    )
                ReportContents.objects.bulk_create(report_contents)
        return "success"


class ReportDeleteResource(Resource):
    """
    删除订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        report_item_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            ReportItems.objects.filter(id=validated_request_data["report_item_id"]).delete()
            ReportContents.objects.filter(report_item=validated_request_data["report_item_id"]).delete()
            return "success"
        except Exception as e:
            logger.error(e)
            raise CustomException(e)


class ReportTestResource(Resource):
    """
    测试订阅报表
    """

    class RequestSerializer(serializers.Serializer):
        mail_title = serializers.CharField(required=True, max_length=512)
        receivers = ReceiverSerializer(many=True)
        channels = ReportChannelSerializer(many=True, required=False)
        report_contents = ReportContentSerializer(many=True)
        frequency = FrequencySerializer(required=False)
        is_link_enabled = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data):
        validated_request_data["creator"] = str(get_request().user)
        return api.monitor.test_report_mail(**validated_request_data)


class GroupListResource(CacheResource):
    """
    订阅报表用户组列表接口
    """

    # 缓存类型
    cache_type = CacheType.BIZ

    def format_data(self, group_type, children):
        """
        格式化数据
        :param group_type: 组类型
        :param children: 组下的人员
        :return: 格式化后的数据
        """
        notify_groups = resource.cc.get_notify_roles()
        notify_groups[GroupId.bk_biz_controller] = _("配置管理人员")
        notify_groups[GroupId.bk_biz_notify_receiver] = _("告警接收人员")
        if "admin" in children:
            children.remove("admin")
        if "system" in children:
            children.remove("system")

        return {
            "id": group_type,
            "display_name": notify_groups[group_type],
            "logo": "",
            "type": "group",
            "children": list(filter(None, set(children))),
        }

    def fetch_strategy_bizs(self):
        """
        通过策略配置开关获取已接入的业务列表
        :return: biz_list: 已接入的业务列表
        """
        return list(set(Strategy.origin_objects.filter(is_enabled=True).values_list("bk_biz_id", flat=True)))

    def perform_request(self, validated_request_data):
        all_business = api.cmdb.get_business(bk_biz_ids=self.fetch_strategy_bizs())
        maintainers = []
        productors = []
        developers = []
        testers = []

        for biz in all_business:
            maintainers.extend(biz.bk_biz_maintainer)
            productors.extend(biz.bk_biz_productor)
            developers.extend(biz.bk_biz_developer)
            testers.extend(biz.bk_biz_tester)

        # 配置人员列表、告警接收人员列表
        setting_notify_group_data = api.monitor.get_setting_and_notify_group()

        result = [
            self.format_data(GroupId.bk_biz_maintainer, maintainers),
            self.format_data(GroupId.bk_biz_productor, productors),
            self.format_data(GroupId.bk_biz_tester, testers),
            self.format_data(GroupId.bk_biz_developer, developers),
            self.format_data(GroupId.bk_biz_controller, setting_notify_group_data["controller_group"]["users"]),
            self.format_data(GroupId.bk_biz_notify_receiver, setting_notify_group_data["alert_group"]["users"]),
        ]

        return result
