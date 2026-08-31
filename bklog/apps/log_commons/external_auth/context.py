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

from dataclasses import dataclass, field
from typing import Any

from apps.iam import Permission
from apps.utils.local import get_request_tenant_id


@dataclass(frozen=True)
class IdentityContext:
    """外部访问链路上的三种身份。

    这三者在 PO 场景下不是同一个人，混用任意两个都会造成越权或审计失真：
    - authorization_subject：判权主体，外部用户本人；
    - execution_user：下游视图实际执行的内部授权人，代理仍以它登录；
    - audit_user：审计留痕对象，必须是外部用户，否则查不到真实操作人。

    bk_tenant_id 是必填字段而不是让调用方各自补：apps.iam.handlers.permission.Permission
    只有在 username 与 bk_tenant_id 同时给出时才认显式身份，否则会回落到线程内已登录的
    授权人，判权主体会被静默换掉。
    """

    authorization_subject: str
    execution_user: str
    audit_user: str
    bk_tenant_id: str

    @classmethod
    def for_external_request(
        cls,
        external_user: str,
        authorizer: str,
        bk_tenant_id: str = "",
    ) -> "IdentityContext":
        return cls(
            authorization_subject=external_user,
            execution_user=authorizer,
            audit_user=external_user,
            bk_tenant_id=bk_tenant_id or get_request_tenant_id(),
        )

    def permission_for_subject(self) -> Permission:
        """构造以判权主体发起的权限中心客户端。

        接入 IAM 的来源一律走这里，不要自行 new Permission：代理链路在鉴权之后才把请求登录成
        内部授权人，但线程内可能已经存在其它已登录请求，只传 username 会被静默替换成那个用户。
        """
        return Permission(username=self.authorization_subject, bk_tenant_id=self.bk_tenant_id)


@dataclass(frozen=True)
class ExternalRequestContext:
    """一次外部代理请求中，鉴权需要用到的全部输入。

    declared_action_id 由接口自身的视图映射解析，与外部用户持有哪些授权项无关；
    命中的授权项另由 SourceResult.matched_action_id 表达。两者分开是为了让审计在
    「新侧放行但没有旧票」时仍能定位到操作类型。
    """

    identity: IdentityContext
    space_uid: str
    view_set: str
    view_action: str
    declared_action_id: str
    url_kwargs: dict[str, Any] = field(default_factory=dict)
    json_data_str: str = ""

    @property
    def external_user(self) -> str:
        return self.identity.authorization_subject
