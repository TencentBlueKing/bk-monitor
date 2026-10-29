# P1 旧项目静态分析

扫描范围：`bklog/web/src`。结果来自 `node migration-project/analyze-legacy.mjs` 的正则与目录扫描，不是运行时结论。完整命中位置在 `migration-project/artifacts/analysis/*.json`。

## 路由

业务路由文件是 `src/router/index.js`、`retrieve.js`、`monitor.js`、`dashboard.js`、`manage.js`。带 `path` 的路由 88 条。没有 `path`、只出现 `name` 的对象 1 个，它们多半是嵌套占位组件，不计入页面。

| 位置 | path | name | title |
| --- | --- | --- | --- |
| src/router/dashboard.js:39 | `/dashboard` | dashboard | — |
| src/router/dashboard.js:46 | `home` | home | 仪表盘 |
| src/router/dashboard.js:56 | `default-dashboard` | default-dashboard | 仪表盘 |
| src/router/dashboard.js:66 | `create-dashboard` | create-dashboard | 仪表盘 |
| src/router/dashboard.js:78 | `create-folder` | create-folder | 仪表盘 |
| src/router/dashboard.js:90 | `import-dashboard` | import-dashboard | 仪表盘 |
| src/router/index.js:108 | `/un-authorized` | un-authorized | 无权限页面 |
| src/router/index.js:118 | `*` | exception | 无权限页面 |
| src/router/manage.js:159 | `/manage` | manage | — |
| src/router/manage.js:186 | `log-collection` | log-collection | — |
| src/router/manage.js:193 | `collection-item` | collection-item | — |
| src/router/manage.js:200 | `list` | collection-item-list | 日志采集 |
| src/router/manage.js:210 | `manage/:collectorId` | manage-collection | 日志采集 |
| src/router/manage.js:222 | `add` | collectAdd | 日志采集 |
| src/router/manage.js:234 | `edit/:collectorId` | collectEdit | 日志采集 |
| src/router/manage.js:246 | `field/:collectorId` | collectField | 日志采集 |
| src/router/manage.js:258 | `storage/:collectorId` | collectStorage | 日志采集 |
| src/router/manage.js:270 | `masking/:collectorId` | collectMasking | 日志采集 |
| src/router/manage.js:282 | `start/:collectorId` | collectStart | 日志采集 |
| src/router/manage.js:294 | `stop/:collectorId` | collectStop | 日志采集 |
| src/router/manage.js:308 | `log-index-set` | log-index-set | — |
| src/router/manage.js:315 | `list` | log-index-set-list | 日志采集 |
| src/router/manage.js:325 | `manage/:indexSetId` | log-index-set-manage | 日志采集 |
| src/router/manage.js:337 | `create` | log-index-set-create | 日志采集 |
| src/router/manage.js:349 | `edit/:indexSetId` | log-index-set-edit | 日志采集 |
| src/router/manage.js:361 | `masking/:indexSetId` | log-index-set-masking | 日志采集 |
| src/router/manage.js:376 | `tgpa-task` | tgpa-task | — |
| src/router/manage.js:383 | `list` | tgpa-task-list | 客户端日志 |
| src/router/manage.js:393 | `clean-config` | clean-config | 清洗配置 |
| src/router/manage.js:407 | `bk-data-collection` | bk-data-collection | — |
| src/router/manage.js:414 | `list` | bkdata-index-set-list | 计算平台 |
| src/router/manage.js:424 | `manage/:indexSetId` | bkdata-index-set-manage | 计算平台 |
| src/router/manage.js:436 | `create` | bkdata-index-set-create | 计算平台 |
| src/router/manage.js:448 | `edit/:indexSetId` | bkdata-index-set-edit | 计算平台 |
| src/router/manage.js:460 | `masking/:indexSetId` | bkdata-index-set-masking | 计算平台 |
| src/router/manage.js:474 | `es-collection` | es-collection | — |
| src/router/manage.js:481 | `list` | es-index-set-list | 第三方ES |
| src/router/manage.js:491 | `manage/:indexSetId` | es-index-set-manage | 第三方ES |
| src/router/manage.js:503 | `create` | es-index-set-create | 第三方ES |
| src/router/manage.js:515 | `edit/:indexSetId` | es-index-set-edit | 第三方ES |
| src/router/manage.js:527 | `masking/:indexSetId` | es-index-set-masking | 第三方ES |
| src/router/manage.js:541 | `custom-report` | custom-report | — |
| src/router/manage.js:548 | `list` | custom-report-list | 自定义上报 |
| src/router/manage.js:558 | `create` | custom-report-create | 自定义上报 |
| src/router/manage.js:570 | `edit/:collectorId` | custom-report-edit | 自定义上报 |
| src/router/manage.js:582 | `detail/:collectorId` | custom-report-detail | 自定义上报 |
| src/router/manage.js:594 | `masking/:indexSetId` | custom-report-masking | 自定义上报 |
| src/router/manage.js:608 | `clean-list` | clean-list | — |
| src/router/manage.js:615 | `list` | log-clean-list | 日志清洗 |
| src/router/manage.js:625 | `create` | clean-create | 日志清洗 |
| src/router/manage.js:637 | `edit/:collectorId` | clean-edit | 日志清洗 |
| src/router/manage.js:651 | `clean-templates` | clean-templates | — |
| src/router/manage.js:658 | `list` | log-clean-templates | 日志清洗 |
| src/router/manage.js:668 | `create` | clean-template-create | 日志清洗 |
| src/router/manage.js:680 | `edit/:templateId` | clean-template-edit | 日志清洗 |
| src/router/manage.js:694 | `log-desensitize` | log-desensitize | — |
| src/router/manage.js:701 | `list` | log-desensitize-list | 日志清洗 |
| src/router/manage.js:713 | `grok-manage` | grok-manage | Grok管理 |
| src/router/manage.js:723 | `archive-repository` | archive-repository | 日志归档 |
| src/router/manage.js:733 | `archive-list` | archive-list | 日志归档 |
| src/router/manage.js:743 | `archive-restore` | archive-restore | 日志归档 |
| src/router/manage.js:753 | `manage-log-extract` | manage-log-extract | 日志提取 |
| src/router/manage.js:763 | `log-extract-task` | log-extract-task | 日志提取 |
| src/router/manage.js:784 | `extract-create` | extract-create | 日志提取 |
| src/router/manage.js:796 | `extract-clone` | extract-clone | 日志提取 |
| src/router/manage.js:810 | `extract-link-manage` | extract-link-manage | — |
| src/router/manage.js:817 | `list` | extract-link-list | 日志提取 |
| src/router/manage.js:827 | `edit/:linkId` | extract-link-edit | 日志提取 |
| src/router/manage.js:839 | `create` | extract-link-create | 日志提取 |
| src/router/manage.js:853 | `es-cluster-manage` | es-cluster-manage | ES集群 |
| src/router/manage.js:863 | `report-manage` | report-manage | 订阅管理 |
| src/router/manage.js:873 | `collection-track` | collection-track | 采集接入 |
| src/router/manage.js:883 | `bk-data-track` | bk-data-track | — |
| src/router/manage.js:890 | `list` | bkdata-track-list | 数据平台接入 |
| src/router/manage.js:900 | `manage/:indexSetId` | bkdata-track-manage | 数据平台接入 |
| src/router/manage.js:912 | `create` | bkdata-track-create | 数据平台接入 |
| src/router/manage.js:924 | `edit/:indexSetId` | bkdata-track-edit | 数据平台接入 |
| src/router/manage.js:938 | `sdk-track` | sdk-track | SDK接入 |
| src/router/manage.js:948 | `manage-data-link-conf` | manage-data-link-conf | 设置 |
| src/router/manage.js:958 | `collect` | — | — |
| src/router/monitor.js:39 | `/monitor-apm-log/:indexId?` | monitor-apm-log | APM检索-日志 |
| src/router/monitor.js:50 | `/monitor-trace-log/:indexId?` | monitor-trace-log | Trace检索-日志 |
| src/router/retrieve.js:39 | `/retrieve/:indexId?` | retrieve | 检索 |
| src/router/retrieve.js:49 | `/client-log-search` | client-log-search | 客户端日志 |
| src/router/retrieve.js:59 | `/template-manage` | templateManage | — |
| src/router/retrieve.js:65 | `/external-auth/:activeNav?` | externalAuth | 授权列表 |
| src/router/retrieve.js:75 | `/share/:linkId?` | share | 分享链接 |
| src/router/retrieve.js:86 | `/data_id/:id?` | data_id | 根据 bk_data_id 获取采集项和索引集信息 |

## 组件

`src/components` 与 `src/views` 下的 `.vue` / `.tsx` 共 468 个，文件清单在 `components.json`。静态 import 共 243 次。动态 `import()`、`<component :is>` 不在这张表里。

引用次数前 30：

| specifier | 次数 |
| --- | --- |
| `@/views/retrieve-helper` | 29 |
| `@/components/empty-status` | 26 |
| `@/components/bklog-popover` | 21 |
| `@/components/time-range/utils` | 18 |
| `@/components/empty-status/index.vue` | 15 |
| `@/components/common/auth-container-page` | 7 |
| `@/views/retrieve-core/page-highlight` | 7 |
| `@/components/time-range/time-range` | 7 |
| `@/views/manage-v2/utils/clean-template` | 6 |
| `@/components/log-ip-selector/log-ip-selector` | 5 |
| `@/components/user-selector` | 5 |
| `@/views/retrieve-core/tenant-manager` | 5 |
| `@/components/filter-rule` | 3 |
| `@/views/retrieve-core/marked-json` | 3 |
| `@/views/retrieve-core/highlight-range` | 3 |
| `@/components/basic-tab` | 3 |
| `@/views/manage-v2/hooks/use-table-setting` | 3 |
| `@/components/monitor-echarts/utils` | 3 |
| `@/views/retrieve-v2/result-comp/download/downloadProgress` | 3 |
| `@/components/collection-access/advance-clean-land` | 2 |
| `@/views/manage-v2/es-cluster/cluster-manage/cluster-type-tabs` | 2 |
| `@/components/log-button` | 2 |
| `@/components/log-icon` | 2 |
| `@/views/un-authorized` | 2 |
| `@/components/collection-access/step-field` | 2 |
| `@/components/index-set-label-select` | 2 |
| `@/views/manage/manage-access/components/usage-details` | 2 |
| `@/components/collection-access/components/log-filter/type` | 2 |
| `@/views/manage-v2/hooks/use-adaptive-pagination` | 2 |
| `@/views/manage-v2/log-collection/components/business-comp/step3/clean-template-picker` | 2 |

## Vue 2 高风险特性

| ID | 命中 | 处置 |
| --- | --- | --- |
| beforeDestroy | 20 | Vue 3 改为 beforeUnmount，P4 前不批量替换 |
| destroyed | 1 | Vue 3 改为 unmounted |
| dollar-on | 3 | 实例事件 API 已移除，改为 mitt 或组件事件；先确认是业务事件还是第三方 |
| dollar-off | 2 | 与 $on 一起替换 |
| dollar-once | 0 | 与 $on 一起替换 |
| dollar-set | 34 | Vue 3 响应式不需要 $set |
| dollar-delete | 2 | 改为 delete 响应式对象属性 |
| dollar-children | 3 | 改为模板 ref 或 provide/inject |
| filters-option | 1 | 过滤器已移除，改为函数或计算属性 |
| vue-filter | 0 | 全局过滤器已移除 |
| vue-prototype | 12 | 改为 app.config.globalProperties |
| vue-mixin | 1 | 全局 mixin 改为组合函数，先逐个核对副作用 |
| slot-scope | 3 | 改为 v-slot |
| sync-modifier | 62 | 改为 v-model 参数 |
| functional-component | 1 | 函数式组件写法改为普通函数组件 |
| new-vue | 4 | 改为 createApp |
| vue-extend | 1 | 改为 defineComponent |

这些是源码文本命中。同名标识符可能造成少量误报，迁移时以对应文件的行号复核，不在本阶段改业务代码。

## 数据流

| 项 | 数量 |
| --- | --- |
| store 文件 | 29 |
| api 文件 | 4 |
| mapState | 35 |
| mapGetters | 97 |
| mapActions | 0 |
| mapMutations | 0 |
| $store | 450 |
| $http | 592 |
| axios import | 15 |
| eventBus / $bus | 0 |

状态入口是 `src/store/index.js`。`Vue.prototype.$http` 在 `src/api/index.js`。事件总线命中要打开对应文件后才能判断是全局总线还是局部变量。

## 样式与组件库

源组件库是 `bk-magic-vue`。模板标签命中 46 种 `bk-*`。

| 标签 | 次数 |
| --- | --- |
| `bk-button` | 983 |
| `bk-form-item` | 655 |
| `bk-table-column` | 618 |
| `bk-input` | 483 |
| `bk-select` | 369 |
| `bk-option` | 283 |
| `bk-form` | 158 |
| `bk-table` | 136 |
| `bk-dialog` | 136 |
| `bk-checkbox` | 133 |
| `bk-radio` | 130 |
| `bk-exception` | 117 |
| `bk-popover` | 89 |
| `bk-radio-group` | 74 |
| `bk-switcher` | 63 |
| `bk-sideslider` | 62 |
| `bk-alert` | 58 |
| `bk-user-display-name` | 49 |
| `bk-tag` | 32 |
| `bk-date-picker` | 29 |

| 样式写法 | 命中 | 处置 |
| --- | --- | --- |
| v-deep | 11 | 改为 :deep() |
| deep-fn | 120 | 已是 Vue 3 推荐写法，迁移时保留 |

## 需要运行时确认

| ID | 命中 | 原因 |
| --- | --- | --- |
| dynamic-component | 12 | 动态组件的真实分支要在运行时确认 |
| dynamic-import | 75 | 懒加载目标要和路由清单对照，不能只看静态 import |
| require-context | 0 | webpack 上下文依赖不能直接当成 Vite 可用 |

静态扫描不能证明权限、接口返回和弹层的真实行为。登录后的页面仍按 P0 的 R-001 阻塞。
