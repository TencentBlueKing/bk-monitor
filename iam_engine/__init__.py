"""BKLog 与监控共用的 IAM 双栈基础设施。

# ---------------------------------------------------------------------------
# iam_engine —— 协议无关的鉴权编排
#
# 不注册产品 Schema，不装配产品 AppConfig，也不接管业务资源反向回调。
# 两平台继续使用现有 Permission 入口，注入模式、方言、资源解析和事务提交 hook。
#
# 分层：
#   core/        运行时值对象、鉴权模式、拓扑、异常。禁止 import Django / IAM SDK。
#   provider/    Provider 契约、Bundle、ModeRouter、Union 合并策略。
#   migration/   申请选边、双写与冻结计划重放。事务提交 hook 由产品侧注入。
#   settings/v4 共用 BKLog 配置契约、HTTP 传输及响应校验。
#
# 协议方言留在两平台产品适配层，公共层不能反向 import 业务模块：
#   引擎说普通话（view_business、space、3），方言层负责编码成
#   view_business_v2 / neg_3 后再打网关。
#
# 换代要同时改 AuthMode 枚举、默认拓扑和 Bundle 注入；退出的协议名会变成非法配置。
# 不要在 Router / Policy 里再写死版本名。
# ---------------------------------------------------------------------------
"""
