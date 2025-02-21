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
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers import (
    DutyRuleDetailSlz,
    DutyRuleSlz,
    UserGroupDetailSlz,
    UserGroupSlz,
)
from bkmonitor.models import (
    ActionConfig,
    DutyArrange,
    DutyRule,
    StrategyActionConfigRelation,
    UserGroup,
)
from bkmonitor.strategy.serializers import NoticeGroupSerializer
from constants.action import ActionSignal, NoticeWay, NotifyStep
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.notice_group import NoticeGroupHasStrategy


class SearchNoticeGroupResource(Resource):
    """
    查询通知组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(required=True, label="业务ID"), required=False)
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="告警组ID"), required=False)

    def perform_request(self, params):
        user_groups = UserGroup.objects.all().order_by("-update_time")

        if params.get("bk_biz_ids"):
            user_groups = user_groups.filter(bk_biz_id__in=params.get("bk_biz_ids"))

        if params.get("ids"):
            user_groups = user_groups.filter(id__in=params.get("ids"))

        user_group_ids = []
        webhook_action_ids = {}

        for user_group in user_groups:
            user_group_ids.append(user_group.id)

            if user_group.webhook_action_id:
                webhook_action_ids[user_group.webhook_action_id] = user_group.id

        users_by_group = {}

        for arrange in DutyArrange.objects.filter(user_group_id__in=user_group_ids):
            users_by_group[arrange.user_group_id] = arrange.users

        webhook_by_group = {}

        for action in ActionConfig.objects.filter(id__in=webhook_action_ids):
            if action.plugin_id != "2":
                continue
            webhook_url = action.execute_config.get("template_detail", {}).get("url", "")
            if webhook_url:
                webhook_by_group[webhook_action_ids[action.id]] = webhook_url

        result = []
        for user_group in user_groups:
            notice_way = {}
            wxwork_group = {}

            if user_group.alert_notice:
                for conf in user_group.alert_notice[0]["notify_config"]:
                    if not conf.get("type"):
                        # 如果当前配置里面没有老数据结构，表示是新数据结构
                        conf["type"] = []
                        for new_notice_way in conf.get("notice_ways", []):
                            notice_way_name = new_notice_way.pop("name", "")
                            conf["type"].append(notice_way_name)
                            if notice_way_name == NoticeWay.WX_BOT:
                                wxwork_group[str(conf["level"])] = ",".join(new_notice_way.pop("receivers", []))
                    else:
                        # 老数据结构，保持不变
                        if "wxwork-bot" in conf["type"]:
                            wxwork_group[str(conf["level"])] = conf.get("chatid", "")
                    notice_way[str(conf["level"])] = conf["type"]

            result.append(
                {
                    "id": user_group.id,
                    "name": user_group.name,
                    "notice_way": notice_way,
                    "notice_receiver": users_by_group.get(user_group.id, []),
                    "webhook_url": webhook_by_group.get(user_group.id, ""),
                    "webhook_action_id": user_group.webhook_action_id,
                    "wxwork_group": wxwork_group,
                    "message": user_group.desc,
                    "create_time": user_group.create_time,
                    "update_time": user_group.update_time,
                    "update_user": user_group.update_user,
                    "bk_biz_id": user_group.bk_biz_id,
                    "create_user": user_group.create_user,
                }
            )
        return result


class SaveNoticeGroupResource(Resource):
    """
    保存通知组
    """

    RequestSerializer = NoticeGroupSerializer

    def validate_request_data(self, request_data):
        # 对象不存在
        if request_data.get("id"):
            group = SearchNoticeGroupResource()(ids=[request_data["id"]])
            if not group:
                raise ValidationError(_("通知组不存在"))
            group = group[0]
            group.update(request_data)
            serializer = self.RequestSerializer(data=group)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data

        # 重名检测
        instance = (
            UserGroup.objects.filter(name=request_data["name"], bk_biz_id=request_data["bk_biz_id"])
            .exclude(id=request_data.get("id"))
            .first()
        )
        if instance:
            raise ValidationError(_("通知组名称已存在"))

        return super(SaveNoticeGroupResource, self).validate_request_data(request_data)

    def perform_request(self, validated_request_data):
        if validated_request_data.get("id"):
            user_group_id = validated_request_data["id"]
            user_group = UserGroup.objects.get(id=user_group_id, bk_biz_id=validated_request_data["bk_biz_id"])
        else:
            user_group = UserGroup()

        notice_ways = [
            {"level": int(level), "type": notice_type}
            for level, notice_type in validated_request_data["notice_way"].items()
        ]

        wxwork_group = validated_request_data.get("wxwork_group", {})

        for level_notice_way in notice_ways:
            if str(level_notice_way["level"]) in wxwork_group:
                level_notice_way["type"].append("wxwork-bot")
                level_notice_way["chatid"] = wxwork_group[str(level_notice_way["level"])]

        user_group.name = validated_request_data["name"]
        user_group.bk_biz_id = validated_request_data["bk_biz_id"]
        user_group.desc = validated_request_data.get("message", "")
        user_group.alert_notice = [
            {
                "time_range": "00:00:00--23:59:59",
                "notify_config": notice_ways,
            }
        ]

        if not user_group.action_notice:
            user_group.action_notice = [
                {
                    "time_range": "00:00:00--23:59:59",
                    "notify_config": [
                        {
                            "phase": phase,
                            "type": [NoticeWay.MAIL],
                        }
                        for phase in [NotifyStep.BEGIN, NotifyStep.SUCCESS, NotifyStep.FAILURE]
                    ],
                }
            ]

        if validated_request_data.get("webhook_url") or user_group.webhook_action_id:
            # 如果带了webhook链接，或者当前存在处理套餐ID， 则创建或更新对应的处理套餐信息
            action_config = None
            if user_group.webhook_action_id:
                action_config = ActionConfig.objects.filter(id=user_group.webhook_action_id, plugin_id="2").first()

            if not action_config:
                action_config = ActionConfig(
                    **{
                        "name": "[webhook] {}".format(user_group.name),
                        "plugin_id": 2,
                        "bk_biz_id": user_group.bk_biz_id,
                        "execute_config": {
                            "template_detail": {
                                "method": "POST",
                                "url": validated_request_data["webhook_url"],
                                "headers": [],
                                "authorize": {"auth_type": "none", "auth_config": {}},
                                "body": {
                                    "data_type": "raw",
                                    "params": [],
                                    "content": "{{alarm.callback_message}}",
                                    "content_type": "json",
                                },
                                "query_params": [],
                                "need_poll": True,
                                "notify_interval": 2 * 60 * 60,  # 默认2小时回调一次
                                "failed_retry": {
                                    "is_enabled": True,
                                    "max_retry_times": 3,
                                    "retry_interval": 3,
                                    "timeout": 3,
                                },
                            },
                            "timeout": 600,
                        },
                    }
                )

            action_config.name = "[webhook] {}".format(user_group.name)
            action_config.execute_config["template_detail"]["url"] = validated_request_data["webhook_url"]
            action_config.save()

            user_group.webhook_action_id = action_config.id

        user_group.save()

        duty_arrange = DutyArrange.objects.filter(user_group_id=user_group.id).first()

        if not duty_arrange:
            duty_arrange = DutyArrange(user_group_id=user_group.id)

        duty_arrange.users = validated_request_data["notice_receiver"]
        duty_arrange.save()

        # 如果传入了webhook_url，则需要去校验是否已经创建了对应的relation
        if validated_request_data.get("webhook_url"):
            notice_relations = StrategyActionConfigRelation.objects.filter(
                user_groups__contains=user_group.id, relate_type=StrategyActionConfigRelation.RelateType.NOTICE
            ).values("strategy_id", "user_groups")
            action_relations = set(
                StrategyActionConfigRelation.objects.filter(
                    relate_type=StrategyActionConfigRelation.RelateType.ACTION, config_id=user_group.webhook_action_id
                ).values_list("strategy_id", flat=True)
            )
            need_add_notice_relations = [
                relation for relation in notice_relations if relation["strategy_id"] not in action_relations
            ]

            need_add_action_relation_list = []
            # 2. 循环所有的relations，将对应的策略ID和用户组放到需要添加的action_relation
            for relation in need_add_notice_relations:
                need_add_action_relation_list.append(
                    StrategyActionConfigRelation(
                        strategy_id=relation["strategy_id"],
                        config_id=user_group.webhook_action_id,
                        user_groups=relation["user_groups"],
                        relate_type=StrategyActionConfigRelation.RelateType.ACTION,
                        signal=[
                            ActionSignal.ABNORMAL,
                            ActionSignal.NO_DATA,
                            ActionSignal.RECOVERED,
                            ActionSignal.CLOSED,
                        ],
                        options={
                            "converge_config": {
                                "is_enabled": False,
                            },
                            "exclude_notice_ways": {"recovered": [], "closed": []},
                        },
                    )
                )

            StrategyActionConfigRelation.objects.bulk_create(need_add_action_relation_list)

        return {"id": user_group.id, "webhook_action_id": user_group.webhook_action_id}


class DeleteNoticeGroupResource(Resource):
    """
    删除通知组
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(required=True, label="通知组ID")

    def perform_request(self, validated_request_data):
        ids = validated_request_data["ids"]
        groups = UserGroup.objects.filter(id__in=ids)

        for group in groups:
            if StrategyActionConfigRelation.objects.filter(user_groups__contains=group.id).exists():
                raise NoticeGroupHasStrategy

        groups.delete()


class SearchUserGroupResource(Resource):
    """
    查询通知组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(required=True, label="业务ID"), required=False)
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="告警组ID"), required=False)
        name = serializers.CharField(required=False, label="告警组名称")

    def perform_request(self, params):
        #  T告警组列表的获取

        user_groups = UserGroup.objects.all().order_by("-update_time")

        if params.get("bk_biz_ids"):
            user_groups = user_groups.filter(bk_biz_id__in=params.get("bk_biz_ids"))

        if params.get("ids"):
            user_groups = user_groups.filter(id__in=params.get("ids"))

        if params.get("name"):
            user_groups = user_groups.filter(name__icontains=params["name"])

        return UserGroupSlz(user_groups, many=True).data


class SearchUserGroupDetailResource(Resource):
    """
    查询通知组
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="告警组ID")

    def perform_request(self, params):
        # 告警组列表的获取
        try:
            user_group = UserGroup.objects.get(id=params["id"])
        except UserGroup.DoesNotExist:
            # 如果不存在，直接返回空
            return {}
        return UserGroupDetailSlz(instance=user_group).data


class SaveUserGroupResource(Resource):
    """
    保存通知组, 有ID就新建，没有ID就更新
    """

    class RequestSerializer(UserGroupDetailSlz):
        id = serializers.IntegerField(required=False, label="告警组ID")

    def validate_request_data(self, request_data):
        """
        校验请求数据
        """
        self._request_serializer = None
        user_group = None
        if request_data.get("id"):
            try:
                user_group = UserGroup.objects.get(id=request_data.pop("id"), bk_biz_id=request_data["bk_biz_id"])
            except UserGroup.DoesNotExist:
                raise ValidationError("user group not existed")
        self._request_serializer = self.RequestSerializer(data=request_data, instance=user_group)
        self._request_serializer.is_valid(raise_exception=True)
        return self._request_serializer.validated_data

    def perform_request(self, validated_request_data):
        user_group = self._request_serializer.save()
        return UserGroupDetailSlz(instance=user_group).data


class DeleteUserGroupResource(Resource):
    """
    删除通知组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(required=True, label="业务ID"), required=True)
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="告警组ID"), required=True)

    def perform_request(self, validated_request_data):
        deleted_user_group_queryset = UserGroup.objects.filter(
            id__in=validated_request_data["ids"], bk_biz_id__in=validated_request_data["bk_biz_ids"]
        )
        user_groups = UserGroupSlz(deleted_user_group_queryset, many=True).data
        not_allowed_groups = []
        for group in user_groups:
            if not group["delete_allowed"]:
                # 当查询出来的告警组有关联关系
                not_allowed_groups.append(str(group["id"]))
        if not_allowed_groups:
            # 如果存在不允许删除的告警组，直接返回错误
            raise NoticeGroupHasStrategy(
                "Follow groups(%s) are to not allowed to delete because of "
                "these user groups have been related to some strategies" % ",".join(not_allowed_groups)
            )
        deleted_group_ids = list(deleted_user_group_queryset.values_list("id", flat=True))
        DutyArrange.objects.filter(user_group_id__in=deleted_group_ids).delete()
        deleted_user_group_queryset.delete()

        return {"ids": deleted_group_ids}


class SearchDutyRuleResource(Resource):
    """
    查询通知组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(required=True, label="业务ID"), required=False)
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="规则组ID"), required=False)
        name = serializers.CharField(required=False)

    def perform_request(self, params):
        # 告警规则列表的获取

        duty_rules = DutyRule.objects.all().order_by("-update_time")

        if params.get("bk_biz_ids"):
            duty_rules = duty_rules.filter(bk_biz_id__in=params.get("bk_biz_ids"))

        if params.get("ids"):
            duty_rules = duty_rules.filter(id__in=params.get("ids"))

        if params.get("name"):
            duty_rules = duty_rules.filter(name__icontains=params["name"])

        return DutyRuleSlz(duty_rules, many=True).data


class SearchDutyRuleDetailResource(Resource):
    """
    查询告警规则详细内容
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="轮值规则组ID")

    def perform_request(self, params):
        # 告警组列表的获取
        try:
            duty_rule = DutyRule.objects.get(id=params["id"])
        except DutyRule.DoesNotExist:
            # 如果不存在，直接返回空
            return {}
        return DutyRuleDetailSlz(instance=duty_rule).data


class SaveDutyRuleResource(Resource):
    """
    保存告警规则组, 有ID就新建，没有ID就更新
    """

    class RequestSerializer(DutyRuleDetailSlz):
        id = serializers.IntegerField(required=False, label="规则组ID")

    def validate_request_data(self, request_data):
        """
        校验请求数据
        """
        self._request_serializer = None
        duty_rule = None
        if request_data.get("id"):
            try:
                duty_rule = DutyRule.objects.get(id=request_data.pop("id"), bk_biz_id=request_data["bk_biz_id"])
            except DutyRule.DoesNotExist:
                raise ValidationError("duty rule not existed")
        self._request_serializer = self.RequestSerializer(data=request_data, instance=duty_rule)
        self._request_serializer.is_valid(raise_exception=True)
        return self._request_serializer.validated_data

    def perform_request(self, validated_request_data):
        duty_rule = self._request_serializer.save()
        return DutyRuleDetailSlz(instance=duty_rule).data


class DeleteDutyRuleResource(Resource):
    """
    批量删除轮值规则
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(required=True, label="业务ID"), required=True)
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="规则ID"), required=True)

    def perform_request(self, validated_request_data):
        deleted_duty_rule_queryset = DutyRule.objects.filter(
            id__in=validated_request_data["ids"], bk_biz_id__in=validated_request_data["bk_biz_ids"]
        )
        duty_rules = DutyRuleSlz(deleted_duty_rule_queryset, many=True).data
        not_allowed_rules = []
        for rule in duty_rules:
            if not rule["delete_allowed"]:
                # 当查询出来的告警组有关联关系
                not_allowed_rules.append(str(rule["id"]))
        if not_allowed_rules:
            # 如果存在不允许删除的告警规则组，直接返回错误
            raise NoticeGroupHasStrategy(
                "Follow duty rules(%s) are to not allowed to delete because of "
                "these rules have been related to some user groups" % ",".join(not_allowed_rules)
            )
        deleted_rule_ids = list(deleted_duty_rule_queryset.values_list("id", flat=True))
        DutyArrange.objects.filter(duty_rule_id__in=deleted_rule_ids).delete()
        deleted_duty_rule_queryset.delete()

        return {"ids": deleted_rule_ids}


class NoticeGroupViewSet(ResourceViewSet):
    """
    通知组API
    """

    resource_routes = [
        ResourceRoute("POST", SearchNoticeGroupResource, endpoint="search"),
        ResourceRoute("POST", DeleteNoticeGroupResource, endpoint="delete"),
        ResourceRoute("POST", SaveNoticeGroupResource, endpoint="save"),
    ]


class UserGroupViewSet(ResourceViewSet):
    """
    新版本的通知组API
    """

    resource_routes = [
        ResourceRoute("POST", SearchUserGroupResource, endpoint="search"),
        ResourceRoute("POST", SearchUserGroupDetailResource, endpoint="search_detail"),
        ResourceRoute("POST", DeleteUserGroupResource, endpoint="delete"),
        ResourceRoute("POST", SaveUserGroupResource, endpoint="save"),
        ResourceRoute("POST", resource.user_group.preview_user_group_plan, endpoint="preview"),
    ]


class DutyRuleViewSet(ResourceViewSet):
    """
    轮值规则API
    """

    resource_routes = [
        ResourceRoute("POST", SearchDutyRuleResource, endpoint="search"),
        ResourceRoute("POST", SearchDutyRuleDetailResource, endpoint="search_detail"),
        ResourceRoute("POST", DeleteDutyRuleResource, endpoint="delete"),
        ResourceRoute("POST", SaveDutyRuleResource, endpoint="save"),
        ResourceRoute("POST", resource.user_group.preview_duty_rule_plan, endpoint="preview"),
    ]
