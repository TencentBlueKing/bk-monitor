## 1. 兼容基线梳理

- [x] 1.1 在 `bk-monitor-base` 中梳理 `NodemanInstaller.status()` 当前依赖的数据源和调用路径，明确哪些现有逻辑可复用、哪些需要按旧版兼容语义重建
- [x] 1.2 从旧版 collecting `NodeManInstaller.status(diff)`、`_process_nodeman_task_result()` 和 `DeploymentConfigVersion.show_diff()` 提炼出可直接实现的 diff 分类与实例字段转换规则
- [x] 1.3 明确主机旧格式节点归一化、模板展开、动态分组主机关联和 `REMOVE` 过滤等历史兼容规则在 base 中的落点

## 2. status 兼容实现

- [x] 2.1 将 `bk-monitor-base` 的 `NodemanInstaller.status` 方法签名调整为 `status(diff=False)`，并保持默认行为返回旧版全量状态结构
- [x] 2.2 实现旧版兼容的节点 diff 计算逻辑，覆盖首版部署、插件版本变化、参数变化、远程采集范围变化和节点增删改场景
- [x] 2.3 实现旧版兼容的实例字段转换逻辑，补齐 `task_id`、`plugin_version`、`scope_ids`、状态映射和阶段日志格式
- [x] 2.4 按旧版 target scope 语义实现 HOST、TOPO、DYNAMIC_GROUP、SERVICE_TEMPLATE、SET_TEMPLATE 的结果分组和 `node_path/label_name/is_label` 输出
- [x] 2.5 在结果构建流程中补齐主机旧格式节点归一化、模板节点展开、动态分组回填和临时字段清理，确保与旧版边界行为一致

## 3. 验证与回归

- [x] 3.1 为 `status(diff=False)` 增加兼容测试，覆盖主机实例和服务实例的字段结构与默认返回格式
- [x] 3.2 为 `status(diff=True)` 增加兼容测试，覆盖 `ADD`、`UPDATE`、`RETRY`、首版部署、插件版本变化和 `REMOVE` 不出现在最终结果中的行为
- [x] 3.3 为模板目标、动态分组目标和主机旧格式节点归一化增加专项测试，确保节点映射与分组结果不漂移
- [x] 3.4 运行相关测试与静态检查，确认 `NodemanInstaller.status` 新签名和兼容输出未引入明显回归
