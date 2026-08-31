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

# 空间级访问的接入点。
#
# 页面入口和空间列表接口回答的是「这个外部用户能进哪些空间」，粒度比 authorize() 的接口级判定更粗，
# 也早于任何 view_set/action 信息，所以单独成一条链路而不是复用 AuthSource。
# 形状与 AuthSource 保持一致：来源之间取并集，接入新来源不需要改调用方。

from typing import Protocol, runtime_checkable

from apps.log_commons.external_auth.context import IdentityContext
from apps.log_commons.external_auth.decision import DecisionSource
from apps.log_commons.models import ExternalPermission


@runtime_checkable
class SpaceAccessSource(Protocol):
    """一条空间级访问依据。"""

    name: DecisionSource

    def list_space_actions(self, identity: IdentityContext) -> dict[str, list[str]]:
        """返回空间到授权项列表的映射。"""

    def list_space_uids(self, identity: IdentityContext) -> list[str]:
        """返回可访问的空间列表。"""

    def has_access(self, identity: IdentityContext, space_uid: str) -> bool:
        """判断能否进入指定空间。"""


class LegacySpaceAccessSource:
    """基于 ExternalPermission 授权记录的空间级访问来源。"""

    name = DecisionSource.LEGACY

    def list_space_actions(self, identity: IdentityContext) -> dict[str, list[str]]:
        return dict(ExternalPermission.get_authorizer_permission(authorizer=identity.authorization_subject))

    def list_space_uids(self, identity: IdentityContext) -> list[str]:
        return list(ExternalPermission.get_authorized_user_space_list(authorized_user=identity.authorization_subject))

    def has_access(self, identity: IdentityContext, space_uid: str) -> bool:
        permission = ExternalPermission.get_authorizer_permission(
            authorizer=identity.authorization_subject, space_uid=space_uid
        )
        return bool(permission.get(space_uid))


LEGACY_SPACE_ACCESS_SOURCE = LegacySpaceAccessSource()

# 当前只认旧票，空间级放行行为与接入前一致。接入权限中心的空间范围查询时在这里追加来源。
SPACE_ACCESS_SOURCES: tuple[SpaceAccessSource, ...] = (LEGACY_SPACE_ACCESS_SOURCE,)


def list_authorized_space_actions(
    identity: IdentityContext,
    sources: tuple[SpaceAccessSource, ...] | None = None,
) -> dict[str, list[str]]:
    """空间到授权项的映射，多来源时同一空间的授权项取并集。"""
    merged: dict[str, list[str]] = {}
    for source in SPACE_ACCESS_SOURCES if sources is None else sources:
        for space_uid, action_ids in source.list_space_actions(identity).items():
            existing = merged.setdefault(space_uid, [])
            existing.extend(action_id for action_id in action_ids if action_id not in existing)
    return merged


def list_authorized_space_uids(
    identity: IdentityContext,
    sources: tuple[SpaceAccessSource, ...] | None = None,
) -> list[str]:
    """可访问的空间列表，保持各来源的返回顺序，跨来源去重。"""
    space_uids: list[str] = []
    for source in SPACE_ACCESS_SOURCES if sources is None else sources:
        space_uids.extend(space_uid for space_uid in source.list_space_uids(identity) if space_uid not in space_uids)
    return space_uids


def has_space_access(
    identity: IdentityContext,
    space_uid: str,
    sources: tuple[SpaceAccessSource, ...] | None = None,
) -> bool:
    """任一来源认可即可进入该空间。"""
    resolved = SPACE_ACCESS_SOURCES if sources is None else sources
    return any(source.has_access(identity, space_uid) for source in resolved)
