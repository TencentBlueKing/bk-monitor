# @blueking/ai-ui-sdk 使用问题记录

## 问题1：package.json 需要补全 typesVersions 属性

### 背景

SDK 的 `package.json` 已配置 `exports.types` 来导出子路径类型，但当前项目使用 `moduleResolution: "node"`，该模式**不支持 `exports` 的子路径类型解析**，导致子路径导入（如 `@blueking/ai-ui-sdk/components`）无法识别类型。

因此需要同时补充 `typesVersions` 配置，作为 `node` 模式下的兼容兜底：

```json
{
  "types": "dist/main.d.ts",
  "typesVersions": {
    "*": {
      "components": ["./dist/components.d.ts"],
      "enums": ["./dist/enums.d.ts"]
    }
  },
  "exports": {
    "./components": {
      "types": "./dist/components.d.ts",
      "import": "./dist/components.ts.js",
      "require": "./dist/components.ts.js"
    },
    "./enums": {
      "types": "./dist/enums.d.ts",
      "import": "./dist/enums.ts.js",
      "require": "./dist/enums.ts.js"
    }
  }
}
```

### 原理

| `moduleResolution`                      | 生效机制        | 说明                                                          |
| --------------------------------------- | --------------- | ------------------------------------------------------------- |
| `"node"` (`node10`)                     | `typesVersions` | `exports` 被忽略，由 `typesVersions` 兜底映射子路径到 `.d.ts` |
| `"node16"` / `"nodenext"` / `"bundler"` | `exports.types` | 优先遵循 `exports` 规范                                       |

### 结论

当前项目 `moduleResolution: "node"` 下，子路径导入的类型能正常解析，**依赖的是 `typesVersions` 的兼容配置**，而非 `exports`。

---

## 问题2：SDK 编译产物依赖 `bkui-vue` 全局注册，强制宿主项目全量引入

### 背景

`@blueking/ai-ui-sdk` 的组件（如 `RenderResourceDialog`）内部模板直接使用了 `bk-dialog`、`bk-button`、`bk-resize-layout` 等 `bkui-vue` 组件标签，且 `package.json` 将 `bkui-vue` 声明为 `peerDependency`，构建配置也把 `bkui-vue` 设为 **external**，即不把组件代码打包进 SDK 产物，由宿主项目提供。

### 现象

在 `src/trace/index.ts` 中：

- 若执行 `app.use(bkui)`（全量注册 `bkui-vue`），`RenderResourceDialog` 能正常渲染；
- 若去掉 `app.use(bkui)`，仅按需引入宿主页面直接使用的少数组件（如 `Button`、`Message`、`Sideslider`），`RenderResourceDialog` 会失效。

### 根因

**SDK 源码模板里使用了 `<bk-xxx>` 标签，但没有显式 import 这些组件。**

Vue 3 SFC 编译规则是：模板中的自定义组件如果未在 `<script>` 中显式 import，编译后会生成 `_resolveComponent("bk-dialog")`，在运行时从当前 app 实例的**全局组件注册表**里查找；如果显式 import 了，编译后则直接使用组件对象。

查看 SDK 编译产物可以确认这一点：

```js
// node_modules/@blueking/ai-ui-sdk/dist/components/render-dialog/index.script.vue.js
const _component_bk_dialog = _resolveComponent("bk-dialog");
const _component_bk_resize_layout = _resolveComponent("bk-resize-layout");
```

这意味着 SDK 运行时真正依赖的是：

```ts
app.component('bk-dialog', BkDialog);
app.component('bk-resize-layout', BkResizeLayout);
// ...
```

而 `app.use(bkui)` 正是通过遍历所有组件并调用 `app.component()` 完成全局注册，所以全量引入时能命中 `resolveComponent`。当宿主按需引入时，只注册了 `Button`、`Message`、`Sideslider` 等少量组件，`RenderResourceDialog` 需要的 `bk-dialog`、`bk-resize-layout`、`bk-loading`、`bk-popover`、`bk-tag` 等均未注册，`resolveComponent` 失败，组件无法渲染。

### 问题本质

| SDK 侧行为 | 对宿主的隐含要求 |
| --- | --- |
| `bkui-vue` 作为 peer dependency | 宿主需要安装 bkui-vue |
| `bkui-vue` 作为 external | 宿主需要提供 bkui-vue 运行时代码 |
| 模板使用 `resolveComponent("bk-xxx")` | 宿主必须全局注册 bkui-vue 全部相关组件 |

前两条是合理的，第三条把"提供运行时代码"升级成了"必须全量全局注册"，这才是强制宿主全量引入的根源。

### 期望修复方式

SDK 侧应打破对全局注册的依赖，具体做法：

1. **源码中显式 import 组件（最彻底）**

   在 SDK 组件的 `<script setup>` 中显式 import 用到的 `bkui-vue` 组件：

   ```ts
   import { BkDialog, BkResizeLayout } from 'bkui-vue';
   ```

   这样 Vue 编译后会直接使用组件对象，而不是 `resolveComponent("bk-dialog")`。`bkui-vue` 仍可保持 external，宿主只需安装它，无需全量注册。

2. **SDK 提供 install 插件**

   如果保持模板写法不变，SDK 应导出一个 install 函数，在 `app.use(aiUiSdk)` 时主动注册它需要的全部 `bkui-vue` 组件。宿主不需要 `app.use(bkui)`。

3. **组件内部懒注册**

   针对 `import { RenderResourceDialog } from '@blueking/ai-ui-sdk/components'` 这种直接引用子组件的用法，SDK 组件可以在 `setup` 中检查并注册所需组件，避免依赖宿主显式调用 install。

### 结论

问题根源在于 **SDK 编译产物依赖 Vue 全局组件注册机制（`resolveComponent`），而宿主项目按需引入 `bkui-vue` 时无法满足这一假设**。这不是"SDK 已经显式 import 了组件但宿主没引入"，而是"SDK 没有显式 import 组件，导致编译产物使用了字符串组件名解析"。修复应由 SDK 侧在源码/编译层面把对 `bk-xxx` 的引用改为显式 import，或由 SDK 侧承担组件注册职责，从而解除对宿主全量引入 `bkui-vue` 的强制要求。

