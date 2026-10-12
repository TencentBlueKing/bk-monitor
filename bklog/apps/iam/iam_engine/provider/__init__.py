"""Provider 契约与编排。

# ---------------------------------------------------------------------------
# provider/
#
# PermissionProvider     单个协议栈的鉴权入口，返回三态 AuthResult
# ProviderBundle         把鉴权 / 申请 / Writer / 范围查询绑在同一个版本上
# ModeRouter             读 Feature Toggle，按 DualStackSpec 决定跑几路或查范围
# UnionDecisionPolicy    union 语义：任一 ALLOW 即过；ERROR 只标 degraded
# PairExecutor           双栈并发的注入点，实现放在 apps.iam.concurrency
#
# 本包不认识 IAM SDK。具体 HTTP / 编码在 backends/v3|v4。
# ---------------------------------------------------------------------------
"""
