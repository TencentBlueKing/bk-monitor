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

from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error, logger


class PermissionDeniedError(Error):
    """
    无权限异常
    """

    status_code = 403
    code = 9900403
    name = _lazy("权限校验不通过")
    message_tpl = _lazy("当前用户无 [{action_name}] 权限")
    popup_message = "primary"  # 报错弹框级别-蓝框


class APIPermissionDeniedError(PermissionDeniedError):
    """
    第三方接口无权限异常
    """

    def __init__(self, context=None, data=None, extra=None, **kwargs):
        permission_actions = []
        extra = extra or {}
        for action in extra.get("permission", {}).get("actions", []):
            action_name = action["name"]
            resource_name = _lazy("无实例")
            related_resources = action.get("related_resource_types", [])
            for resource in related_resources:
                instances = resource.get("instances", [])
                try:
                    resource_name = instances[0][0]["name"]
                    break
                except BaseException as error:
                    logger.error("get related resource name error %s", str(error))
            permission_actions.append("{}-{}".format(action_name, resource_name))
        kwargs.update(permission=",".join(permission_actions))
        super(APIPermissionDeniedError, self).__init__(context, data, extra, **kwargs)

    message_tpl = _lazy("请求[{system_name}]系统[{url}]权限校验不通过，请前往权限中心申请对应权限[{permission}]")


class ActionNotExistError(Error):
    status_code = 400
    code = 3399001
    name = _lazy("动作ID不存在")
    message_tpl = _lazy("动作ID不存在：{action_id}")


class ResourceNotExistError(Error):
    status_code = 400
    code = 3399002
    name = _lazy("资源ID不存在")
    message_tpl = _lazy("资源ID不存在：{resource_id}")
