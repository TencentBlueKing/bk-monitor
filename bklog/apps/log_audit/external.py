"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from dataclasses import dataclass

from bk_audit.constants.log import (
    DEFAULT_EMPTY_VALUE,
    DEFAULT_RESULT_CODE,
    AccessTypeEnum,
    UserIdentifyTypeEnum,
)
from bk_audit.log.models import AuditContext, AuditInstance

from apps.constants import ExternalPermissionActionEnum
from apps.log_audit.client import bk_audit_client
from apps.utils.log import logger

# 审计中心「操作人账号来源」，用于把外部版身份与内部账号区分开
USER_IDENTIFY_SRC = "po_external"

# 审计中心「管理空间类型」
SCOPE_TYPE = "space_uid"

# log_common 对应菜单、全局配置等元数据接口，不涉及日志数据访问，调用量大且无审计价值
IGNORED_ACTION_IDS = frozenset({ExternalPermissionActionEnum.LOG_COMMON.value})


@dataclass
class _AuditId:
    """bk_audit 通过 .id 读取操作与资源类型，这里提供最小载体"""

    id: str


@dataclass
class _AuditInstance:
    """bk_audit 通过 AuditInstance 读取实例属性"""

    instance_id: str
    instance_name: str


def get_access_source_ip(request) -> str:
    """
    从外层请求解析客户端 IP

    转发给业务视图的 fake_request 由 RequestFactory 构造，REMOTE_ADDR 恒为 127.0.0.1，
    只能从外层 request 取值，否则记录到的是错误值而非缺失值。
    """
    if request.META.get("HTTP_X_REAL_IP"):
        return request.META["HTTP_X_REAL_IP"]
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.replace(" ", "").split(",")[0]
    return request.META.get("REMOTE_ADDR", DEFAULT_EMPTY_VALUE)


class ExternalAuditRecorder:
    """
    外部代理请求的审计事件收集器

    内部版靠 apps/log_audit/middleware.py 在 process_response 中按 URL 正则上报，
    而外部请求由 dispatch_external_proxy 直接调用视图函数，不经过中间件，故单独埋点。
    转发入口存在多个鉴权提前返回分支，调用方需在 finally 中调用 push()，保证拒绝事件同样留痕。
    """

    def __init__(self, request):
        self.request = request
        self.external_user = DEFAULT_EMPTY_VALUE
        self.authorizer = DEFAULT_EMPTY_VALUE
        self.space_uid = DEFAULT_EMPTY_VALUE
        self.action_id = DEFAULT_EMPTY_VALUE
        self.view_set = DEFAULT_EMPTY_VALUE
        self.view_action = DEFAULT_EMPTY_VALUE
        self.resource = None
        self.result_code = DEFAULT_RESULT_CODE
        self.result_content = DEFAULT_EMPTY_VALUE

    def set_result(self, result_code: int, result_content: str):
        self.result_code = result_code
        self.result_content = result_content

    def push(self):
        """审计上报失败不能影响外部用户的正常请求"""
        try:
            self._push()
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                f"[external_audit] 上报审计事件失败, external_user: {self.external_user}, action_id: {self.action_id}"
            )

    def _push(self):
        # action_id 为空说明 URL 未解析成功，没有可归属的操作；username 为空则失去审计意义。
        # 两者也都是 AuditEvent 的必填校验项，为空会直接抛 AssertionError
        if not self.action_id or not self.external_user:
            return
        # 元数据类接口只有成功访问才忽略，被拒绝的访问一律留痕
        if self.result_code == DEFAULT_RESULT_CODE and self.action_id in IGNORED_ACTION_IDS:
            return
        # 不传 request，避免 DjangoFormatter 用授权人覆写 username 等字段
        context = AuditContext(
            username=self.external_user,
            user_identify_type=UserIdentifyTypeEnum.PERSONAL,
            user_identify_src=USER_IDENTIFY_SRC,
            user_identify_src_username=self.authorizer,
            scope_type=SCOPE_TYPE,
            scope_id=self.space_uid,
            access_type=AccessTypeEnum.WEB,
            access_source_ip=get_access_source_ip(self.request),
            access_user_agent=self.request.META.get("HTTP_USER_AGENT", DEFAULT_EMPTY_VALUE),
            request_id=getattr(self.request, "request_id", DEFAULT_EMPTY_VALUE),
        )
        instance_id = str(self.resource) if self.resource else DEFAULT_EMPTY_VALUE
        bk_audit_client.add_event(
            action=_AuditId(self.action_id),
            resource_type=_AuditId(self.view_set),
            instance=AuditInstance(_AuditInstance(instance_id=instance_id, instance_name=instance_id)),
            audit_context=context,
            event_content=f"{self.view_set}.{self.view_action}",
            result_code=self.result_code,
            result_content=self.result_content,
            extend_data={
                "view_set": self.view_set,
                "view_action": self.view_action,
                "authorizer": self.authorizer,
                "space_uid": self.space_uid,
            },
        )
        bk_audit_client.export_events()
