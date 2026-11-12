# 管理列表标签与停用预览契约（实施中）

依据：`packages/web-v2/src/views/manage-v2/log-collection/components/common-comp/tag-more.tsx`，以及当前安装的 `bk-magic-vue/lib/select.js` 中 `search`、`ensureSearch`、`handleDocumentKeydown`、`selectOption`、`handleClose`。此组件同时用于索引集展示和标签编辑，两个模式不能互相替代验收。

## 已确认问题与处理

- V3 旧适配 Select 未传递 `trigger` 插槽：空标签显示成普通输入框，原 58px 自定义触发区域未渲染。两次相同数据重放均可复现；原菜单 y=275，V3 y=271。
- 停用预览 TDialog 默认 32px padding 与 V2 的 24px 业务边距不一致，432px 卡片被裁切；默认 top=180 与 V2 top=200 不同。只针对该弹框恢复样式及 body 挂载，不全局改变其他弹框。
- 菜单关闭并无业务缺陷：Tippy 已设置 isVisible=false，截图发生在退场动画中。验证脚本改为等待实际隐藏。旧 wrapper 位于 -100000 的矩形不作为可视弹框基准。
- `rowHeight` 不属于当前 TDesign Table 的有效顶层属性；不能简单认为是全部行高问题的原因。标签自定义触发器丢失才是本样本主要根因；不通过给菜单加偏移掩盖。

## 标签模式必须保留

1. 内置标签从普通选择列表与已选展示中排除；已选标签在下拉列表禁用；terminated 禁止添加、保留原 tooltip。
2. 单选成功仍调用 unionAddLabel，参数 index_set_id/tag_id 不变；成功后回填原对象、发送原更新事件、显示成功消息，finally 清空临时选中值。
3. 删除调用 unionDeleteLabel，成功后仅移除同 tag_id；不改变接口和事件顺序。
4. 新增表单：必填、普通标签重名、内置名三条校验；提交 trim 后 name/space_uid；创建成功刷新列表并关联；finally 清空草稿、收起新增与选择器。取消新增只收起草稿区域，关闭选择器才清空草稿。
5. TDesign Form 的 validate 失败会 resolve 错误对象，不能按旧 reject-only 协议直接提交；必须 `result === true`。
6. 自定义触发器、默认加号触发器、空态、两行展示、+N、tooltip、测量与 ResizeObserver 生命周期全部保留。
7. 搜索输入位于浮层内，trim+大小写不敏感过滤；Enter 参考 V2 ensureSearch；Escape/Tab 关闭；上下箭头的循环和焦点转移参考 V2 原处理；卸载移除 document 监听。
8. 搜索、hover、打开、关闭、校验失败不允许产生业务写请求。

## 本批验收边界

已有资源仅做查看、菜单/弹框预览与取消，禁止点下一步、确认、选择实际标签、删除标签。真实创建/关联/删除成功链路必须在新建专用资源上单独验收。权限、terminated、内置标签、两行溢出、键盘提交及异步失败仍需独立场景；本文件不声明组件全量通过。


## 2026-11-11 的独立问题与证据修正

- V2 标签取消出现三次 live 失败、一次固定重放成功。对失败样本 `bklog-v2-management-PdH95Y` 的 MutationObserver 记录确认，同一次点击先将 `new-label-input` 改为 `add-new-label`，随即又改回 `new-label-input` 并自动聚焦。这与取消函数只置 false、新增函数置 true、两个条件分支复用 div 的源码一致，是框架事件冒泡/节点复用问题。
- 不将偶然成功的取消录制当稳定全量基线。`labels` 模式改为搜索、必填、Escape 关闭、重开复位；`labels-cancel` 独立场景保持未完成，需要单独的源契约回归。取消不从能力分母删除。
- V3 给草稿和新增入口设置不同 key，保持取消函数原行为，防止同一点击命中新挂载的新增监听器。
- 之前标签视觉样本截在 scaleY 动画中，输入框高度为 9.84/29.60px。该样本不再用于新的视觉结论。新工具等待有限动画结束和连续稳定帧；新增两项隔离浏览器校准已通过（总14项），不是业务验收。
- 使用 TSelect 的公开 label TNode 保留完整业务触发区域；搜索框放回 panelTopContent，表单放回 panelBottomContent。TDesign Popup 在存在默认插槽时优先默认内容，不能仅靠 popupProps.triggerElement 替换 TSelect 输入结构。
- 输入与标签 ID 保持原类型，不通过 Number 转换改变 API 参数。TForm 校验仍为三条源规则；错误提示以 TTooltip 呈现，避免固定高度页脚裁切错误文案。


## Enter 与事件协议修复

当前安装的 TDesign 1.20.10 `es/input/hooks/useInputEventHandler.mjs` 对 Enter 只调用 onEnter，不调用 onKeydown。真实组件隔离测试复现：新增标签按 Enter 意外执行列表选中（tag_id=2），没有调用创建服务。已将新增和搜索提交映射至 onEnter，并保留源代码的传播阻止；普通键仍走 onKeydown。隔离服务记录精确检查新增 name.trim()/space_uid、后续关联 tag_id，以及删除、禁用、键盘循环、空值不写入。

TDesign Dialog 的 cancelBtnAction 先调用 onCancel，再以 trigger=cancel 发出 onClose。旧 V3 同时绑定同一处理函数会重复 emit cancel。停用弹框改为只由 onClose 处理取消/关闭，确认仍保持原 handleSave 的 update → cancel 顺序。隔离测试要求取消按钮与 Escape 各只产生一次 cancel。

索引集编辑 Input 也存在同类 Enter 传播阻止失效：原 V2 onEnter 提交、onKeydown 阻止冒泡；现将两者放在原生 onEnter 内完成。初版夹具错误地要求成功后子组件继续 emit cancel，已根据 V2 table-list-v2.tsx handleSubmitAddIndexSet（先关闭，再刷新）的真实父组件契约修正；该错误不记为产品缺陷。子组件请求期间 cancel guard 不变，没有为迎合测试新增事件。

焦点与键盘生命周期分别提取为 useVisibleInputFocus 与 useLabelPickerKeyboard；关闭、卸载清理 observer 和 document 监听。全局角色配置、业务 API 和规则没有替换为简化实现。
