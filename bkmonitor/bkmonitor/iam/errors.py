"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# IAM 适配层的对外异常。这里的异常服务于旧 DRF / 前端协议，不属于
# iam_engine 的 ProviderError 层级。ProviderUnavailable 必须先在框架组合
# 策略中保留原语义，以便 union / primary 可以尝试其它 Provider；只有 DRF
# 边界确认无法得到鉴权结论后，才将其降级为本模块的异常。

from core.errors.iam import PermissionDeniedError


class IAMBackendUnavailableError(PermissionDeniedError):
    """IAM 后端不可用时的旧鉴权协议降级异常。

    对外刻意保持 PermissionDeniedError 的 HTTP 403 / 9900403 协议，避免
    老前端因后端切换观察到新的错误码、消息或 error_details.type。真实
    的故障分类仅保留在异常类型、异常链和服务端日志中。
    """

    backend_unavailable = True

    def __init__(self, action_name: str, apply_url: str = "", permission: dict | None = None):
        super().__init__(
            context={"action_name": action_name},
            data={"apply_url": apply_url},
            extra={"permission": permission},
        )
        # Error.__init__ 默认会使用子类名。对外固定为旧类型，确保历史前端
        # 或第三方调用方按 error_details.type 判断时也不感知后端切换。
        self.set_details(
            exc_type=PermissionDeniedError.__name__,
            exc_code=self.code,
            overview=self.message,
            detail=self.data,
            popup_message=self.popup_message,
        )


def build_legacy_permission_denied(
    action_name: str,
    apply_url: str = "",
    permission: dict | None = None,
    *,
    backend_unavailable: bool = False,
) -> PermissionDeniedError:
    """构建 DRF 鉴权失败的历史响应载体。

    无论底层是 V3、V4 还是 union，浏览器均收到同一份
    PermissionDeniedError 协议。backend_unavailable 仅决定服务端异常的
    Python 类型，绝不改变客户端 JSON 契约。
    """
    if backend_unavailable:
        return IAMBackendUnavailableError(action_name, apply_url, permission)
    return PermissionDeniedError(
        context={"action_name": action_name},
        data={"apply_url": apply_url},
        extra={"permission": permission},
    )
