from collections import defaultdict
from django.utils import timezone

from apps.constants import ViewTypeEnum, TokenStatusEnum, ExternalPermissionActionEnum
from apps.log_commons.models import AuthorizerSettings, ExternalPermission
from bkm_space.api import SpaceApi

from apps.iam import Permission
from apps.iam.handlers import ResourceEnum
from apps.iam.handlers.actions import ActionEnum
from bkm_space.utils import space_uid_to_bk_biz_id


class ExternalPermissionHandler:
    def __init__(self):
        self.bk_biz_id_dict = {}
        self.authorizer_dict = {}
        self.log_extract_is_allowed_dict = {}
        self.log_search_manage_permission_info = {}

    def list(self, space_uid: str = "", view_type: str = ViewTypeEnum.USER.value):
        """
        1. 基于被授权人视角
        2. 基于实例资源视角
        """

        authorizer = self.get_authorizer(space_uid=space_uid)

        permission_qs = ExternalPermission.objects.all()

        if space_uid:
            permission_qs = permission_qs.filter(space_uid=space_uid)

        permission_qs_list = list(permission_qs)

        index_set_ids_map = defaultdict(set)

        for permission in permission_qs_list:
            if permission.action_id == ExternalPermissionActionEnum.LOG_EXTRACT.value:
                continue
            index_set_ids_map[permission.space_uid].update(permission.resources)

        for key_space_uid, index_set_ids in index_set_ids_map.items():
            iam_resources = []
            for index_set_id in index_set_ids:
                attribute = {
                    "bk_biz_id": self.get_bk_biz_id(key_space_uid),
                    "space_uid": key_space_uid,
                }
                iam_resources.append(
                    [ResourceEnum.INDICES.create_simple_instance(instance_id=index_set_id, attribute=attribute)]
                )
            if iam_resources:
                verified_authorizer = self.get_authorizer(space_uid=key_space_uid)
                # result: {index_set_id: {action_id: True / False}}
                result = Permission(username=verified_authorizer).batch_is_allowed(
                    actions=[ActionEnum.SEARCH_LOG], resources=iam_resources
                )
                for index_set_id, permission_info in result.items():
                    index_set_id = int(index_set_id)
                    self.log_search_manage_permission_info[(verified_authorizer, index_set_id, key_space_uid)] = (
                        permission_info
                    )

        if view_type != ViewTypeEnum.RESOURCE.value:
            # 获取每个被授权用户的资源、操作、授权状态信息, 合成列表
            permission_qs_list = sorted(permission_qs_list, key=lambda x: x.updated_at, reverse=True)
            permission_list = [
                {
                    "updated_at": permission.updated_at,
                    "authorized_user": permission.authorized_user,
                    "action_id": permission.action_id,
                    "resources": permission.resources,
                    "expire_time": permission.expire_time,
                    "status": self.get_status(permission),
                    "space_uid": permission.space_uid,
                }
                for permission in permission_qs_list
            ]
        else:
            # 资源 + 操作 + 状态作为 key, 获取相对应的被授权用户列表以及授权状态等
            resource_to_user = defaultdict(lambda: {"authorized_users": []})
            for permission in permission_qs_list:
                status = self.get_status(permission)
                for resource_id in permission.resources:
                    resource_key = (permission.action_id, resource_id, status)
                    resource_to_user[resource_key]["authorized_users"].append(permission.authorized_user)
                    resource_to_user[resource_key]["action_id"] = permission.action_id
                    resource_to_user[resource_key]["resource_id"] = resource_id
                    resource_to_user[resource_key]["status"] = status
                    resource_to_user[resource_key]["space_uid"] = permission.space_uid
                    # 创建时间设置为资源中的最早创建时间
                    if "created_at" not in resource_to_user[resource_key]:
                        resource_to_user[resource_key]["created_at"] = permission.created_at
                    elif permission.created_at and permission.created_at < resource_to_user[resource_key]["created_at"]:
                        resource_to_user[resource_key]["created_at"] = permission.created_at

            permission_list = list(resource_to_user.values())
            # 按创建时间倒序排列
            permission_list.sort(key=lambda x: x["created_at"], reverse=True)

        # 获取所有 space_uid, 构造空间名称映射
        space_uids = {permission["space_uid"] for permission in permission_list}
        space_names = {
            space_uid: detail.space_name
            for space_uid, detail in SpaceApi.batch_get_space_detail(space_uids).items()
            if detail and hasattr(detail, "space_name") and detail.space_name
        }

        for permission in permission_list:
            permission["space_name"] = space_names.get(permission["space_uid"], "")
            if not space_uid:
                permission["authorizer"] = self.get_authorizer(space_uid=permission["space_uid"])
            else:
                permission["authorizer"] = authorizer

        return permission_list

    def get_status(self, obj: ExternalPermission):
        """
        获取状态
        """
        status = TokenStatusEnum.AVAILABLE.value

        if obj.expire_time and timezone.now() > obj.expire_time:
            status = TokenStatusEnum.EXPIRED.value
            return status

        # 需要对授权人的权限进行校验
        authorizer = self.get_authorizer(space_uid=obj.space_uid)

        if authorizer:
            if obj.action_id == ExternalPermissionActionEnum.LOG_EXTRACT.value:
                # 日志提取权限维度是空间
                if not self.does_the_authorizer_have_log_extract_manage_permission_of_bk_biz_id(
                    authorizer, obj.space_uid
                ):
                    # 如果授权者没有或失去该 bk_biz_id 下的日志提取管理权限, 则状态设为无效
                    status = TokenStatusEnum.INVALID.value
            elif obj.action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
                # 日志检索权限维度是索引集
                permission_info_map = {}
                for index_set_id in obj.resources:
                    permission_info_map[index_set_id] = self.get_permission_info(
                        authorizer, index_set_id, obj.space_uid
                    )
                # 如果授权者没有或失去其中一个 index_set_id 下的日志检索管理权限, 则状态设为无效
                # permission_info_dict: {index_set_id: {action_id: True/False}}
                for index_set_id, permission_info in permission_info_map.items():
                    index_set_id = int(index_set_id)
                    if index_set_id not in obj.resources:
                        continue
                    if not permission_info or not permission_info.get(ActionEnum.SEARCH_LOG.id, False):
                        status = TokenStatusEnum.INVALID.value
                        break
        else:
            status = TokenStatusEnum.INVALID.value

        return status

    def get_permission_info(self, authorizer, index_set_id: int, space_uid):
        """
        获取权限信息
        """

        return self.log_search_manage_permission_info.get((authorizer, index_set_id, space_uid))

    def does_the_authorizer_have_log_extract_manage_permission_of_bk_biz_id(self, authorizer, space_uid):
        """
        授权者是否拥有该 bk_biz_id 下的日志提取管理权限
        """

        is_allowed = self.log_extract_is_allowed_dict.get((authorizer, space_uid))

        if is_allowed is None:
            temp_bk_biz_id = self.get_bk_biz_id(space_uid)
            # is_allowed_by_biz 里针对 bk_biz_id 的判断, 当非 BKCC 的时候需要传入 space_uid
            bk_biz_id = temp_bk_biz_id if temp_bk_biz_id > 0 else space_uid
            is_allowed = Permission(username=authorizer).is_allowed_by_biz(
                bk_biz_id=bk_biz_id, action=ActionEnum.MANAGE_EXTRACT_CONFIG, raise_exception=False
            )
            self.log_extract_is_allowed_dict[(authorizer, space_uid)] = is_allowed

        return is_allowed

    def get_authorizer(self, space_uid: str = ""):
        """
        获取授权人
        """

        authorizer = self.authorizer_dict.get(space_uid)

        if authorizer is None:
            authorizer = AuthorizerSettings.get_authorizer(space_uid=space_uid)
            self.authorizer_dict[space_uid] = authorizer

        return authorizer

    def get_bk_biz_id(self, space_uid):
        """
        获取业务ID
        """

        bk_biz_id = self.bk_biz_id_dict.get(space_uid)

        if bk_biz_id is None:
            bk_biz_id = space_uid_to_bk_biz_id(space_uid)
            self.bk_biz_id_dict[space_uid] = bk_biz_id

        return bk_biz_id
