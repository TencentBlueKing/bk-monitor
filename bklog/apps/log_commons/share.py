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
from datetime import datetime
from functools import partial
from secrets import token_hex

from apps.iam import Permission, ActionEnum, ResourceEnum
from apps.log_commons.exceptions import TokenDeletedException, TokenExpiredException, TokenValidatedException
from apps.log_commons.models import ApiAuthToken, TokenAccessRecord
from apps.utils.local import get_request_tenant_id, get_request, get_request_username

ShareAuthMap = {
    # 日志检索
    "search": [{
        "action": ActionEnum.SEARCH_LOG,
        "resource": ResourceEnum.INDICES,
        "instance_id": "index_set_id"
    }]
}


class ShareHandler:
    @staticmethod
    def create_or_update(data):
        if data.get("token"):
            token = data["token"]
        else:
            # 创建唯一token，长度8位
            exist_tokens = list(
                ApiAuthToken.objects.all().values_list("token", flat=True).distinct()
            )
            token = partial(token_hex, 8)()
            while token in exist_tokens:
                token = partial(token_hex, 8)()
        create_params = {
            "space_uid": data["space_uid"],
            "type": data["type"],
            "token": token,
            "expire_time": datetime.fromtimestamp(data["expire_time"]),
            "params": {
                "lock_search": data["lock_search"],
                "start_time": data["start_time"],
                "end_time": data["end_time"],
                "default_time_range": data["default_time_range"],
                "expire_period": data["expire_period"],
                "data": data["data"],
            },
        }
        token_obj = ApiAuthToken.objects.update_or_create(**create_params)
        return {"token": token_obj.token, "expire_time": int(token_obj.expire_time.timestamp()), **token_obj.params}

    @staticmethod
    def get_share_params(token):
        try:
            token_obj = ApiAuthToken.objects.get(token=token)
            # token过期校验
            if token_obj.is_expired():
                raise TokenExpiredException
            space_uid = token_obj.space_uid
            # 判定该用户是否有相关权限
            request = get_request(peaceful=True)
            if request:
                has_permission = True
                request.token = None
                for auth_instance in ShareAuthMap[token_obj.type]:
                    resource = auth_instance["resource"]
                    instance_id = token_obj.params["data"].get(auth_instance["instance_id"], None)
                    action = auth_instance["action"]
                    attribute = {
                        "space_uid": space_uid,
                    }
                    permission_result = Permission(username=get_request_username()).is_allowed(
                        action=action, resources=[
                            resource.create_simple_instance(instance_id=instance_id, attribute=attribute)
                        ])
                    if not permission_result:
                        has_permission = False
                        TokenAccessRecord.objects.update_or_create(
                            defaults={"updated_at": datetime.now()},
                            created_by=get_request_username() or "unknown",
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
            raise TokenValidatedException
