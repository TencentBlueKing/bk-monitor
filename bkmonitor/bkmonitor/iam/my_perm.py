"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

权限中心「我的权限」跳转地址解析。

各 IAM 版本的「我的权限」路由不同，前端不做版本判断，由后端按当前鉴权版本拼出完整地址下发。
前端接入前，该地址只下发不消费，跳转行为与改动前一致。
"""

from django.conf import settings

from common.log import logger

# 各 IAM 版本下「我的权限」页面的路由。V4 与 V3 路径完全不同，不可互相兜底。
IAM_MY_PERM_PATHS = {
    "v3": "/my-perm",
    "v4": "/permission/my-own/overview",
}

# union 是双栈迁移期，current 已是 v4，故跳转路由与 v4 一致
_V4_LIKE_MODES = {"v4", "union"}

# 监控侧已适配的版本。取值合法性由引擎的 AuthMode 负责（非法值在引擎里就抛错），
# 这里只回答「监控侧认不认识」，仅在引擎换代新增协议版本时才会命中。
_KNOWN_MODES = frozenset(IAM_MY_PERM_PATHS) | _V4_LIKE_MODES


def get_iam_mode() -> str:
    """当前生效的 IAM 鉴权版本。

    读取失败时按 v3 处理：版本探测异常不应导致上下文接口或页面渲染整体不可用。
    """
    try:
        from bkmonitor.iam.mode import get_mode_provider

        mode = get_mode_provider().get_mode()
    except Exception:  # noqa: BLE001
        # 含引擎抛出的 InvalidAuthModeError：非法配置在引擎里已 fail-closed 并记过日志，
        # 这里只是拼一个跳转地址，回退 v3 不放行任何权限，故不再区分异常类型。
        logger.exception("[get_iam_mode] 获取 IAM 鉴权版本失败，回退 v3")
        return "v3"

    # AuthMode 是 str 混入的枚举，Python 3.11 起 str() 得到 "AuthMode.V4"，必须取 value
    mode_value = str(getattr(mode, "value", mode)).strip().lower()
    if mode_value not in _KNOWN_MODES:
        # 引擎校验已保证返回值合法，此处只在引擎换代新增协议版本时为监控侧留痕
        logger.warning(f"[get_iam_mode] 未适配的 IAM 鉴权版本 {mode!r}，按 v3 处理")
        return "v3"

    return mode_value


def get_iam_my_perm_url() -> str:
    """「权限中心 -> 我的权限」的完整跳转地址，供前端直接打开。

    前端此前按 ``{BK_IAM_URL}/my-perm`` 拼接，而 ``/my-perm`` 是 IAM V3 专有路由，
    V4 下为 ``/permission/my-own/overview``。路径差异在此按鉴权版本吸收。
    基址为空时返回空串，由前端决定降级行为。
    """
    host = (settings.BK_IAM_SAAS_HOST or "").rstrip("/")
    if not host:
        return ""

    path = IAM_MY_PERM_PATHS["v4"] if get_iam_mode() in _V4_LIKE_MODES else IAM_MY_PERM_PATHS["v3"]
    return f"{host}{path}"
