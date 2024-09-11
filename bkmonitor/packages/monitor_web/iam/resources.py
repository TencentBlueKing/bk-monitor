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
from typing import Dict, List
from urllib.parse import urljoin

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from api.itsm.default import TokenVerifyResource
from bk_dataview.permissions import GrafanaRole
from bk_dataview.views import ProxyBaseView
from bkm_space.api import SpaceApi
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.iam.resource import ApmApplication
from bkmonitor.models.external_iam import (
    ExternalPermission,
    ExternalPermissionApplyRecord,
)
from bkmonitor.utils.request import get_request, get_request_username
from bkmonitor.utils.user import get_local_username
from core.drf_resource import Resource, api, resource
from monitor.models import GlobalConfig
from monitor_web.grafana.auth import GrafanaAuthSync
from monitor_web.grafana.permissions import DashboardPermission
from monitor_web.iam.serializers import (
    ExternalPermissionApplyRecordSerializer,
    ExternalPermissionSerializer,
)

logger = logging.getLogger("iam")


class GetAuthorityMetaResource(Resource):
    """
    获取动作列表
    """

    def perform_request(self, validated_request_data):
        return Permission().list_actions()


class CheckAllowedByActionIdsResource(Resource):
    """
    查询是否有权限
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        action_ids = serializers.ListField(required=True, allow_empty=False, label="动作ID列表")
        space_uid = serializers.CharField(required=False, default="", allow_null=True)

        def validate(self, attrs):
            if not attrs.get("space_uid", ""):
                if not attrs["bk_biz_id"]:
                    raise ValueError("bk_biz_id or space_uid not found")
                return attrs
            space = SpaceApi.get_space_detail(attrs["space_uid"])
            attrs["bk_biz_id"] = space.bk_biz_id
            return attrs

    def perform_request(self, validated_request_data):
        client = Permission()
        result = []
        for action_id in validated_request_data["action_ids"]:
            is_allowed = client.is_allowed_by_biz(validated_request_data["bk_biz_id"], action_id, raise_exception=False)
            result.append({"action_id": action_id, "is_allowed": is_allowed})
        return result


class CheckAllowedByApmApplicationResource(Resource):
    """
    查询是否有APM应用的权限
    """

    class RequestSerializer(serializers.Serializer):
        # application_id 和 application_name 两个参数必须要传一个
        application_id = serializers.IntegerField(required=False, label="应用ID")
        application_name = serializers.CharField(required=False, label="应用名称")
        action_ids = serializers.ListField(required=True, allow_empty=False, label="动作ID列表")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        application_id = validated_request_data.get("application_id")
        application_name = validated_request_data.get("application_name")
        if not application_id and not application_name:
            raise ValueError(_("应用ID(application_id)或者应用名称(application_name)不能同时为空"))

        # application_name to application_id
        if not application_id:
            from apm_web.models import Application

            try:
                app = Application.objects.get(bk_biz_id=validated_request_data["bk_biz_id"], app_name=application_name)
                application_id = app.application_id
            except Application.DoesNotExist:
                raise ValueError("Application({}) does not exist".format(application_name))

        apm_resource = Permission.make_resource(resource_type=ApmApplication.id, instance_id=application_id)
        client = Permission()
        result = []
        for action_id in validated_request_data["action_ids"]:
            is_allowed = client.is_allowed(action_id, [apm_resource])
            result.append({"action_id": action_id, "is_allowed": is_allowed})
        return result


class CheckAllowedResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ResourceSerializer(serializers.Serializer):
            type = serializers.CharField(required=True, label="资源类型")
            id = serializers.CharField(required=True, label="资源ID")

        resources = serializers.ListField(required=True, allow_empty=False, label="资源列表", child=ResourceSerializer())
        action_ids = serializers.ListField(required=True, allow_empty=False, label="动作ID列表")
        username = serializers.CharField(required=False, allow_null=True, label="指定用户名")

    def perform_request(self, validated_request_data):
        action_ids = validated_request_data.get("action_ids", [])
        resources = Permission.batch_make_resource(validated_request_data.get("resources", []))
        client = Permission()
        detail = []
        for action_id in action_ids:
            is_allowed = client.is_allowed(action_id, resources)
            detail.append({"action_id": action_id, "is_allowed": is_allowed})
        all_allowed = all(d["is_allowed"] for d in detail)
        apply_url = ""
        if not all_allowed:
            _, apply_url = client.get_apply_data(action_ids, resources)
        return {"is_allowed": all_allowed, "detail": detail, "apply_url": apply_url}


class GetAuthorityDetailResource(Resource):
    """
    根据动作ID获取授权信息详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        action_ids = serializers.ListField(required=True, label="动作ID")
        space_uid = serializers.CharField(required=False, default="")

        def validate(self, attrs):
            if not attrs.get("space_uid", ""):
                if not attrs["bk_biz_id"]:
                    raise ValueError("bk_biz_id or space_uid not found")
                return attrs
            space = SpaceApi.get_space_detail(attrs["space_uid"])
            attrs["bk_biz_id"] = space.bk_biz_id
            return attrs

    def perform_request(self, validated_request_data):
        action_ids = validated_request_data["action_ids"]
        client = Permission()

        space = SpaceApi.get_space_detail(bk_biz_id=validated_request_data["bk_biz_id"])

        space_resource = ResourceEnum.BUSINESS.create_instance(space.bk_biz_id)
        actions, detail_resources = client.prepare_apply_for_saas([space_resource])
        if detail_resources:
            space_resource = detail_resources[0]
            action_ids = actions
        apply_data, apply_url = client.get_apply_data(action_ids, [space_resource])
        return {
            "authority_list": apply_data,
            "apply_url": apply_url,
        }


class GetAuthorityApplyInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ResourceSerializer(serializers.Serializer):
            type = serializers.CharField(required=True, label="资源类型")
            id = serializers.CharField(required=True, label="资源ID")

        resources = serializers.ListField(required=True, allow_empty=False, label="资源列表", child=ResourceSerializer())
        action_ids = serializers.ListField(required=True, allow_empty=False, label="动作ID列表")

    def perform_request(self, validated_request_data):
        action_ids = validated_request_data.get("action_ids", [])
        resources = validated_request_data.get("resources", [])
        client = Permission()
        resources = client.batch_make_resource(resources)
        apply_data, apply_url = client.get_apply_data(action_ids, resources)
        return {
            "authority_list": apply_data,
            "apply_url": apply_url,
        }


class TestResource(Resource):
    """
    测试抛出异常
    """

    def perform_request(self, validated_request_data):
        Permission(username="xxx").is_allowed_by_biz(2, ActionEnum.VIEW_BUSINESS, raise_exception=True)


def update_dashboard_permission(bk_biz_id, authorized_users):
    try:
        request = get_request(peaceful=True)
        for authorized_user in authorized_users:
            external_user = f"external_{authorized_user}"
            GrafanaAuthSync.sync(external_user, bk_biz_id, is_external=True)
            ProxyBaseView().provision_user(request, external_user)
            ProxyBaseView().provision_org(str(bk_biz_id), external_user, GrafanaRole.Viewer)

    except Exception as e:
        logger.error(f"更新仪表盘实例权限异常：{e}")


def create_permission(authorized_users, params):
    """
    新增权限
        1. 判定是否有存量被授权人权限
        2. 判定该实例是否已被授权，若有则不处理，无则更新该条授权记录
        3. 给剩余被授权人新增权限
        4. 注入grafana新增被授权人的用户权限
    """
    exist_authorized_users = set()
    for permission_obj in ExternalPermission.objects.filter(
        authorized_user__in=authorized_users,
        action_id=params["action_id"],
        bk_biz_id=params["bk_biz_id"],
    ):
        exist_authorized_users.add(permission_obj.authorized_user)
        all_resources = set(params["resources"]) | set(permission_obj.resources)
        if all_resources - set(permission_obj.resources):
            permission_obj.resources = list(all_resources)
            permission_obj.expire_time = params["expire_time"]
            permission_obj.save()
    add_authorized_users = set(authorized_users) - exist_authorized_users
    ExternalPermission.objects.bulk_create(
        ExternalPermission(authorized_user=authorized_user, **params) for authorized_user in add_authorized_users
    )
    update_dashboard_permission(params["bk_biz_id"], add_authorized_users)


class CreateOrUpdateExternalPermission(Resource):
    """
    创建/更新外部人员权限
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        action_id = serializers.CharField(required=True, label="操作ID")
        authorizer = serializers.CharField(required=True, label="授权人")
        authorized_users = serializers.ListField(required=False, label="被授权人列表")
        resources = serializers.ListField(required=False, label="资源列表")
        expire_time = serializers.DateTimeField(required=False, label="过期时间", default=None)
        view_type = serializers.CharField(label="视图类型", default="user")
        operate_type = serializers.CharField(required=False, label="操作", default="create")

        def validate(self, attrs):
            """
            验证授权人是否有对应操作ID权限
            """
            from monitor_web.grafana.permissions import DashboardPermission

            authorizer = attrs.pop("authorizer", "")
            _, role, _ = DashboardPermission.get_user_permission(authorizer, str(attrs["bk_biz_id"]))
            if (attrs["action_id"] == "view_grafana" and role < GrafanaRole.Viewer) or (
                attrs["action_id"] == "manage_grafana" and role < GrafanaRole.Editor
            ):
                raise serializers.ValidationError(f"{authorizer}无此操作权限")
            return attrs

    def create_approval_ticket(self, authorized_users, params):
        """
        创建ITSM审批单据并创建审批记录，保存单据号和跳转url
        1. 新增权限 - 被授权人视角
        2. 新增权限 - 实例视角
        """
        biz = resource.cc.get_app_by_id(params["bk_biz_id"])
        bk_biz_name = biz.bk_biz_name
        ticket_data = {
            "creator": get_request_username() or get_local_username(),
            "fields": [
                {"key": "bk_biz_id", "value": params["bk_biz_id"]},
                {"key": "bk_biz_name", "value": bk_biz_name},
                {"key": "title", "value": "对外版监控平台授权审批"},
                {"key": "expire_time", "value": params["expire_time"].strftime("%Y-%m-%d %H:%M:%S")},
                {"key": "authorized_user", "value": ",".join(authorized_users)},
                {"key": "resources", "value": ",".join(params["resources"])},
            ],
            "service_id": settings.EXTERNAL_APPROVAL_SERVICE_ID,
            "fast_approval": False,
            "meta": {"callback_url": urljoin(settings.BK_ITSM_CALLBACK_HOST, "/external_callback/")},
        }
        try:
            data = api.itsm.create_fast_approval_ticket(ticket_data)
        except Exception as e:
            logger.error(f"审批创建异常: {e}")
            raise e
        record = ExternalPermissionApplyRecord(
            **params,
            authorized_users=authorized_users,
            approval_url=data.get("ticket_url", ""),
            operate="create",
            approval_sn=data.get("sn", ""),
            status="approval",
        )
        record.save()

    def perform_request(self, validated_request_data):
        """
        1. 基于被授权人视角：
           1.1 新增：需走审批流程
           1.2 编辑：删除存量权限，如有新增则创建审批单据
        2. 基于实例资源视角
           2.1 编辑：删除存量权限，如有新增则创建审批单据
        """
        authorized_users = validated_request_data.pop("authorized_users")
        view_type = validated_request_data.pop("view_type", "user")
        operate_type = validated_request_data.pop("operate_type", "create")
        resources = validated_request_data["resources"]
        expire_time = validated_request_data["expire_time"]
        need_approval = False
        add_authorized_users = []
        add_resources = []
        if operate_type == "create":
            # 新增操作需创建审批流程
            need_approval = True
        elif view_type == "resource":
            # 基于实例视角的编辑操作
            exist_authorized_users = set()
            del_permission_ids = set()
            origin_authorized_users = set(authorized_users)
            # 遍历与该实例相关的授权信息
            for permission in ExternalPermission.objects.filter(
                action_id=validated_request_data["action_id"],
                bk_biz_id=validated_request_data["bk_biz_id"],
            ):
                resource_id = resources[0]
                if resource_id not in permission.resources:
                    continue
                if permission.authorized_user in origin_authorized_users:
                    exist_authorized_users.add(permission.authorized_user)
                else:
                    # 若该被授权人不在编辑提交的被授权人列表中，则删除这条授权中的当前实例
                    permission.resources = list(set(permission.resources) - set(validated_request_data["resources"]))
                    if permission.resources:
                        permission.save()
                    else:
                        # 若删除这条授权中的当前实例则无实例存在，将该授权删除
                        del_permission_ids.add(permission.id)
            ExternalPermission.objects.filter(id__in=del_permission_ids).delete()
            # 判定当前实例是否有新增的被授权人，有则创建审批单据
            add_authorized_users = list(origin_authorized_users - exist_authorized_users)
            if add_authorized_users:
                need_approval = True
        else:
            # 基于被授权人视角的编辑操作
            authorized_user = authorized_users[0]
            try:
                permission = ExternalPermission.objects.get(
                    authorized_user=authorized_user,
                    action_id=validated_request_data["action_id"],
                    bk_biz_id=validated_request_data["bk_biz_id"],
                )
            except ExternalPermission.DoesNotExist:
                raise Exception("该授权人权限不存在，请联系管理员")
            # 新增实例则需要审批，否则直接覆盖截止时间和实例列表
            add_resources = list(set(resources) - set(permission.resources))
            if add_resources:
                need_approval = True
            else:
                permission.resources = resources
                permission.expire_time = expire_time
                permission.save()
        # 记录更新授权操作
        ExternalPermissionApplyRecord.objects.create(
            **validated_request_data, authorized_users=authorized_users, operate="update"
        )
        # 提交审批单据
        if need_approval:
            approval_users = add_authorized_users or authorized_users
            approval_resources = add_resources or resources
            validated_request_data["resources"] = approval_resources
            self.create_approval_ticket(approval_users, validated_request_data)
        return {"need_approval": need_approval}


class DeleteExternalPermission(Resource):
    """
    删除外部人员权限
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        action_id = serializers.CharField(required=True, label="操作ID")
        authorized_users = serializers.ListField(required=False, label="被授权人列表")
        resources = serializers.ListField(required=False, label="资源列表")
        view_type = serializers.CharField(label="视图类型", default="user")

    def perform_request(self, validated_request_data):
        """
        1. 基于被授权人视角：修改资源列表
        2. 基于实例资源视角：修改对应被授权人的资源列表
        """
        authorized_users = validated_request_data["authorized_users"]
        resources = validated_request_data["resources"]
        view_type = validated_request_data.pop("view_type", "user")
        del_permission_ids = []
        if view_type == "resource":
            resource_id = resources[0]
            for permission in ExternalPermission.objects.filter(
                authorized_user__in=authorized_users,
                action_id=validated_request_data["action_id"],
                bk_biz_id=validated_request_data["bk_biz_id"],
            ):
                permission.resources = [
                    exist_resource for exist_resource in permission.resources if exist_resource != resource_id
                ]
                if permission.resources:
                    permission.save()
                else:
                    del_permission_ids.append(permission.id)
        else:
            del_permission_ids = ExternalPermission.objects.filter(
                authorized_user__in=authorized_users,
                action_id=validated_request_data["action_id"],
                bk_biz_id=validated_request_data["bk_biz_id"],
            ).values_list("id", flat=True)
        # 记录删除授权操作
        ExternalPermissionApplyRecord.objects.create(**validated_request_data, operate="delete")
        ExternalPermission.objects.filter(id__in=del_permission_ids).delete()
        return {"delete_permission_ids": list(del_permission_ids)}


class GetExternalPermissionList(Resource):
    """
    获取外部权限列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        view_type = serializers.CharField(label="视图类型", default="user")

    def perform_request(self, validated_request_data):
        """
        1. 基于被授权人视角
        2. 基于实例资源视角
        """
        authorizer_map, _ = GlobalConfig.objects.get_or_create(key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}})
        space_info = {i["bk_biz_id"]: i["space_name"] for i in SpaceApi.list_spaces_dict()}
        permission_qs = ExternalPermission.objects.all()

        # 业务过滤
        if validated_request_data["bk_biz_id"] != 0:
            permission_qs = permission_qs.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        biz_authorizer_role = {}
        for permission in permission_qs:
            # 获取授权人权限
            if permission.bk_biz_id not in biz_authorizer_role:
                authorizer = authorizer_map.value.get(str(permission.bk_biz_id))
                if not authorizer:
                    biz_authorizer_role[permission.bk_biz_id] = GrafanaRole.Anonymous
                else:
                    _, role, _ = DashboardPermission.get_user_permission(authorizer, str(permission.bk_biz_id))
                    biz_authorizer_role[permission.bk_biz_id] = role

        if validated_request_data["view_type"] != "resource":
            serializer = ExternalPermissionSerializer(permission_qs, many=True)
            permission_list = serializer.data
            for permission, permission_data in zip(permission_qs, permission_list):
                authorizer_role = biz_authorizer_role[permission.bk_biz_id]
                permission_data["status"] = permission.get_status(authorizer_role)
        else:
            resource_to_user = defaultdict(lambda: {"authorized_users": []})
            for permission in permission_qs:
                for resource_id in permission.resources:
                    # 根据授权人权限判断权限状态
                    authorizer_role = biz_authorizer_role[permission.bk_biz_id]
                    permission_status = permission.get_status(authorizer_role)

                    resource_key = tuple([permission.action_id, resource_id, permission_status])
                    resource_to_user[resource_key]["authorized_users"].append(permission.authorized_user)
                    resource_to_user[resource_key]["action_id"] = permission.action_id
                    resource_to_user[resource_key]["resource_id"] = resource_id
                    resource_to_user[resource_key]["status"] = permission_status
                    resource_to_user[resource_key]["bk_biz_id"] = permission.bk_biz_id

            permission_list: List[Dict] = list(resource_to_user.values())

        for permission in permission_list:
            permission["authorizer"] = authorizer_map.value.get(str(permission["bk_biz_id"]), "")
            permission["space_name"] = space_info.get(permission["bk_biz_id"], "")
        return permission_list


class CreateOrUpdateAuthorizer(Resource):
    """
    创建/修改授权人（仅允许运维角色修改，仅允许修改授权人为运维角色）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        authorizer = serializers.CharField(required=True, label="授权人")

    def perform_request(self, validated_request_data):
        business = api.cmdb.get_business(bk_biz_ids=[validated_request_data["bk_biz_id"]])
        bk_biz_maintainer = getattr(business[0], "bk_biz_maintainer", [])
        if not bk_biz_maintainer:
            raise Exception(f"业务{validated_request_data['bk_biz_id']}不存在运维角色")
        elif validated_request_data["authorizer"] not in bk_biz_maintainer:
            raise Exception(f"授权人{validated_request_data['authorizer']}不属于该业务的运维角色")
        authorizer_map, _ = GlobalConfig.objects.get_or_create(key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}})
        authorizer_map.value[str(validated_request_data["bk_biz_id"])] = validated_request_data["authorizer"]
        authorizer_map.save()
        return validated_request_data


class GetAuthorizerList(Resource):
    """
    获取授权人列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        business = api.cmdb.get_business(bk_biz_ids=[validated_request_data["bk_biz_id"]])
        bk_biz_maintainer = getattr(business[0], "bk_biz_maintainer", [])
        return bk_biz_maintainer


class GetAuthorizerByBiz(Resource):
    """
    获取当前业务授权人
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        authorizer_map, _ = GlobalConfig.objects.get_or_create(key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}})
        return authorizer_map.value.get(str(validated_request_data["bk_biz_id"]), None)


class GetResourceByAction(Resource):
    """
    根据操作类型获取资源实例列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        action_id = serializers.CharField(required=True, label="操作ID")

    def perform_request(self, validated_request_data):
        if validated_request_data["action_id"] not in ["view_grafana", "manage_grafana"]:
            return []
        if validated_request_data["bk_biz_id"] == 0:
            resources = []
            bk_biz_ids = ExternalPermission.objects.all().values_list("bk_biz_id", flat=True).distinct()
            for bk_biz_id in bk_biz_ids:
                resources.extend(resource.grafana.get_dashboard_list(bk_biz_id=bk_biz_id))
            return resources
        return resource.grafana.get_dashboard_list(bk_biz_id=validated_request_data["bk_biz_id"])


class GetApplyRecordList(Resource):
    """
    获取授权审批记录列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        permission_qs = ExternalPermissionApplyRecord.objects.exclude(status="no_status")
        if validated_request_data["bk_biz_id"] != 0:
            permission_qs = permission_qs.filter(bk_biz_id=validated_request_data["bk_biz_id"])
        serializer = ExternalPermissionApplyRecordSerializer(permission_qs, many=True)
        return serializer.data


class CallbackResource(Resource):
    """
    获取审批结果
    """

    class RequestSerializer(serializers.Serializer):
        sn = serializers.CharField(required=True, label="工单号")
        title = serializers.CharField(required=True, label="工单标题")
        updated_by = serializers.CharField(required=True, label="更新人")
        approve_result = serializers.BooleanField(required=True, label="审批结果")
        token = serializers.CharField(required=False, label="校验token")

    def perform_request(self, validated_request_data):
        if validated_request_data.get("token"):
            verify_data = TokenVerifyResource().request({"token": validated_request_data["token"]})
            if not verify_data.get("is_passed", False):
                return {"message": "Error Token", "result": False}

        try:
            apply_record = ExternalPermissionApplyRecord.objects.get(approval_sn=validated_request_data["sn"])
        except ExternalPermissionApplyRecord.DoesNotExist:
            error_msg = f"更新权限失败，关联单据{validated_request_data['sn']}审批记录不存在"
            logger.error(error_msg)
            return dict(result=False, message=error_msg)
        if not validated_request_data["approve_result"]:
            apply_record.status = "failed"
            apply_record.save()
            return dict(result=True, message=f"approval failed by {validated_request_data['updated_by']}")
        create_params = {
            key: value
            for key, value in apply_record.__dict__.items()
            if key in ["bk_biz_id", "action_id", "resources", "expire_time"]
        }
        create_permission(apply_record.authorized_users, create_params)
        apply_record.status = "success"
        apply_record.save()
        return dict(result=True, message="approval success")
