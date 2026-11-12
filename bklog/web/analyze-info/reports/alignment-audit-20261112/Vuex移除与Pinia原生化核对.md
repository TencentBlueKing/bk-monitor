# Vuex 移除与 Pinia 原生化核对

实施更新（2026-11-12 批次 03）：根状态及内部旧调用清理已落地，详见 [实施记录-03-根状态原生Pinia与Monitor聚类验证](实施记录-03-根状态原生Pinia与Monitor聚类验证.md)。历史分析继续保留；全业务、统一视口视觉及真实 APM/Trace 宿主链路仍未全部验收。

日期：2026-11-12。本次为源码与依赖核查，未修改业务状态实现。

## 当前事实

1. `packages/web-v3/package.json` 同时声明 Pinia 4.1.0（dependencies）和 Vuex 4.1.0（devDependencies），并保留 vuex peerDependencyRules。根 web/package.json 和 pnpm-lock.yaml 中也有对应声明。实际安装的 Pinia 包版本为 4.1.0。
2. V3 src 中未发现直接导入 Vuex 或创建 Vuex Store 的代码。`app/state/index.ts` 调用 useApplicationStores，最终由 `platform/state/domain-store.ts` 的 defineStore 创建真实 Pinia store。
3. `app/bootstrap/start.js` 的 app.use(store) 安装的是本地兼容对象，其 `platform/state/state-runtime.ts` install 调用 app.use(pinia) 并挂载 `$store`，不是安装 Vuex。
4. 业务仍大量使用 `$store/state/getters/commit/dispatch`、命名空间字符串及本地 mapState/mapGetters。`shared/composables/use-store.ts` 返回兼容对象；`application-runtime.ts` 仍将旧 state/getters/mutations/actions 定义交给通用转换器。因此是“Pinia 持有状态、旧式调用仍经过兼容边界”的过渡状态，不能标为业务已全部原生 Pinia 化。

## 用户确认的最终目标

V3 移除 Vuex，业务状态全部使用原生 Pinia；不以删除依赖声明或保留同形兼容库作为最终完成。

## 后续落地要求

- 为 application/retrieve/collect/globals、platform-config/report-log 等实际域列出状态、派生值、写入、异步 action、跨域调用和外部消费者，保留 V2 业务语义与副作用。
- 逐域建立明确的 useXxxStore、命名 action 和 getter；旧 mutation 行为迁为 action 或明确状态赋值，不再由通用转换器运行旧定义。
- 业务调用改为直接 store 属性、storeToRefs 和具名 action，移除字符串 commit/dispatch、全局 `$store`、旧命名空间查找及自制 map-helpers。非组件调用使用明确 Pinia 实例，避免多实例状态串用。
- 主应用、APM/Trace 独立入口及已发布消费者共同核对。若对外协议需要保留旧结构，仅允许在明确的外部边界提供经过验证的适配，不让 V3 内部业务继续依赖它。
- 调用方与消费者迁移通过后，再删除 state-runtime/domain-store 中的旧协议转换、本地 map-helpers、相关类型和无用代码，清理 V3 与根工程不再需要的 Vuex 声明、peer 规则和锁文件 importer。
- V2、封版 V1 或第三方包的 Vuex 传递依赖必须另行归属，不能为清零字面文本而破坏对照环境或旧版产物。最终检查重点是 V3 自身依赖、业务源码和运行产物均不依赖 Vuex。

## 完成判断

原生 Pinia store 是唯一状态来源；V3 业务不再通过 Vuex 形式的兼容对象工作；异步返回值、失败、取消、持久化、跨域状态与原行为一致；多 Pinia 实例隔离、路由恢复、主应用及 APM/Trace 通过验证。此前 Pinia 底层测试通过，只能证明当前过渡层的对应断言，不能替代以上完成条件。
