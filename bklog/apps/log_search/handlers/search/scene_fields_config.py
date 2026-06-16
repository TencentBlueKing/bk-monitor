"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from django.forms.models import model_to_dict

from apps.log_search.constants import DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME, SearchScopeEnum
from apps.log_search.exceptions import (
    SceneDefaultConfigNotAllowedDelete,
    SceneFieldsConfigAlreadyExistException,
    SceneFieldsConfigNotExistException,
)
from apps.log_search.models import SceneFieldsConfig, UserSceneCustomConfig, UserSceneFieldsConfig
from apps.utils.local import get_request_app_code, get_request_external_username, get_request_username


class SceneFieldsConfigHandler:
    """场景化字段模板（展示字段 + 排序）CRUD 与应用，对标 IndexSetFieldsConfigHandler。"""

    data: SceneFieldsConfig | None = None

    def __init__(
        self,
        config_id: int | None = None,
        bk_biz_id: int | None = None,
        scene_id: str | None = None,
        scope: str = SearchScopeEnum.DEFAULT.value,
    ):
        self.config_id = config_id
        self.bk_biz_id = bk_biz_id
        self.scene_id = scene_id
        self.scope = scope
        self.source_app_code = get_request_app_code()
        if config_id:
            try:
                self.data = SceneFieldsConfig.objects.get(pk=config_id)
            except SceneFieldsConfig.DoesNotExist:
                raise SceneFieldsConfigNotExistException()
            self._validate_ownership()

    def _validate_ownership(self):
        """校验请求方对该模板的归属权，避免凭 config_id 枚举越权读取/删除/应用他业务模板。

        retrieve_config / delete_config / apply_config 仅传 config_id，没有 bk_biz_id
        参数可供权限类在 view 层判断，因此这里基于取到的对象自身做兜底校验：
        - source_app_code 必须与模板一致（跨 SaaS 应用隔离）；
        - 若调用方显式传入了 bk_biz_id / scene_id，则必须与模板一致；
        - 始终对模板所属业务做 VIEW_BUSINESS 鉴权（无权限抛带申请链接的异常）。
        归属类校验失败统一抛 SceneFieldsConfigNotExistException，不暴露存在性。
        （scope 默认值会与历史数据不一致，故不在此强校验，业务+场景+应用三元组已足以隔离。）
        """
        if self.source_app_code and self.data.source_app_code != self.source_app_code:
            raise SceneFieldsConfigNotExistException()
        if self.bk_biz_id is not None and self.data.bk_biz_id != self.bk_biz_id:
            raise SceneFieldsConfigNotExistException()
        if self.scene_id is not None and self.data.scene_id != self.scene_id:
            raise SceneFieldsConfigNotExistException()
        self._verify_business_permission(self.data.bk_biz_id)

    @staticmethod
    def _verify_business_permission(bk_biz_id):
        from django.conf import settings

        if settings.IGNORE_IAM_PERMISSION or not bk_biz_id:
            return
        from apps.iam import ActionEnum, ResourceEnum
        from apps.iam.handlers.permission import Permission

        Permission().is_allowed(
            action=ActionEnum.VIEW_BUSINESS,
            resources=[ResourceEnum.BUSINESS.create_instance(bk_biz_id)],
            raise_exception=True,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def retrieve(self) -> dict:
        if not self.data:
            raise SceneFieldsConfigNotExistException()
        return model_to_dict(self.data)

    def list(self) -> list:
        objs = SceneFieldsConfig.objects.filter(
            bk_biz_id=self.bk_biz_id,
            scene_id=self.scene_id,
            scope=self.scope,
            source_app_code=self.source_app_code,
        ).all()
        config_list = [model_to_dict(obj) for obj in objs]
        # 默认模板排在最前
        config_list.sort(key=lambda c: c["name"] == DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME, reverse=True)
        return config_list

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_or_update(self, name: str, display_fields: list, sort_list: list) -> dict:
        username = get_request_external_username() or get_request_username()
        # 名称重复校验（创建态、或更新但改名时）
        if not self.data or self.data.name != name:
            exists = SceneFieldsConfig.objects.filter(
                bk_biz_id=self._infer_biz_id(),
                scene_id=self._infer_scene_id(),
                name=name,
                scope=self._infer_scope(),
                source_app_code=self.source_app_code,
            ).exists()
            if exists:
                raise SceneFieldsConfigAlreadyExistException()

        if self.data:
            # 默认模板不允许改名
            if self.data.name != DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME:
                self.data.name = name
            self.data.display_fields = display_fields
            self.data.sort_list = sort_list
            self.data.updated_by = username
            self.data.save()
        else:
            self.data = SceneFieldsConfig.objects.create(
                name=name,
                bk_biz_id=self.bk_biz_id,
                scene_id=self.scene_id,
                scope=self.scope,
                source_app_code=self.source_app_code,
                display_fields=display_fields,
                sort_list=sort_list,
                created_by=username,
                updated_by=username,
            )
        return model_to_dict(self.data)

    def delete(self):
        if not self.data:
            raise SceneFieldsConfigNotExistException()
        if self.data.name == DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME:
            raise SceneDefaultConfigNotAllowedDelete()
        SceneFieldsConfig.delete_config(self.config_id, source_app_code=self.source_app_code)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, username: str) -> dict:
        """切换用户当前在 (业务, 场景, 范围, 来源) 下应用的模板指针，返回用户视角完整配置。"""
        if not self.data:
            raise SceneFieldsConfigNotExistException()
        user_obj, created = UserSceneFieldsConfig.objects.get_or_create(
            bk_biz_id=self.data.bk_biz_id,
            username=username,
            scene_id=self.data.scene_id,
            scope=self.data.scope,
            source_app_code=self.source_app_code,
            defaults={"config_id": self.data.id},
        )
        if not created and user_obj.config_id != self.data.id:
            user_obj.config_id = self.data.id
            user_obj.save(update_fields=["config_id", "updated_at"])
        return self.build_applied_template_response(user_obj, self.data, username, self.source_app_code)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _infer_biz_id(self) -> int:
        return self.data.bk_biz_id if self.data else self.bk_biz_id

    def _infer_scene_id(self) -> str:
        return self.data.scene_id if self.data else self.scene_id

    def _infer_scope(self) -> str:
        return self.data.scope if self.data else self.scope

    # ------------------------------------------------------------------
    # User-config read (used by fields_config GET)
    # ------------------------------------------------------------------

    @classmethod
    def get_or_create_default(
        cls,
        bk_biz_id: int,
        scene_id: str,
        scope: str = SearchScopeEnum.DEFAULT.value,
    ) -> SceneFieldsConfig:
        source_app_code = get_request_app_code()
        obj, _ = SceneFieldsConfig.objects.get_or_create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            name=DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
            scope=scope,
            source_app_code=source_app_code,
            defaults={"display_fields": [], "sort_list": []},
        )
        return obj

    @classmethod
    def get_user_applied_config(
        cls,
        bk_biz_id: int,
        username: str,
        scene_id: str,
        scope: str = SearchScopeEnum.DEFAULT.value,
    ) -> tuple[UserSceneFieldsConfig | None, SceneFieldsConfig]:
        """读用户当前应用的模板；无指针则懒创建默认模板（不写指针，保留 first-write 行为给 apply()）。"""
        source_app_code = get_request_app_code()
        user_obj = UserSceneFieldsConfig.objects.filter(
            bk_biz_id=bk_biz_id,
            username=username,
            scene_id=scene_id,
            scope=scope,
            source_app_code=source_app_code,
        ).first()
        if user_obj:
            try:
                tpl = SceneFieldsConfig.objects.get(pk=user_obj.config_id)
                return user_obj, tpl
            except SceneFieldsConfig.DoesNotExist:
                # 指针指向的模板被外部清理：回退到默认模板
                user_obj = None
        tpl = cls.get_or_create_default(bk_biz_id, scene_id, scope)
        return user_obj, tpl

    @classmethod
    def build_applied_template_response(
        cls,
        user_obj: UserSceneFieldsConfig | None,
        tpl: SceneFieldsConfig,
        username: str,
        source_app_code: str,
    ) -> dict:
        """组装"当前应用模板"视图（apply 返回 + list_config 表头使用）。"""
        return {
            "id": user_obj.id if user_obj else None,
            "config_id": tpl.id,
            "username": username,
            "bk_biz_id": tpl.bk_biz_id,
            "scene_id": tpl.scene_id,
            "scope": tpl.scope,
            "source_app_code": source_app_code,
            "name": tpl.name,
            "display_fields": tpl.display_fields or [],
            "sort_list": tpl.sort_list or [],
            "created_at": tpl.created_at,
            "updated_at": tpl.updated_at,
        }


class UserSceneCustomConfigHandler:
    """场景化检索 - 用户 UI 偏好（7 字段 JSON）CRUD，与模板系统完全解耦。

    对标 ``apps.log_search.handlers.index_set.UserIndexSetConfigHandler``：
    存储载体是 ``UserSceneCustomConfig.scene_config``，前端按 camelCase 的完整 JSON
    （``fieldsWidth`` / ``displayFields`` / ``filterSetting`` / ``filterAddition`` /
    ``fixedFilterAddition`` / ``sortList`` / ``contextDisplayFields``）一次性 upsert，
    后端不解析内层结构。
    """

    @classmethod
    def get(
        cls,
        bk_biz_id: int,
        username: str,
        scene_id: str,
        scope: str = SearchScopeEnum.DEFAULT.value,
    ) -> dict:
        source_app_code = get_request_app_code()
        obj = UserSceneCustomConfig.objects.filter(
            bk_biz_id=bk_biz_id,
            username=username,
            scene_id=scene_id,
            scope=scope,
            source_app_code=source_app_code,
        ).first()
        return obj.scene_config if obj else {}

    @classmethod
    def update_or_create(
        cls,
        bk_biz_id: int,
        username: str,
        scene_id: str,
        scope: str,
        scene_config: dict,
    ) -> dict:
        source_app_code = get_request_app_code()
        obj, _ = UserSceneCustomConfig.objects.update_or_create(
            bk_biz_id=bk_biz_id,
            username=username,
            scene_id=scene_id,
            scope=scope,
            source_app_code=source_app_code,
            defaults={"scene_config": scene_config or {}},
        )
        return obj.scene_config or {}

    @classmethod
    def delete(
        cls,
        bk_biz_id: int,
        username: str,
        scene_id: str,
        scope: str = SearchScopeEnum.DEFAULT.value,
    ) -> dict:
        source_app_code = get_request_app_code()
        deleted, _ = UserSceneCustomConfig.objects.filter(
            bk_biz_id=bk_biz_id,
            username=username,
            scene_id=scene_id,
            scope=scope,
            source_app_code=source_app_code,
        ).delete()
        return {"deleted": bool(deleted)}
