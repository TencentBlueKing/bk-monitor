"""BKLog IAM 双栈编排层。

# ---------------------------------------------------------------------------
# iam_engine —— 协议无关的鉴权编排
#
# 和监控平台 IAMFramework 的分工不同：这里不注册 Schema、不装配 Django
# AppConfig、也不接管反向回调。业务仍走 ``handlers.permission.Permission``，
# 本包只回答「当前该跑哪些 Provider、结果怎么合并、申请/双写选哪一边」。
#
# 分层：
#   core/        运行时值对象、鉴权模式、拓扑、异常。禁止 import Django / IAM SDK。
#   provider/    Provider 契约、Bundle、ModeRouter、Union 合并策略。
#   migration/   申请选边与创建者双写。可以依赖 Django 事务，但不认识具体协议。
#
# 协议方言在 ``apps.iam.backends.v3`` / ``apps.iam.backends.v4``：
#   引擎说普通话（view_business、space、3），方言层负责编码成
#   view_business_v2 / neg_3 后再打网关。
#
# 换代要同时改 AuthMode 枚举、默认拓扑和 Bundle 注入；退出的协议名会变成非法配置。
# 不要在 Router / Policy 里再写死版本名。
# ---------------------------------------------------------------------------
"""
