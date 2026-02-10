from typing import Any

from bk_monitor_base.strategy import UserGroupType
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.models.strategy import NoticeSubscribe
from core.drf_resource import Resource


class SaveStrategySubscribeResource(Resource):
    """
    新增/保存策略订阅
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False)
        sub_username = serializers.CharField(required=True, source="username")
        bk_biz_id = serializers.IntegerField(required=True)
        conditions = serializers.ListField(required=True, child=serializers.DictField())
        notice_ways = serializers.ListField(required=True, child=serializers.CharField())
        priority = serializers.IntegerField(required=False, default=-1)
        user_type = serializers.ChoiceField(
            required=False, choices=UserGroupType.CHOICE, default=UserGroupType.FOLLOWER
        )
        is_enable = serializers.BooleanField(required=False, default=True)

    def perform_request(self, validated_request_data: dict[str, Any]):
        sub_id = validated_request_data.get("id")
        bk_biz_id = validated_request_data["bk_biz_id"]
        if sub_id:
            try:
                instance = NoticeSubscribe.objects.get(id=sub_id, bk_biz_id=bk_biz_id)
                for k, v in validated_request_data.items():
                    setattr(instance, k, v)
                instance.save()
            except NoticeSubscribe.DoesNotExist:
                raise ValidationError(_(f"订阅ID：{sub_id} 在业务[{bk_biz_id}] 下不存在"))
        else:
            instance = NoticeSubscribe.objects.create(**validated_request_data)

        return {
            "id": instance.id,
            "username": instance.username,
            "bk_biz_id": instance.bk_biz_id,
            "conditions": instance.conditions,
            "notice_ways": instance.notice_ways,
            "priority": instance.priority,
            "user_type": instance.user_type,
            "is_enable": instance.is_enable,
        }


class BulkSaveStrategySubscribeResource(Resource):
    """
    批量创建订阅
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        subscriptions = serializers.ListField(required=True, child=SaveStrategySubscribeResource.RequestSerializer())

    def perform_request(self, validated_request_data: dict[str, Any]):
        subscriptions = validated_request_data["subscriptions"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        to_be_created = []
        to_be_updated = []
        update_subs = {}
        filter_dict = {"bk_biz_id": bk_biz_id, "id__in": []}

        for sub in subscriptions:
            sub_id = sub.get("id")
            if sub_id:
                filter_dict["id__in"].append(sub_id)
                update_subs[sub_id] = sub
            else:
                # 确保新创建的订阅包含 bk_biz_id
                sub_data = sub.copy()
                sub_data["bk_biz_id"] = bk_biz_id
                to_be_created.append(NoticeSubscribe(**sub_data))

        # 只有当有需要更新的订阅时才执行查询
        if filter_dict["id__in"]:
            for sub in NoticeSubscribe.objects.filter(**filter_dict):
                sub_data = update_subs[sub.id]
                for k, v in sub_data.items():
                    if k != "id":  # 跳过id字段
                        setattr(sub, k, v)
                to_be_updated.append(sub)

        with transaction.atomic():
            if to_be_created:
                NoticeSubscribe.objects.bulk_create(to_be_created)
            if to_be_updated:
                # 动态获取需要更新的字段
                update_fields = ["username", "conditions", "notice_ways", "priority", "user_type", "is_enable"]
                NoticeSubscribe.objects.bulk_update(to_be_updated, update_fields)

        return {"created": len(to_be_created), "updated": len(to_be_updated)}


class BulkDeleteStrategySubscribeResource(Resource):
    """
    批量删除/取消策略订阅
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(
            child=serializers.IntegerField(), required=True, allow_empty=False, help_text="要删除的订阅ID列表"
        )
        bk_biz_id = serializers.IntegerField(required=True)
        sub_username = serializers.CharField(required=False, source="username", default="")

    def perform_request(self, validated_request_data: dict[str, Any]):
        ids = validated_request_data["ids"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 查询要删除的订阅记录
        qs = NoticeSubscribe.objects.filter(id__in=ids, bk_biz_id=bk_biz_id)
        if validated_request_data["username"]:
            qs = qs.filter(username=validated_request_data["username"])

        # 获取实际存在的订阅ID，用于返回结果
        existing_ids = list(qs.values_list("id", flat=True))

        # 执行批量删除
        deleted_count, __ = qs.delete()

        # 检查是否有未找到的订阅ID
        not_found_ids = [id for id in ids if id not in existing_ids]

        if deleted_count == 0:
            raise ValidationError(_("删除失败：未找到符合条件的订阅"))

        result = {
            "deleted_count": deleted_count,
            "deleted_ids": existing_ids,
        }

        # 如果有部分ID未找到，添加到返回结果中
        if not_found_ids:
            result["not_found_ids"] = not_found_ids
            result["message"] = _("部分订阅删除成功，但以下ID未找到：{}").format(", ".join(map(str, not_found_ids)))

        return result


class DeleteStrategySubscribeResource(Resource):
    """
    删除/取消单个策略订阅（向后兼容接口）
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        sub_username = serializers.CharField(required=False, source="username", default="")

    def perform_request(self, validated_request_data: dict[str, Any]):
        # 复用批量删除的逻辑
        batch_params = {
            "ids": [validated_request_data["id"]],
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "sub_username": validated_request_data["username"],
        }

        # 调用批量删除资源
        batch_resource = BulkDeleteStrategySubscribeResource()
        result = batch_resource.perform_request(batch_params)

        # 如果有未找到的ID，说明删除失败
        if "not_found_ids" in result:
            raise ValidationError(_("删除失败：未找到符合条件的订阅"))

        return True


class ListStrategySubscribeResource(Resource):
    """
    策略订阅列表
    """

    class RequestSerializer(serializers.Serializer):
        sub_username = serializers.CharField(required=False, source="username")
        bk_biz_id = serializers.IntegerField(required=True)
        is_enable = serializers.BooleanField(required=False, default=True)
        page = serializers.IntegerField(required=False, default=1, min_value=1)
        page_size = serializers.IntegerField(required=False, default=100, min_value=1, max_value=500)

    def perform_request(self, validated_request_data: dict[str, Any]):
        # 只使用经过验证的字段进行过滤，避免潜在的安全风险
        filter_params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
        }
        if validated_request_data.get("username", ""):
            filter_params["username"] = validated_request_data["username"]

        # 可选的is_enable过滤
        if "is_enable" in validated_request_data:
            filter_params["is_enable"] = validated_request_data["is_enable"]

        # 分页参数
        page = validated_request_data.get("page", 1)
        page_size = validated_request_data.get("page_size", 100)
        offset = (page - 1) * page_size

        # 查询数据
        qs = NoticeSubscribe.objects.filter(**filter_params).order_by("priority", "id")

        # 获取总数和分页数据
        total_count = qs.count()
        paginated_qs = qs[offset : offset + page_size]

        return {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "results": [
                {
                    "id": obj.id,
                    "username": obj.username,
                    "bk_biz_id": obj.bk_biz_id,
                    "conditions": obj.conditions,
                    "notice_ways": obj.notice_ways,
                    "priority": obj.priority,
                    "user_type": obj.user_type,
                    "is_enable": obj.is_enable,
                }
                for obj in paginated_qs
            ],
        }


class DetailStrategySubscribeResource(Resource):
    """
    策略订阅详情
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]
        obj = NoticeSubscribe.objects.filter(id=validated_request_data["id"], bk_biz_id=bk_biz_id).first()
        if not obj:
            raise ValidationError(_(f"[{bk_biz_id}]下未找到符合条件的订阅"))
        return {
            "id": obj.id,
            "username": obj.username,
            "bk_biz_id": obj.bk_biz_id,
            "conditions": obj.conditions,
            "notice_ways": obj.notice_ways,
            "priority": obj.priority,
            "user_type": obj.user_type,
            "is_enable": obj.is_enable,
        }
