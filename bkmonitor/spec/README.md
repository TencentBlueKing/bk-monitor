# Spec

本目录参考 OpenSpec 的组织方式，作为需求调研、方案设计和实施任务的落地点。

目录约定：

- `changes/<change-id>/proposal.md`：变更背景、目标、范围和影响。
- `changes/<change-id>/design.md`：设计细节、关键决策、约束和风险。
- `changes/<change-id>/tasks.md`：实施与验证任务拆解。
- `changes/<change-id>/specs/<capability>/spec.md`：面向行为的规格说明，使用 requirement/scenario 约束最终实现。

当前已登记的变更：

- `stabilize-datalink-component-reuse`：为 `DataLink.apply_data_link` 增加已有组件复用与稳定映射能力，避免迁移后因组件 `name` 不对齐导致重复创建。
