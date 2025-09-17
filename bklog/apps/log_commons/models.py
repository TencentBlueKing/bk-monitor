from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin

import pytz
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from apps.api import BkItsmApi
from apps.constants import (
    ITEM_EXTERNAL_PERMISSION_LOG_ASSESSMENT,
    ApiTokenAuthType,
    ExternalPermissionActionEnum,
    ITSMStatusChoicesEnum,
    OperateEnum,
    TokenStatusEnum,
    ViewSetActionEnum,
    ViewTypeEnum,
)
from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import EXTERNAL_AUTHORIZER_MAP
from apps.iam import Permission
from apps.iam.handlers import ResourceEnum
from apps.iam.handlers.actions import ActionEnum
from apps.log_commons.cc import get_maintainers
from apps.log_commons.exceptions import IllegalMaintainerException
from apps.models import OperateRecordModel
from apps.utils.local import get_local_username, get_request_username
from apps.utils.log import logger
from bkm_space.api import SpaceApi
from bkm_space.utils import space_uid_to_bk_biz_id


def get_random_string_16() -> str:
    """
    获取16位随机字符串
    :return:
    """
    return get_random_string(length=16)


class ApiAuthToken(OperateRecordModel):
    """API鉴权令牌"""

    space_uid = models.CharField(_("空间唯一标识"), blank=True, default="", max_length=256, db_index=True)
    token = models.CharField(_("鉴权令牌"), max_length=32, default=get_random_string_16)
    type = models.CharField(_("鉴权类型"), max_length=32, choices=ApiTokenAuthType.get_choices())
    params = models.JSONField(_("鉴权参数"), default=dict)
    expire_time = models.DateTimeField(_("过期时间"), blank=True, null=True, default=None)

    class Meta:
        verbose_name = _("API鉴权令牌")
        verbose_name_plural = _("API鉴权令牌")

    def is_expired(self):
        """
        判断token是否过期
        """
        # 未设置过期时间，不判断是否过期
        if not self.expire_time:
            return False
        return self.expire_time < datetime.now(tz=pytz.utc)


class AuthorizerSettings:
    """
    外部授权人特性开关设置
    """

    @classmethod
    def switch(cls, space_uid: str):
        bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        obj = cls.get_or_create()
        if bk_biz_id in obj.biz_id_white_list:
            return True
        return False

    @classmethod
    def get_or_create(cls):
        obj, __ = FeatureToggle.objects.get_or_create(
            name=EXTERNAL_AUTHORIZER_MAP,
            defaults={"status": "debug", "is_viewed": False, "feature_config": {}, "biz_id_white_list": [],
                      "biz_id_black_list": []},
        )
        return obj

    @classmethod
    def enable_space(cls, space_uid: str, authorized_user: str):
        bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        obj = cls.get_or_create()
        if bk_biz_id not in obj.biz_id_white_list:
            obj.biz_id_white_list.append(bk_biz_id)
            obj.feature_config[str(bk_biz_id)] = authorized_user
            obj.save()
        logger.info(f"AuthorizerSettings enable space {space_uid}, authorized_user: {authorized_user}")

    @classmethod
    def disable_space(cls, space_uid: str):
        bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        obj = cls.get_or_create()
        if bk_biz_id in obj.biz_id_white_list:
            obj.biz_id_white_list.remove(bk_biz_id)
            obj.feature_config.pop(str(bk_biz_id))
            obj.save()
        logger.info(f"AuthorizerSettings disable space {space_uid}")

    @classmethod
    def get_authorizer(cls, space_uid: str = "") -> str:
        if not space_uid or not cls.switch(space_uid=space_uid):
            return ""
        bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        obj = cls.get_or_create()
        return obj.feature_config.get(str(bk_biz_id), "")

    @classmethod
    def create_or_update(cls, space_uid: str, maintainer: str):
        allowed_maintainers = get_maintainers(space_uid=space_uid)
        if maintainer not in allowed_maintainers:
            logger.error(f"maintainer {maintainer} is not allowed to be authorizer, space_uid: {space_uid}")
            raise IllegalMaintainerException()
        if not cls.switch(space_uid=space_uid):
            cls.enable_space(space_uid=space_uid, authorized_user=maintainer)
            logger.info(f"AuthorizerSettings enable space {space_uid}, authorized_user: {maintainer}")
            return maintainer
        obj = cls.get_or_create()
        obj.feature_config[str(space_uid_to_bk_biz_id(space_uid))] = maintainer
        obj.save()
        logger.info(f"AuthorizerSettings update space {space_uid}, authorized_user: {maintainer}")
        return maintainer


class ExternalPermission(OperateRecordModel):
    """
    外部权限
    """

    space_uid = models.CharField(_("空间唯一标识"), blank=True, default="", max_length=256, db_index=True)
    authorized_user = models.CharField("被授权人", max_length=64)
    action_id = models.CharField(
        "操作类型", max_length=32, choices=ExternalPermissionActionEnum.get_choices(), db_index=True
    )
    resources = models.JSONField("资源列表", default=list)
    expire_time = models.DateTimeField("过期时间", null=True, default=None)

    class Meta:
        verbose_name = "外部权限"
        verbose_name_plural = "外部权限"
        db_table = "external_permission"
        index_together = (("authorized_user", "action_id", "space_uid"),)

    @property
    def bk_biz_id(self):
        return space_uid_to_bk_biz_id(self.space_uid)

    @classmethod
    def get_authorized_user_space_list(cls, authorized_user: str) -> List[str]:
        """
        获取被授权人的空间列表
        :param authorized_user: 被授权人
        :return:
        """
        return (
            ExternalPermission.objects.filter(authorized_user=authorized_user, expire_time__gt=timezone.now())
            .values_list("space_uid", flat=True)
            .distinct()
        )

    @property
    def status(self):
        status = TokenStatusEnum.AVAILABLE.value
        if self.expire_time and timezone.now() > self.expire_time:
            status = TokenStatusEnum.EXPIRED.value
            return status
        # 需要对授权人的权限进行校验
        authorizer = AuthorizerSettings.get_authorizer(space_uid=self.space_uid)
        if authorizer:
            if self.action_id == ExternalPermissionActionEnum.LOG_EXTRACT.value:
                # 日志提取权限维度是空间
                # is_allowed_by_biz里针对bk_biz_id的判断, 当非BKCC的时候需要传入space_uid
                bk_biz_id = self.bk_biz_id if self.bk_biz_id > 0 else self.space_uid
                if not Permission(username=authorizer).is_allowed_by_biz(
                    bk_biz_id=bk_biz_id, action=ActionEnum.MANAGE_EXTRACT_CONFIG, raise_exception=False
                ):
                    status = TokenStatusEnum.INVALID.value
            elif self.action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
                # 日志检索权限维度是索引集
                iam_resources = []
                for index_set_id in self.resources:
                    attribute = {
                        "bk_biz_id": self.bk_biz_id,
                        "space_uid": self.space_uid,
                    }
                    iam_resources.append(
                        [ResourceEnum.INDICES.create_simple_instance(instance_id=index_set_id, attribute=attribute)]
                    )
                permission_result = Permission(username=authorizer).batch_is_allowed(
                    actions=[ActionEnum.SEARCH_LOG], resources=iam_resources
                )
                # permission_result: {index_set_id: {action_id: True/False}}
                for k, v in permission_result.items():
                    if int(k) not in self.resources:
                        continue
                    if not v.get(ActionEnum.SEARCH_LOG.id, False):
                        status = TokenStatusEnum.INVALID.value
                        break
        return status

    @classmethod
    def create(
        cls, authorized_users: List[str], space_uid: str, action_id: str, resources: List[str], expire_time: str
    ):
        """
        新增权限
            1. 判定是否有存量被授权人权限
            2. 判定该实例是否已被授权，若有则不处理，无则更新该条授权记录
            3. 给剩余被授权人新增权限
        """
        exist_authorized_users = set()
        for permission_obj in cls.objects.filter(
            authorized_user__in=authorized_users,
            action_id=action_id,
            space_uid=space_uid,
        ):
            exist_authorized_users.add(permission_obj.authorized_user)
            all_resources = set(resources) | set(permission_obj.resources)
            if all_resources - set(permission_obj.resources):
                permission_obj.resources = list(all_resources)
                permission_obj.expire_time = expire_time
                permission_obj.save()
        add_authorized_users = set(authorized_users) - exist_authorized_users
        cls.objects.bulk_create(
            cls(
                authorized_user=authorized_user,
                space_uid=space_uid,
                action_id=action_id,
                resources=resources,
                expire_time=expire_time,
            )
            for authorized_user in add_authorized_users
        )

    @classmethod
    def build_itsm_resources_display_name(cls, action_id: str, space_uid: str, resources: List[Any]) -> str:
        """
        拼接资源列表, 用于ITSM审批单据展示
        :param action_id: ExternalPermissionActionEnum 定义的模块操作ID
        :param space_uid: 空间唯一标识
        :param resources:
        :return:
        """
        allowed_resources: List[Dict[str, Any]] = cls.get_resource_by_action(action_id=action_id, space_uid=space_uid)
        if not resources or not allowed_resources:
            return ""
        return ", ".join(
            [
                "[{id}]{text}".format(id=resource["id"], text=resource["text"])
                for resource in allowed_resources
                if resource["id"] in resources
            ]
        )

    @classmethod
    def create_approval_ticket(cls, authorized_users: List[str], params: Dict[str, Any]):
        """
        创建ITSM审批单据并创建审批记录，保存单据号和跳转url
        1. 新增权限 - 被授权人视角
        2. 新增权限 - 实例视角
        """
        action_id = params["action_id"]
        space_uid = params["space_uid"]
        space_info = SpaceApi.get_space_detail(space_uid=space_uid)
        bk_biz_id = space_info.bk_biz_id
        bk_biz_name = space_info.space_name
        username = get_request_username() or get_local_username()
        ticket_data = {
            "creator": username,
            # operator和creator保持一致
            "operator": username,
            # 这里是因为需要使用admin创建单据，方能越过创建单据的权限限制
            "bk_username": "admin",
            "fields": [
                {"key": "bk_biz_id", "value": bk_biz_id},
                {"key": "bk_biz_name", "value": bk_biz_name},
                {"key": "title", "value": ITEM_EXTERNAL_PERMISSION_LOG_ASSESSMENT},
                {"key": "expire_time", "value": params["expire_time"]},
                {"key": "action_id", "value": ExternalPermissionActionEnum.get_choice_label(params["action_id"])},
                {"key": "authorized_user", "value": ",".join(authorized_users)},
                {"key": "approver", "value": ",".join(get_maintainers(space_uid=space_uid))},
                {
                    "key": "resources",
                    "value": cls.build_itsm_resources_display_name(
                        action_id=action_id, space_uid=space_uid, resources=params["resources"]
                    ),
                },
            ],
            "service_id": settings.ITSM_EXTERNAL_PERMISSION_SERVICE_ID,
            "fast_approval": False,
            "meta": {"callback_url": urljoin(settings.BK_ITSM_CALLBACK_HOST, "/external_callback/")},
        }
        try:
            data = BkItsmApi.create_ticket(ticket_data)
        except Exception as e:
            logger.error(f"审批创建异常: {e}")
            raise e
        record = ExternalPermissionApplyRecord(
            **params,
            authorized_users=authorized_users,
            approval_url=data.get("ticket_url", ""),
            operate=OperateEnum.CREATE.value,
            approval_sn=data.get("sn", ""),
            status=ITSMStatusChoicesEnum.APPROVAL.value,
        )
        record.save()

    @classmethod
    def create_or_update(cls, validated_request_data: Dict[str, Any]):
        """
        1. 基于被授权人视角：
           1.1 新增：需走审批流程
           1.2 编辑：删除存量权限，如有新增则创建审批单据
        2. 基于实例资源视角
           2.1 编辑：删除存量权限，如有新增则创建审批单据
        """
        authorized_users = validated_request_data.pop("authorized_users")
        if "__all__" in authorized_users:
            authorized_users = list(
                cls.objects.filter(
                    space_uid=validated_request_data["space_uid"],
                )
                .values_list("authorized_user", flat=True)
                .distinct()
            )

        view_type = validated_request_data.pop("view_type", ViewTypeEnum.USER.value)
        operate_type = validated_request_data.pop("operate_type", OperateEnum.CREATE.value)
        resources = validated_request_data["resources"]
        expire_time = validated_request_data["expire_time"]
        need_approval = False
        add_authorized_users = []
        add_resources = []
        if operate_type == OperateEnum.CREATE.value:
            # 新增操作需创建审批流程
            need_approval = True
        elif view_type == ViewTypeEnum.RESOURCE.value:
            # 基于实例视角的编辑操作
            exist_authorized_users = set()
            del_permission_ids = set()
            origin_authorized_users = set(authorized_users)
            # 遍历与该实例相关的授权信息
            for permission in cls.objects.filter(
                action_id=validated_request_data["action_id"],
                space_uid=validated_request_data["space_uid"],
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
            cls.objects.filter(id__in=del_permission_ids).delete()
            # 判定当前实例是否有新增的被授权人，有则创建审批单据
            add_authorized_users = list(origin_authorized_users - exist_authorized_users)
            if add_authorized_users:
                need_approval = True
        else:
            # 基于被授权人视角的编辑操作
            authorized_user = authorized_users[0]
            try:
                permission = cls.objects.get(
                    authorized_user=authorized_user,
                    action_id=validated_request_data["action_id"],
                    space_uid=validated_request_data["space_uid"],
                )
            except cls.DoesNotExist:
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
            **validated_request_data, authorized_users=authorized_users, operate=OperateEnum.UPDATE.value
        )
        # 提交审批单据
        if need_approval:
            approval_users = add_authorized_users or authorized_users
            approval_resources = add_resources or resources
            validated_request_data["resources"] = approval_resources
            cls.create_approval_ticket(approval_users, validated_request_data)
        return {"need_approval": need_approval}

    @classmethod
    def destroy(cls, validated_request_data: Dict[str, Any]):
        """
        1. 基于被授权人视角：修改资源列表
        2. 基于实例资源视角：修改对应被授权人的资源列表
        """
        authorized_users = validated_request_data["authorized_users"]
        resources = validated_request_data["resources"]
        view_type = validated_request_data.pop("view_type", ViewTypeEnum.USER.value)
        del_permission_ids = []
        if view_type == ViewTypeEnum.RESOURCE.value:
            resource_id = resources[0]
            for permission in cls.objects.filter(
                authorized_user__in=authorized_users,
                action_id=validated_request_data["action_id"],
                space_uid=validated_request_data["space_uid"],
            ):
                permission.resources = [
                    exist_resource for exist_resource in permission.resources if exist_resource != resource_id
                ]
                if permission.resources:
                    permission.save()
                else:
                    del_permission_ids.append(permission.id)
        else:
            del_permission_ids = cls.objects.filter(
                authorized_user__in=authorized_users,
                action_id=validated_request_data["action_id"],
                space_uid=validated_request_data["space_uid"],
            ).values_list("id", flat=1)
        # 记录删除授权操作
        ExternalPermissionApplyRecord.objects.create(**validated_request_data, operate=OperateEnum.DELETE.value)
        cls.objects.filter(id__in=del_permission_ids).delete()
        return {"delete_permission_ids": list(del_permission_ids)}

    @classmethod
    def list(cls, space_uid: str = "", view_type: str = ViewTypeEnum.USER.value):
        """
        1. 基于被授权人视角
        2. 基于实例资源视角
        """
        authorizer = AuthorizerSettings.get_authorizer(space_uid=space_uid)
        permission_qs = ExternalPermission.objects.all()
        if space_uid:
            permission_qs = permission_qs.filter(space_uid=space_uid)
        if view_type != ViewTypeEnum.RESOURCE.value:
            permission_qs = permission_qs.order_by("-updated_at")
            permission_list = [
                {
                    "updated_at": permission.updated_at,
                    "authorized_user": permission.authorized_user,
                    "action_id": permission.action_id,
                    "resources": permission.resources,
                    "expire_time": permission.expire_time,
                    "status": permission.status,
                    "space_uid": permission.space_uid,
                }
                for permission in permission_qs.iterator()
            ]
        else:
            resource_to_user = defaultdict(lambda: {"authorized_users": []})
            for permission in permission_qs:
                for resource_id in permission.resources:
                    resource_key = tuple([permission.action_id, resource_id, permission.status])
                    resource_to_user[resource_key]["authorized_users"].append(permission.authorized_user)
                    resource_to_user[resource_key]["action_id"] = permission.action_id
                    resource_to_user[resource_key]["resource_id"] = resource_id
                    resource_to_user[resource_key]["status"] = permission.status
                    resource_to_user[resource_key]["space_uid"] = permission.space_uid
                    if "created_at" not in resource_to_user[resource_key]:
                        resource_to_user[resource_key]["created_at"] = permission.created_at
                    elif permission.created_at and permission.created_at < resource_to_user[resource_key]["created_at"]:
                        resource_to_user[resource_key]["created_at"] = permission.created_at

            permission_list = list(resource_to_user.values())
            # 按创建时间倒序排列
            permission_list.sort(key=lambda x: x["created_at"], reverse=True)

        # 获取所有的空间ID，构造空间名称映射
        space_uids = {permission["space_uid"] for permission in permission_list}
        space_names = {}
        for space_uid in space_uids:
            space_info = SpaceApi.get_space_detail(space_uid=space_uid)
            if space_info:
                space_names[space_uid] = space_info.space_name

        for permission in permission_list:
            if not space_uid:
                permission["authorizer"] = AuthorizerSettings.get_authorizer(space_uid=permission["space_uid"])
            else:
                permission["authorizer"] = authorizer
            permission["space_name"] = space_names.get(permission["space_uid"], "")
        return permission_list

    @classmethod
    def create_or_update_authorizer(cls, space_uid: str, authorizer: str):
        maintainers = get_maintainers(space_uid=space_uid)
        if not maintainers:
            raise Exception(f"空间{space_uid}不存在运维角色")
        elif authorizer not in maintainers:
            raise Exception(f"授权人{authorizer}不属于该业务的运维角色")
        if not AuthorizerSettings.switch(space_uid=space_uid):
            AuthorizerSettings.enable_space(space_uid=space_uid, authorized_user=authorizer)

    @classmethod
    def list_authorizer(cls, space_uid: str) -> List[str]:
        return get_maintainers(space_uid=space_uid)

    @classmethod
    def get_authorizer(cls, space_uid: str) -> str:
        return AuthorizerSettings.get_authorizer(space_uid=space_uid)

    @classmethod
    def get_resource_by_action(cls, action_id: str, space_uid: str = "") -> List[Dict[str, Any]]:
        if action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
            return cls._get_log_search_resource(space_uid=space_uid)
        if action_id == ExternalPermissionActionEnum.LOG_EXTRACT.value:
            return cls._get_log_extract_resource(space_uid=space_uid)
        return []

    @classmethod
    def _get_log_search_resource(cls, space_uid: str) -> List[Dict[str, Any]]:
        from apps.log_search.handlers.index_set import IndexSetHandler
        from apps.log_search.models import LogIndexSet

        related_space_uids = []
        if not space_uid:
            space_uid_list = ExternalPermission.objects.all().values_list("space_uid", flat=True).distinct()
            for _space_uid in space_uid_list:
                related_space_uids.extend(IndexSetHandler.get_all_related_space_uids(space_uid=_space_uid))
        else:
            related_space_uids = IndexSetHandler.get_all_related_space_uids(space_uid=space_uid)
        qs = LogIndexSet.objects.filter(space_uid__in=related_space_uids)
        return [
            {
                "id": index_set.index_set_id,
                "uid": index_set.index_set_id,
                "text": index_set.index_set_name,
            }
            for index_set in qs.iterator()
        ]

    @classmethod
    def _get_log_extract_resource(cls, space_uid: str) -> List[Dict[str, Any]]:
        from apps.log_extract.models import Strategies

        # 只过滤授权人有的策略
        authorizer = AuthorizerSettings.get_authorizer(space_uid=space_uid)
        qs = Strategies.objects.filter(user_list__contains=f",{authorizer},").exclude(operator="")
        if not space_uid:
            space_uid_list = ExternalPermission.objects.all().values_list("space_uid", flat=True).distinct()
            bk_biz_id_list = [space_uid_to_bk_biz_id(space_uid) for space_uid in space_uid_list]
            qs = qs.filter(bk_biz_id__in=bk_biz_id_list)
        else:
            bk_biz_id = space_uid_to_bk_biz_id(space_uid)
            qs = qs.filter(bk_biz_id=bk_biz_id)

        return [
            {
                "id": strategy.strategy_id,
                "uid": strategy.strategy_id,
                "text": strategy.strategy_name,
            }
            for strategy in qs.iterator()
        ]

    @classmethod
    def get_authorizer_permission(cls, authorizer: str, space_uid: str = "") -> Dict[str, List[str]]:
        """
        获取授权人的各个业务ID的权限列表
        """
        qs = ExternalPermission.objects.filter(authorized_user=authorizer, expire_time__gt=timezone.now())
        if space_uid:
            qs = qs.filter(space_uid=space_uid)
        space_uid_permission_dict = defaultdict(list)
        for permission in qs.iterator():
            space_uid_permission_dict[permission.space_uid].append(permission.action_id)
        return space_uid_permission_dict

    @classmethod
    def is_action_valid(cls, view_set: str, view_action: str, action_id: str):
        """
        判断ViewSet和Action是否合法
        :param view_set: 视图ViewSet
        :param view_action: 视图接口Action
        :param action_id: 后台定义操作ID, ActionEnum
        :return: bool
        """
        for _action in ViewSetActionEnum.get_keys():
            if _action.action_id != action_id:
                continue
            if _action.view_set != view_set:
                continue
            if not _action.view_action:
                return True
            if _action.view_action == view_action:
                return True
        return False

    @classmethod
    def get_resources(cls, action_id: str, authorized_user: str, space_uid: str):
        """
        获取被授权人的资源列表
        :param action_id: 操作ID
        :param authorized_user: 被授权人
        :param space_uid: 空间唯一标识
        :return:
        """
        result = {
            "allowed": False,
            "resources": [],
        }
        if action_id == ExternalPermissionActionEnum.LOG_COMMON.value:
            return result
        result["allowed"] = True
        # 可能多次授权, 需要合并资源
        objs = ExternalPermission.objects.filter(
            action_id=action_id, authorized_user=authorized_user, space_uid=space_uid, expire_time__gt=timezone.now()
        )
        for obj in objs:
            result["resources"].extend(obj.resources)
        return result


class ExternalPermissionApplyRecord(OperateRecordModel):
    """
    外部权限授权记录
    """

    space_uid = models.CharField(_("空间唯一标识"), blank=True, default="", max_length=256, db_index=True)
    authorized_users = models.JSONField("被授权人列表", default=list)
    resources = models.JSONField("资源列表", default=list)
    action_id = models.CharField(
        "操作类型", max_length=32, choices=ExternalPermissionActionEnum.get_choices(), db_index=True
    )
    operate = models.CharField(
        "操作",
        choices=OperateEnum.get_choices(),
        db_index=True,
        max_length=12,
    )
    expire_time = models.DateTimeField("过期时间", null=True, default=None)
    approval_sn = models.CharField("审批单号", max_length=128, default="", null=True, blank=True)
    approval_url = models.CharField("审批地址", default="", max_length=1024, null=True, blank=True)
    status = models.CharField(
        "状态", max_length=32, choices=ITSMStatusChoicesEnum.get_choices(), default=ITSMStatusChoicesEnum.NO_STATUS.value
    )

    class Meta:
        verbose_name = "外部权限授权记录"
        verbose_name_plural = "外部权限授权记录"
        db_table = "external_permission_apply_record"

    @classmethod
    def callback(cls, params: dict):
        if params.get("token"):
            verify_data = BkItsmApi.token_verify({"token": params["token"]})
            if not verify_data.get("is_passed", False):
                return {"message": "Error Token", "result": False}

        try:
            apply_record = ExternalPermissionApplyRecord.objects.get(approval_sn=params["sn"])
        except ExternalPermissionApplyRecord.DoesNotExist:
            error_msg = f"更新权限失败，关联单据{params['sn']}审批记录不存在"
            logger.error(error_msg)
            return dict(result=False, message=error_msg)
        if not params["approve_result"]:
            apply_record.status = ITSMStatusChoicesEnum.FAILED.value
            apply_record.save()
            return dict(result=True, message=f"approval failed by {params['updated_by']}")
        create_params = {
            key: value
            for key, value in apply_record.__dict__.items()
            if key in ["space_uid", "action_id", "resources", "expire_time"]
        }
        create_params["authorized_users"] = apply_record.authorized_users
        ExternalPermission.create(**create_params)
        apply_record.status = ITSMStatusChoicesEnum.SUCCESS.value
        apply_record.save()
        return dict(result=True, message="approval success")

    @classmethod
    def list(cls, space_uid: str):
        qs = ExternalPermissionApplyRecord.objects.exclude(status=ITSMStatusChoicesEnum.NO_STATUS.value)
        if space_uid:
            qs = qs.filter(space_uid=space_uid)
        qs = qs.order_by("-created_at")
        return [
            {
                "authorized_users": record.authorized_users,
                "space_uid": record.space_uid,
                "action_id": record.action_id,
                "resources": record.resources,
                "status": record.status,
                "expire_time": record.expire_time,
                "created_at": record.created_at,
                "created_by": record.created_by,
                "approval_sn": record.approval_sn,
                "approval_url": record.approval_url,
            }
            for record in qs.iterator()
        ]


class TokenAccessRecord(OperateRecordModel):
    """
    API鉴权令牌访问记录
    """

    token = models.CharField("鉴权令牌", max_length=32)

    class Meta:
        verbose_name = "API鉴权令牌访问记录"
        verbose_name_plural = "API鉴权令牌访问记录"
        db_table = "token_access_record"
        index_together = (("token", "created_by"),)
