# -*- coding: utf-8 -*-
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
from collections import defaultdict
from datetime import datetime
from functools import partial
from secrets import token_hex

from bkmonitor.iam.permission import ActionIdMap, Permission
from bkmonitor.models import ApiAuthToken, TokenAccessRecord
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from core.drf_resource import Resource
from core.errors.share import TokenDeletedError, TokenExpiredError, TokenValidatedError

logger = logging.getLogger("monitor_web")

type_prefix_map = {
    "scene_plugin_": "scene_collect",
    "scene_custom_metric_": "scene_custom_metric",
    "scene_custom_event_": "scene_custom_event",
    "collect_": "collect",
    "apm_": "apm",
    "custom_metric_": "custom_metric",
    "custom_event_": "custom_event",
}


def get_token_type(token_type):
    for prefix, new_prefix in type_prefix_map.items():
        if token_type.startswith(prefix):
            token_type = new_prefix
    return token_type


class CreateShareTokenResource(Resource):
    """
    创建临时分享鉴权token
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        type = serializers.CharField(required=True, label="鉴权类型")
        expire_time = serializers.IntegerField(required=True, label="过期时间")
        expire_period = serializers.CharField(required=True, label="有效期")
        lock_search = serializers.BooleanField(required=False, default=False, label="是否锁定查询时间")
        default_time_range = serializers.ListField(required=False, default=[], label="默认时间范围")
        start_time = serializers.IntegerField(required=False, default=None, label="开始时间")
        end_time = serializers.IntegerField(required=False, default=None, label="结束时间")
        data = serializers.DictField(required=False, default={}, label="鉴权参数")

    def perform_request(self, validated_request_data):
        # 获取当前租户
        bk_tenant_id = get_request_tenant_id()

        # 创建唯一token，长度8位
        exist_tokens = list(
            ApiAuthToken.origin_objects.filter(bk_tenant_id=bk_tenant_id).values_list("token", flat=True).distinct()
        )
        token = partial(token_hex, 8)()
        while token in exist_tokens:
            token = partial(token_hex, 8)()
        # 自定义场景、apm、采集视图 类型解析处理
        name = validated_request_data["type"]
        token_type = get_token_type(validated_request_data["type"])
        create_params = {
            "bk_tenant_id": bk_tenant_id,
            "namespaces": [f"biz#{validated_request_data['bk_biz_id']}"],
            "name": str(f"{name}_" + str(datetime.now())),
            "type": token_type,
            "token": token,
            "expire_time": datetime.fromtimestamp(validated_request_data["expire_time"]),
            "params": {
                "lock_search": validated_request_data["lock_search"],
                "start_time": validated_request_data["start_time"],
                "end_time": validated_request_data["end_time"],
                "default_time_range": validated_request_data["default_time_range"],
                "expire_period": validated_request_data["expire_period"],
                "data": validated_request_data["data"],
            },
        }
        token_obj = ApiAuthToken.objects.create(**create_params)
        return {"token": token_obj.token, "expire_time": int(token_obj.expire_time.timestamp()), **token_obj.params}


class UpdateShareTokenResource(Resource):
    """
    更新临时分享鉴权token配置
    """

    class RequestSerializer(serializers.Serializer):
        token = serializers.CharField(required=True, label="鉴权令牌")
        expire_time = serializers.IntegerField(required=False, label="过期时间")
        expire_period = serializers.CharField(required=False, label="有效期")
        lock_search = serializers.BooleanField(required=False, label="是否锁定查询时间")
        default_time_range = serializers.ListField(required=False, default=[], label="默认时间范围")
        start_time = serializers.IntegerField(required=False, default=None, label="开始时间")
        end_time = serializers.IntegerField(required=False, default=None, label="结束时间")
        data = serializers.DictField(required=False, label="鉴权参数")

    def perform_request(self, validated_request_data):
        try:
            token_obj = ApiAuthToken.origin_objects.get(
                bk_tenant_id=get_request_tenant_id(), token=validated_request_data["token"]
            )
            # token被收回校验
            if token_obj.is_deleted:
                raise TokenDeletedError({"username": token_obj.update_user})
            # token过期校验
            if token_obj.is_expired():
                raise TokenExpiredError
        except ApiAuthToken.DoesNotExist:
            raise TokenValidatedError
        if validated_request_data.get("expire_time") and validated_request_data.get("expire_period"):
            token_obj.expire_time = datetime.fromtimestamp(validated_request_data["expire_time"])
            token_obj.params["expire_period"] = validated_request_data["expire_period"]
        if validated_request_data.get("lock_search", None) is not None:
            token_obj.params["lock_search"] = validated_request_data["lock_search"]
            token_obj.params["start_time"] = validated_request_data["start_time"]
            token_obj.params["end_time"] = validated_request_data["end_time"]
            token_obj.params["default_time_range"] = validated_request_data["default_time_range"]
        if validated_request_data.get("data"):
            token_obj.params["data"] = validated_request_data["data"]
        token_obj.save()
        return {"token": token_obj.token, "expire_time": int(token_obj.expire_time.timestamp()), **token_obj.params}


class GetShareParamsResource(Resource):
    """
    获取临时分享鉴权token参数
    """

    class RequestSerializer(serializers.Serializer):
        token = serializers.CharField(required=True, label="鉴权令牌")

    def perform_request(self, validated_request_data):
        try:
            token_obj = ApiAuthToken.origin_objects.get(
                bk_tenant_id=get_request_tenant_id(), token=validated_request_data["token"]
            )
            # token被收回校验
            if token_obj.is_deleted:
                raise TokenDeletedError({"username": token_obj.update_user})
            # token过期校验
            if token_obj.is_expired():
                raise TokenExpiredError
            bk_biz_id = [namespace[4:] for namespace in token_obj.namespaces if namespace.startswith("biz#")][0]
            # 绕过token鉴权,获取该用户是否有相关权限
            request = get_request(peaceful=True)
            if request:
                has_permission = True
                request.token = None
                for action in ActionIdMap[token_obj.type]:
                    if not Permission().is_allowed_by_biz(bk_biz_id=bk_biz_id, action=action):
                        has_permission = False
                        TokenAccessRecord.objects.update_or_create(
                            defaults={"update_time": datetime.now()},
                            create_user=get_global_user() or "unknown",
                            token=token_obj.token,
                        )
                        break
            else:
                # request获取失败默认无权限，展示分享界面
                has_permission = False

            return {
                "has_permission": has_permission,
                "token": token_obj.token,
                "type": token_obj.type,
                "expire_time": int(token_obj.expire_time.timestamp()),
                **token_obj.params,
            }
        except ApiAuthToken.DoesNotExist:
            raise TokenValidatedError


class GetShareTokenListResource(Resource):
    """
    获取该场景下所有临时分享鉴权token
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        type = serializers.CharField(required=True, label="鉴权类型")
        scene_params = serializers.DictField(required=False, label="场景参数")
        filter_params = serializers.DictField(required=False, label="目标参数")

    def get_params(self, params):
        filter_params = set()
        scene_params = set()
        for key, value in params.get("data", {}).get("query", {}).items():
            if key.startswith("filter-"):
                new_key = key[7:]
                filter_params.add((new_key, value))
            if key in ["sceneId", "sceneType", "dashboardId"]:
                scene_params.add((key, value))
        return filter_params, scene_params

    def get_access_record_dict(self, tokens):
        access_record_dict = defaultdict(lambda: {"total": 0, "data": []})
        access_records = TokenAccessRecord.objects.filter(token__in=tokens).values(
            "token", "create_user", "update_time"
        )
        for record in list(access_records):
            record_info = access_record_dict[record["token"]]
            record_info["total"] += 1
            record_info["data"].append({"visitor": record["create_user"], "last_time": record["update_time"]})
        return access_record_dict

    def get_token_status(self, token):
        if token.is_deleted:
            return "is_deleted"
        elif token.is_expired():
            return "is_expired"
        else:
            return "is_enabled"

    def perform_request(self, validated_request_data):
        token_type = get_token_type(validated_request_data["type"])
        token_list = []
        tokens = ApiAuthToken.origin_objects.filter(
            bk_tenant_id=get_request_tenant_id(),
            namespaces=[f"biz#{validated_request_data['bk_biz_id']}"],
            type=token_type,
        ).order_by("-create_time")
        access_record_dict = self.get_access_record_dict(tokens.values_list("token", flat=True))
        for token in tokens:
            if validated_request_data.get("scene_params", None) and validated_request_data.get("filter_params", None):
                filter_params, scene_params = self.get_params(token.params)
                if not (
                    set(validated_request_data["scene_params"].items()).issubset(scene_params)
                    and set(validated_request_data["filter_params"].items()).issubset(filter_params)
                ):
                    continue
            time_range_params = {k: v for k, v in token.params.items() if k != "data"}
            token_list.append(
                {
                    "token": token.token,
                    "expire_time": int(token.expire_time.timestamp()),
                    "status": self.get_token_status(token),
                    "access_info": access_record_dict[token.token],
                    "create_time": token.create_time,
                    "create_user": token.create_user,
                    "params_info": [{"name": "time_range", **time_range_params}],
                }
            )
        return token_list


class DeleteShareTokenResource(Resource):
    """
    回收该场景下指定临时分享鉴权token
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        type = serializers.CharField(required=True, label="鉴权类型")
        tokens = serializers.ListField(
            required=True, child=serializers.CharField(), label="鉴权token列表", allow_empty=False
        )

    def perform_request(self, validated_request_data):
        token_type = get_token_type(validated_request_data["type"])
        username = get_global_user() or "unknown"
        if token_type.startswith("scene_"):
            token_types = [
                type_prefix for _, type_prefix in type_prefix_map.items() if type_prefix.startswith("scene_")
            ]
        else:
            token_types = [token_type]
        return ApiAuthToken.objects.filter(
            bk_tenant_id=get_request_tenant_id(),
            namespaces=[f"biz#{validated_request_data['bk_biz_id']}"],
            type__in=token_types,
            token__in=validated_request_data["tokens"],
        ).update(is_deleted=True, is_enabled=False, update_user=username, update_time=datetime.now())
