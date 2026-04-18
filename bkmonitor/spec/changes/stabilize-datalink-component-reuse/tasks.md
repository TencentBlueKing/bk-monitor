# Tasks

## 1. 基础设施

- [ ] 新增 `ALL_DATA_LINK_COMPONENT_KINDS` 常量，集中维护"全部 DataLink 组件模型"列表
- [ ] 实现 `ExistingComponentContext`，仅暴露 `from_datalink` / `claim(kind, predicate)` / `leftover()` 三个方法
- [ ] `claim` 在传入未注册 kind 时直接 raise；命中 ≥2 条时返回 `None` 且不修改 pool
- [ ] 在 `DataLink` 上新增 `REUSE_LEFTOVER_POLICY` 集中表与 `_leftover_policy(kind)` 访问器，默认 `strict`
- [ ] 新增 `ComponentReuseError`，错误信息包含 `data_link_name / strategy / kind / leftover 标识`
- [ ] 在 `settings` 中新增 `DATA_LINK_COMPONENT_REUSE_STRATEGIES: set[str]` 灰度开关，默认空集合
- [ ] 改造 `DataLink.apply_data_link` 入口：按开关分支构造 `ctx`、调用 compose、做 leftover 检查；leftover 检查必须在 `apply_data_link_with_retry` 之前

## 2. compose 分支按 strategy 接入（一项一 PR，独立灰度）

每项需完成：函数签名加 `existing_context` 参数 → 每个 `update_or_create` 前插入 `claim` → 用 `claim` 返回的 `name` 替换固定 name → 把 strategy 加入 `DATA_LINK_COMPONENT_REUSE_STRATEGIES` → 配套测试。

- [ ] `BK_STANDARD_V2_TIME_SERIES`（`compose_standard_time_series_configs`）
- [ ] `BK_EXPORTER_TIME_SERIES` / `BK_STANDARD_TIME_SERIES`（`compose_bk_plugin_time_series_config`）
- [ ] `BCS_FEDERAL_PROXY_TIME_SERIES`（`compose_bcs_federal_proxy_time_series_configs`）
- [ ] `BCS_FEDERAL_SUBSET_TIME_SERIES`（`compose_bcs_federal_subset_time_series_configs`）
- [ ] `BASE_EVENT_V1`（`compose_base_event_configs`）
- [ ] `SYSTEM_PROC_PERF` / `SYSTEM_PROC_PORT`（`compose_system_proc_configs`）
- [ ] `BK_STANDARD_V2_EVENT`（`compose_custom_event_configs`）
- [ ] `BK_LOG`（`compose_log_configs`）：同时在 `REUSE_LEFTOVER_POLICY` 中声明 `ESStorageBindingConfig` / `DorisStorageBindingConfig` 为 `keep`
- [ ] `BASEREPORT_TIME_SERIES_V1`（`compose_basereport_time_series_configs`）：多 slot 复杂度最高，建议放在最后

## 3. 测试

- [ ] 迁移后 name 不一致但可复用（单实例链路）
- [ ] basereport 多组件稳定复用（连续两次 apply，claim 结果一致）
- [ ] 部分命中 + 部分新建
- [ ] 歧义放弃复用：predicate 命中 ≥2 条时走新建，多余 existing 进入 leftover
- [ ] strict leftover 触发报错（不调用 BKBase 下发接口）
- [ ] 多 strict 违规一次聚合上报
- [ ] `BK_LOG` 关闭某个 binding 开关后旧 binding 被保留
- [ ] `claim` 调用未注册 kind 时直接 raise
- [ ] 历史 strategy 创建的组件被全局加载并触发 leftover 检查
- [ ] 灰度开关关闭时回退到老路径，行为与改造前一致

## 4. 复用后元数据回填

- [x] 改造 `DataLink.sync_metadata`：按 `(bk_tenant_id, namespace, data_link_name, table_id)` 查 `ResultTableConfig`、按 `(bk_tenant_id, namespace, data_link_name)` 查 `DataBusConfig`，读实名回填 `BkBaseResultTable.bkbase_rt_name` / `bkbase_data_name`；`bkbase_table_id` 前缀用 `rt.datalink_biz_ids.data_biz_id`，不再使用全局 `settings.DEFAULT_BKDATA_BIZ_ID`；配置表 miss 时 warning + skip，不再走 `compose_bkdata_*` 推测
- [x] 改造 `create_bkbase_data_link` / `create_fed_bkbase_data_link`：`AccessVMRecord.vm_result_table_id` 改为读 `BkBaseResultTable.bkbase_table_id`，读取失败时 fallback 到 `get_tenant_datalink_biz_id(bk_tenant_id, bk_biz_id).data_biz_id` 拼接并 error log
- [x] 改造 `_refresh_data_link_status`：
  - [x] `DataIdConfig` 按 `bkbase_data_name` 查不到时 fallback 到 `DataLink.bk_data_id`；两个都 miss 时打 warning 且跳过数据源状态刷新，不影响后续组件循环
  - [x] 组件循环按 `(bk_tenant_id, namespace, data_link_name)` 过滤每个 kind 的实例，逐条刷新状态；日志中打印实际 `component_ins.name`
- [x] 删除 `BkBaseResultTable.component_id` property（以及 `bk-monitor-base` 镜像文件）和对应单元测试 `test_component_id`
- [x] 新增测试：
  - [x] `test_bk_exporter_reuse_three_legacy_components` / `test_bk_standard_v2_reuse_three_legacy_components` 追加 `BkBaseResultTable.bkbase_rt_name` / `bkbase_table_id` / `bkbase_data_name` 断言
  - [x] `test_bk_standard_v2_sync_metadata_respects_tenant_biz_id`：patch `get_tenant_datalink_biz_id` 返回非默认值，验证 `bkbase_table_id` 前缀跟随 tenant
  - [x] `test_refresh_data_link_status_matches_by_data_link_name`：三者名字互不相同时所有组件都被按 `data_link_name` 刷新
  - [x] `test_refresh_data_link_status_falls_back_to_bk_data_id`：`bkbase_data_name` 与 `DataIdConfig.name` 不一致但 `DataLink.bk_data_id` 命中时走 fallback 路径

## 5. 文档与清理

- [ ] 在相关模块 docstring / 内部文档中说明 `ExistingComponentContext` 的使用方式与 `REUSE_LEFTOVER_POLICY` 的声明位置
- [ ] 全部 strategy 接入完毕、灰度稳定后，评估是否清理 `STRATEGY_RELATED_COMPONENTS` 中已被 `ALL_DATA_LINK_COMPONENT_KINDS` 覆盖的部分（仅作记录，不在本次范围内强制完成）
