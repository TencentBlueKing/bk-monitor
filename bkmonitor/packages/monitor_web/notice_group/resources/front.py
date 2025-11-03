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

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

from bkmonitor.models import Action, ActionNoticeMapping, StrategyModel
from bkmonitor.utils.request import get_request
from bkmonitor.views import serializers
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.errors.notice_group import NoticeGroupNotExist

logger = logging.getLogger(__name__)


class GetReceiverResource(Resource):
    """
    获取平台全部的通知对象
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务Id")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id", 0)
        # 获取user_list
        if not bk_biz_id:
            business = None
        else:
            business = resource.cc.get_app_by_id(bk_biz_id)

        # 获取角色组列表
        group_msg = resource.cc.get_notify_roles()

        all_members = set()
        for key, value in list(group_msg.items()):
            members = getattr(business, key, []) if business else []
            all_members.update(members)

        futures = []
        user_list = []
        if all_members:
            step_size = 50
            all_members_list = sorted(all_members)
            with ThreadPoolExecutor(max_workers=10) as executor:
                for num in range(0, len(all_members_list), step_size):
                    futures.append(
                        executor.submit(
                            api.bk_login.get_all_user,
                            page_size=500,
                            fields="username,display_name",
                            exact_lookups=",".join(all_members_list[num : num + step_size]),
                        )
                    )
            for future in as_completed(futures):
                try:
                    user_list.extend(future.result()["results"])
                except Exception as e:
                    logger.warning(f"[GetReceiverResource] Failed to get user info: {e}")
                    continue

        display_name = {user["username"]: user["display_name"] for user in user_list}

        group_list = []
        for key, value in list(group_msg.items()):
            members = getattr(business, key, []) if business else []
            group_list.append(
                {
                    "id": key,
                    "display_name": value,
                    "logo": "",
                    "type": "group",
                    "members": [{"id": member, "display_name": display_name.get(member, member)} for member in members],
                }
            )

        return [
            {"id": "group", "display_name": _("用户组"), "children": group_list},
            {"id": "user", "display_name": _("用户"), "children": []},
        ]


class GetNoticeWayResource(Resource):
    """
    获取平台全部的通知方式
    """

    class RequestSerializer(serializers.Serializer):
        show_all = serializers.BooleanField(label="是否展示全部", default=False)

    def perform_request(self, validated_request_data):
        data = api.cmsi.get_msg_type()
        if not validated_request_data["show_all"]:
            data = [way for way in data if way["type"] in settings.ENABLED_NOTICE_WAYS]
        return data


class NoticeGroupDetailResource(Resource):
    """
    获取通知组详情
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="通知組ID")

    @staticmethod
    def get_users_info(usernames: list) -> dict[str, dict]:
        """
        补充通知对象信息
        """
        user_info_dict = {}
        try:
            for user in api.bk_login.get_all_user(
                fields="username,display_name,logo", exact_lookups=",".join(sorted(usernames))
            )["results"]:
                user_info_dict[user["username"]] = user
        except Exception as e:
            logger.error(e)
        return user_info_dict

    def perform_request(self, params):
        instance = resource.notice_group.backend_search_notice_group(ids=[params["id"]])
        if not instance:
            raise NoticeGroupNotExist({"msg": _("获取详情失败")})
        else:
            instance = instance[0]

        usernames = [receiver["id"] for receiver in instance["notice_receiver"] if receiver["type"] == "user"]
        users_info = self.get_users_info(usernames)
        notify_roles = resource.cc.get_notify_roles()
        for receiver in instance["notice_receiver"]:
            if receiver["type"] == "user" and receiver["id"] in users_info:
                receiver["display_name"] = users_info[receiver["id"]]["display_name"]
                receiver["logo"] = users_info[receiver["id"]]["logo"] or ""
            elif receiver["type"] == "group" and receiver["id"] in notify_roles:
                receiver["display_name"] = notify_roles[receiver["id"]]
                receiver["logo"] = ""
            else:
                receiver["display_name"] = receiver["id"]

        return {
            "id": instance["id"],
            "bk_biz_id": instance["bk_biz_id"],
            "name": instance["name"],
            "message": instance["message"],
            "notice_receiver": instance["notice_receiver"],
            "notice_way": instance["notice_way"] or {},
            "webhook_url": instance["webhook_url"],
            "wxwork_group": instance["wxwork_group"],
            "create_user": instance["create_user"],
            "update_user": instance["update_user"],
            "create_time": instance["create_time"],
            "update_time": instance["update_time"],
        }


class NoticeGroupListResource(NoticeGroupDetailResource):
    """
    获取通知组列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id")

        if bk_biz_id:
            bk_biz_ids = [0, bk_biz_id]
        else:
            bk_biz_ids: list[int] = resource.space.get_bk_biz_ids_by_user(get_request().user)

        notice_groups = resource.notice_group.backend_search_notice_group(bk_biz_ids=bk_biz_ids)
        strategy_ids = StrategyModel.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("id", flat=True)
        action_ids = Action.objects.filter(strategy_id__in=strategy_ids).values_list("id", flat=True)
        # 统计关联的告警策略数量
        strategy_counts = (
            ActionNoticeMapping.objects.filter(
                notice_group_id__in=[notice_group["id"] for notice_group in notice_groups],
                action_id__in=action_ids,
            )
            .values("notice_group_id")
            .annotate(count=models.Count("action_id", distinct=True))
        )

        strategy_count_dict = {
            strategy_count["notice_group_id"]: strategy_count["count"] for strategy_count in strategy_counts
        }

        usernames = set()
        for notice_group in notice_groups:
            for receiver in notice_group["notice_receiver"]:
                if receiver["type"] == "user":
                    usernames.add(receiver["id"])
        users_info = self.get_users_info(list(usernames))
        notify_roles = resource.cc.get_notify_roles()
        for notice_group in notice_groups:
            for receiver in notice_group["notice_receiver"]:
                if receiver["type"] == "user" and receiver["id"] in users_info:
                    receiver["display_name"] = users_info[receiver["id"]]["display_name"]
                    receiver["logo"] = users_info[receiver["id"]]["logo"] or ""
                elif receiver["type"] == "group" and receiver["id"] in notify_roles:
                    receiver["display_name"] = notify_roles[receiver["id"]]
                    receiver["logo"] = ""
                else:
                    receiver["display_name"] = receiver["id"]

        return [
            {
                "id": notice_group["id"],
                "name": notice_group["name"],
                "bk_biz_id": notice_group["bk_biz_id"],
                "related_strategy": strategy_count_dict.get(notice_group["id"], 0),
                "message": notice_group["message"],
                "notice_receiver": notice_group["notice_receiver"],
                "delete_allowed": strategy_count_dict.get(notice_group["id"], 0) == 0,
                "edit_allowed": True,
            }
            for notice_group in notice_groups
        ]


class NoticeGroupConfigResource(Resource):
    """
    创建、修改通知组
    """

    def perform_request(self, params):
        return resource.notice_group.backend_save_notice_group(**params)


class DeleteNoticeGroupResource(Resource):
    """
    删除通知组
    """

    class RequestSerializer(serializers.Serializer):
        id_list = serializers.ListField(required=True, label="通知组ID")

    def perform_request(self, params):
        return resource.notice_group.backend_delete_notice_group(ids=params["id_list"])
