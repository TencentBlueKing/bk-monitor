from __future__ import annotations


class V3GrantError(RuntimeError):
    """IAM V3 授权接口以 false 返回值表示的明确失败。"""
