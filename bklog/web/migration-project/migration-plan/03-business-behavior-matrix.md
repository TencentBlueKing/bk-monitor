# P2 业务行为矩阵

试点模块是日志采集新增步骤里的标签弹窗和应用类型选择。证据来自源码，不是登录后操作。其余 88 条路由没有运行时场景。

| 场景 | 源码 | 预期 | 证据 |
| --- | --- | --- | --- |
| COLLECT-LABEL-001 | `label-target-dialog.vue` `isHaveSelectItem` | 备选和已选 id 都为空时，确定按钮禁用。只有候选项、没有 id 时仍禁用 | 源码 |
| COLLECT-LABEL-002 | `handelConfirmLabel` | 只提交已选 id。`operator === '='` 记为 `match_labels`，其他记为 `match_expressions`。提交后清空两边列表 | 源码 |
| COLLECT-LABEL-003 | `handelCancelDialog` / `isShowDialog` | 取消只重置选择。关闭弹窗时再清空搜索词 | 源码 |
| COLLECT-LABEL-004 | `isShowDialog` | 打开时把已有 `labelSelector` 复制进已选，并为每项生成新 id。`namespaceStr === '*'` 时命名空间参数为 `undefined`；`type === 'node'` 时不带命名空间字段 | 源码 |
| COLLECT-LABEL-005 | `handleSelectTreeItem` / `apply` 响应 | 非 pod、node 不请求。过期 `labelRequestId` 的响应丢弃。已选里 `operator === '='` 的同 key/value 不再进入备选 | 源码 |
| COLLECT-LABEL-006 | `filterMethod` | 树搜索按 `node.data.name.includes(keyword)` | 源码 |
| COLLECT-WORKLOAD-001 | `container-target-item.vue` `formData.workload_type` | 类型变化先清空应用名列表。类型不在 `typeList` 中时不请求 | 源码 |
| COLLECT-WORKLOAD-002 | `getWorkLoadNameList` | 已知类型才请求。`namespaceStr === '*'` 不传命名空间。`namespacesExclude === '!='` 时字段名是 `namespaces_exclude` | 源码 |
| COLLECT-WORKLOAD-003 | `beforeDestroy` | 销毁时递增 `nameRequestId`，在途响应不再写入列表 | 源码 |

未从运行时确认：树组件 `isSearchEmpty`、`bk-select` 内部输入框禁用、弹层真实布局、接口失败时页面上的提示。这些不写成已验证行为。
