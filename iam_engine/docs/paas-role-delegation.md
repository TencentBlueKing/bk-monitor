# PaaS 空间角色委托

IAM V4 的系统 clients 与角色授权委托是独立能力。BKMonitor 和 BKLog
只向系统 `bk_paas3` 委托 `space_operator`，使用 `tenant_mode=global`；
不委托 `space_viewer`、管理员或通配角色，也不直接给用户新增权限。

两平台 V4 基线显式移除 `bk_paas3`、`paasv3cli` 两个 clients。
同步会从已有远端 clients 中移除这两项，但继续保留其他手工添加的客户端。
V3 clients 和 V3 同步逻辑不变。

## 同步与失败处理

- 现有部署 post_migrate 和手动 `iam_migrate_model --apply` 使用相同公共同步服务。
- V3 模式不调用 V4；V4/Union 按现有模式规则同步 V4。
- 先注册系统、资源、Action 和角色，再调用
  `POST api/v1/open/mgmt/systems/{system_id}/role-delegations/`。
- 已有系统的 clients 更新在委托创建成功后执行，避免委托失败时提前移除原有客户端。
- IAM 契约为 HTTP 201、`data: null`，已存在的委托会被忽略。
  因未发现可用的委托查询接口，每次实际同步均确保委托存在；预览只报告此操作，
  不声称远端缺少委托，不调用写接口。部分失败后可以重新同步。
- 委托失败遵循现有模型同步失败传播机制，部署/命令报告失败，不降级为 single。

## 环境前提与验证边界

调用应用必须具有该网关 API 的应用权限。`global` 要求全租户系统在运营租户下调用，
对应角色也必须为全租户角色；不满足时需先修正环境接入条件。

离线测试覆盖请求路径、租户头、响应契约、执行顺序、失败传播、客户端移除及 V3 隔离。
它不能证明目标环境的应用权限、角色委托实际生效或 PaaS 创建空间后成功授权；
这些需要授权后另行实测。本变更不调用真实 IAM、不部署、不迁移存量用户授权。
