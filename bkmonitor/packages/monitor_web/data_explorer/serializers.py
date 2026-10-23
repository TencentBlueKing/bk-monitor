"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import collections

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request
from bkmonitor.utils.user import get_global_user
from monitor_web.models import FavoriteGroup, QueryHistory


class BaseFavoriteGroupListSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    type = serializers.CharField(label="检索类型")


class FavoriteGroupSerializer(serializers.ModelSerializer):
    editable = serializers.BooleanField(default=True)

    class Meta:
        model = FavoriteGroup
        fields = ["id", "name", "editable"]

    def update(self, instance, validated_data):
        if validated_data.get("name"):
            # 重名检查
            if (
                instance.name != validated_data["name"]
                and FavoriteGroup.objects.filter(
                    bk_biz_id=instance.bk_biz_id, type=instance.type, name=validated_data["name"]
                ).exists()
            ):
                raise ValidationError(_("收藏组({})名称重复").format(validated_data["name"]))

            instance.name = validated_data["name"]

        if validated_data.get("order") is not None:
            instance.order = validated_data["order"]

        instance.save()
        return instance


class GetFavoriteGroupListSerializer(BaseFavoriteGroupListSerializer):
    """
    获取收藏组列表参数
    """

    query = serializers.CharField(label="查询字段", default="")


class CreateFavoriteGroupSerializer(BaseFavoriteGroupListSerializer):
    """
    创建收藏组参数
    """

    name = serializers.CharField(label="查询字段")

    def validate(self, attrs):
        # 保留名称校验
        if attrs in [_("未分组"), _("个人收藏"), "未分组", "个人收藏"]:
            raise ValidationError(_("保留名称，不可使用"))

        # 重名校验
        if FavoriteGroup.objects.filter(bk_biz_id=attrs["bk_biz_id"], type=attrs["type"], name=attrs["name"]).exists():
            raise ValidationError(_("收藏组({})名称重复").format(attrs["name"]))
        return attrs


class UpdateFavoriteGroupSerializer(BaseFavoriteGroupListSerializer):
    """
    更新收藏组参数
    """

    name = serializers.CharField(label="查询字段", required=False)
    order = serializers.ListField(label="排序配置", default=[], required=False, child=serializers.IntegerField())

    def validate(self, attrs):
        # 保留名称校验
        if attrs.get("name") in [_("未分组"), _("个人收藏"), "未分组", "个人收藏"]:
            raise ValidationError(_("保留名称，不可使用"))
        return attrs


class UpdateFavoriteGroupOrderSerializer(BaseFavoriteGroupListSerializer):
    """
    更新收藏组排序
    """

    order = serializers.ListField(label="排序配置", default=[], required=False, child=serializers.IntegerField())


class FavoriteSerializer(serializers.ModelSerializer):
    config = serializers.JSONField()

    def get_config(self, obj):
        return obj.config

    class Meta:
        model = QueryHistory
        fields = ("id", "name", "config", "group_id", "create_user", "update_user", "update_time")

    @staticmethod
    def _get_existing_names(biz_ids: set[int], query_types: set[str], names: set[str]) -> set[tuple]:
        """一次查出给定业务、检索类型下已被占用的名称，返回 (bk_biz_id, type, name) 集合"""
        if not biz_ids or not query_types or not names:
            return set()
        return set(
            QueryHistory.objects.filter(bk_biz_id__in=biz_ids, type__in=query_types, name__in=names).values_list(
                "bk_biz_id", "type", "name"
            )
        )

    @staticmethod
    def _apply_changes(
        instance, validated_data: dict, existing_names: set[tuple], pending_names: set[tuple] | None = None
    ) -> set[str]:
        """校验并就地修改 instance，不落库，返回本次实际变更的字段名集合"""
        name = validated_data.get("name")
        name_changed = "name" in validated_data and name != instance.name
        group_changed = "group_id" in validated_data and validated_data["group_id"] != instance.group_id
        config_changed = "config" in validated_data
        if not (name_changed or group_changed or config_changed):
            return set()

        changed_fields = set()
        if name:
            name_key = (instance.bk_biz_id, instance.type, name)
            # 名称已被其他记录占用，或同一批内重复改名
            name_conflict = name_key in existing_names or (pending_names is not None and name_key in pending_names)
            if instance.name != name and name_conflict:
                raise ValidationError(_("收藏记录({})名称重复").format(name))
            if pending_names is not None:
                pending_names.add(name_key)
            if name_changed:
                instance.name = name
                changed_fields.add("name")

        if config_changed:
            instance.config = validated_data["config"]
            changed_fields.add("config")

        if group_changed:
            request = get_request()
            if instance.create_user != request.user.username and validated_data["group_id"] == 0:
                raise ValidationError(_("只有创建者才能将收藏记录移动到个人收藏"))

            instance.group_id = validated_data["group_id"]
            changed_fields.add("group_id")

        # bulk_update 不会触发 Model.save()，审计字段需要手动维护
        instance.update_user = get_global_user() or "system"
        instance.update_time = timezone.now()
        changed_fields.update({"update_user", "update_time"})
        return changed_fields

    def update(self, instance, validated_data):
        name = validated_data.get("name")
        existing_names = self._get_existing_names({instance.bk_biz_id}, {instance.type}, {name} if name else set())
        if not self._apply_changes(instance, validated_data, existing_names):
            return instance

        instance.save()
        return instance

    @classmethod
    def bulk_update(cls, instances: dict[int, QueryHistory], configs: list[dict]) -> int:
        """
        批量更新收藏记录，返回实际更新条数

        :param instances: {收藏ID: 实例}，由调用方按权限范围查询后传入
        :param configs: 待更新配置列表，元素包含 id，可选 name、group_id
        """
        # 重名检查：只查一次，覆盖所有涉及的业务与检索类型，避免遗漏
        existing_names = set()
        rename_names = {config["name"] for config in configs if config.get("name")}
        if instances and rename_names:
            existing_names = cls._get_existing_names(
                {instance.bk_biz_id for instance in instances.values()},
                {instance.type for instance in instances.values()},
                rename_names,
            )

        pending_names: set[tuple] = set()
        to_update = []
        # 字段列表由 _apply_changes 返回，避免把未变更的字段（如大字段 config）写进 CASE WHEN
        update_fields: set[str] = set()

        for config in configs:
            instance = instances.get(config["id"])
            if instance is None:
                continue

            changed_fields = cls._apply_changes(instance, config, existing_names, pending_names)
            if changed_fields:
                update_fields |= changed_fields
                to_update.append(instance)

        if to_update:
            QueryHistory.objects.bulk_update(to_update, sorted(update_fields))
        return len(to_update)


class GetFavoriteListSerializer(BaseFavoriteGroupListSerializer):
    """
    获取收藏列表
    """

    query = serializers.CharField(label="查询字段", default="")
    group_id = serializers.IntegerField(label="收藏组ID", required=False, allow_null=True)
    order_type = serializers.ChoiceField(
        choices=(("asc", _("按名称A-Z")), ("desc", "按名称Z-A"), ("update", "按更新时间")), default="asc"
    )


class CreateFavoriteSerializer(BaseFavoriteGroupListSerializer):
    """
    创建收藏
    """

    name = serializers.CharField(label="收藏名")
    config = serializers.JSONField(label="收藏配置")
    group_id = serializers.IntegerField(label="收藏组ID", allow_null=True, default=None)

    def validate(self, attrs):
        # 重名校验
        if QueryHistory.objects.filter(bk_biz_id=attrs["bk_biz_id"], type=attrs["type"], name=attrs["name"]).exists():
            raise ValidationError(_("收藏记录({})名称重复").format(attrs["name"]))

        # 分组校验
        group_id = attrs["group_id"]
        if (
            group_id
            and not FavoriteGroup.objects.filter(bk_biz_id=attrs["bk_biz_id"], type=attrs["type"], id=group_id).exists()
        ):
            raise ValidationError(_("收藏组({})不存在").format(group_id))

        return attrs


class UpdateFavoriteSerializer(BaseFavoriteGroupListSerializer):
    """
    更新收藏
    """

    name = serializers.CharField(label="收藏名", required=False)
    config = serializers.JSONField(label="收藏配置", required=False)
    group_id = serializers.IntegerField(label="收藏组ID", required=False, allow_null=True)

    def validate(self, attrs):
        # 分组校验
        group_id = attrs.get("group_id")
        if (
            group_id
            and not FavoriteGroup.objects.filter(bk_biz_id=attrs["bk_biz_id"], type=attrs["type"], id=group_id).exists()
        ):
            raise ValidationError(_("收藏组({})不存在").format(group_id))
        return attrs


class BulkUpdateFavoriteSerializer(BaseFavoriteGroupListSerializer):
    """
    批量创建/更新收藏
    """

    class SubSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="收藏ID")
        name = serializers.CharField(label="收藏名", required=False)
        group_id = serializers.IntegerField(label="收藏组ID", required=False, allow_null=True)

    configs = serializers.ListField(label="配置列表", child=SubSerializer())

    @classmethod
    def check_group_exists(cls, attrs):
        """
        查询收藏组是否存在
        """
        group_ids = {config["group_id"] for config in attrs["configs"] if config.get("group_id")}
        if not group_ids:
            return

        exists_group_ids = set(
            FavoriteGroup.objects.filter(
                bk_biz_id=attrs["bk_biz_id"], type=attrs["type"], id__in=group_ids
            ).values_list("id", flat=True)
        )
        not_exists_group_id = group_ids - set(exists_group_ids)
        if not_exists_group_id:
            raise ValidationError(
                _("收藏组({})不存在").format(",".join([str(group_id) for group_id in not_exists_group_id]))
            )

    @classmethod
    def check_duplicate_name(cls, attrs: dict):
        """
        重名检查
        """
        # 找到本次修改了名称的收藏
        changed_name_favorite_ids = [config["id"] for config in attrs["configs"] if config.get("name")]
        changed_names = [config["id"] for config in attrs["configs"] if config.get("name")]

        # 判断修改的名称是否重复
        duplicate_names = [item for item, count in collections.Counter(changed_names).items() if count > 1]
        if duplicate_names:
            raise ValidationError(_("收藏记录({})名称重复").format(",".join(duplicate_names)))

        # 查询其他的收藏配置名称
        existed_names = (
            QueryHistory.objects.filter(bk_biz_id=attrs["bk_biz_id"], type=attrs["type"])
            .exclude(id__in=changed_name_favorite_ids)
            .values_list("name", flat=True)
        )

        # 判断修改的名称是否与存量名称重复
        duplicate_names = set(changed_names) & set(existed_names)
        if duplicate_names:
            raise ValidationError(_("收藏记录({})名称重复").format(",".join(duplicate_names)))

    def validate(self, attrs):
        self.check_group_exists(attrs)
        self.check_duplicate_name(attrs)
        return attrs


class BulkDeleteFavoriteSerializer(BaseFavoriteGroupListSerializer):
    """
    批量删除收藏
    """

    ids = serializers.ListField(label="收藏ID列表", child=serializers.IntegerField())


class ShareFavoriteSerializer(BaseFavoriteGroupListSerializer):
    """
    分享收藏
    """

    share_bk_biz_ids = serializers.ListField(label="分享的业务ID列表", child=serializers.IntegerField())
    # 重名处理模式: 覆盖/跳过/创建副本
    duplicate_mode = serializers.ChoiceField(
        label="重名处理模式",
        choices=(("overwrite", "覆盖"), ("skip", "跳过"), ("copy", "创建副本")),
        default="skip",
    )
    name = serializers.CharField(label="分享收藏名称")
    config = serializers.JSONField(label="分享收藏配置")


class QueryHistorySerializer(serializers.ModelSerializer):
    config = serializers.JSONField()

    class Meta:
        model = QueryHistory
        fields = ["id", "name", "config", "type", "bk_biz_id"]


class QueryHistoryListQuerySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True)
    type = serializers.ChoiceField(default="time_series", choices=["time_series", "event", "trace"])
