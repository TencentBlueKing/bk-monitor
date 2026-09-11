/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/**
 * 从 `src/trace` 打 Vue3 库产物的公共构建配置工厂。
 *
 * ## 背景
 * 原先是三份配置各发一个 npm 包（对外 Vue3 组件、monitor-alarm-center、monitor-trace-explore），
 * 三者源码同出于 `src/trace`、依赖几乎一致，使用方要装三次、版本对齐三次，还各自内联了一份
 * Vue3 / bkui-vue / echarts。现在按**使用方**收敛成两个包，构建选项则由本工厂统一提供：
 *
 * | 包 | 入口 | 面向 |
 * | --- | --- | --- |
 * | `@blueking/monitor-vue3-components` | `src/trace/components.ts` | Vue3 工程用组件与组合式函数 |
 * | `@blueking/apm-vue3-for-vue2` | `src/trace/apm-vue3-for-vue2.ts` | APM 的 Vue2 宿主用 mount* 挂载整块 Vue3 子应用 |
 *
 * 两个包各自独立构建、自包含（因此共享的组件库与图表代码在两个包里各存一份），
 * 但必须共用下面这一套取舍，否则任一条不一致都会在宿主里出问题：
 *
 * 1. **Vue3 运行时必须 external，且以 `@blueking/bkui-library` 为导入名**。
 *    内联会让宿主 runtime 渲染的组件拿不到自己那份 Vue 的 currentInstance，inject / 生命周期全部失效；
 *    而直接 external 裸 `vue` 在 Vue2 宿主里又有解析到 Vue2 的风险（宿主根 node_modules 的 vue 是 v2）。
 *    `@blueking/bkui-library` 是蓝鲸约定的中性包名，内容就是 `export * from '@vue/runtime-dom'`，
 *    Vue2 宿主装它不会与自己的 `vue` 冲突（monitor-pc 已用同样方式承载 Vue3 组件）。
 *    因此这里把源码与内联依赖里的裸 `vue` 统一别名到该包，再把它标成 external。
 *    依赖 vue 的 `pinia` / `vue-router` / `vue-i18n` **全部内联**：它们内部的 `vue` 同样会被别名，
 *    从而与运行时天然同实例，本包也就不必再声明 `vue` 依赖（若它们保持 external，其 peer `vue`
 *    在 Vue2 宿主里会回落到宿主根目录的 v2，直接崩）。
 *    注意 vue-i18n 内联后，使用方的 i18n 实例必须来自包内导出的 `i18n`，否则 `useI18n()` 因
 *    注入 key 属于不同副本而报错——这也是 `components.ts` 要把 i18n 一并导出的原因。
 * 2. **bkui-vue / tdesign 必须内联**。external 就无法在构建期改写它们的 CSS 类名，
 *    而 Vue2 宿主页面自带一套同名 `.bk-*` 样式，两者会互相污染。
 * 3. **`monitor-*` 全部 external**（api / common / ui / pc / static）。
 *    由使用方（本仓库的 APM 宿主经 pnpm workspace 软链）提供同一份实现：`monitor-api` 尤其不能
 *    内联，否则宿主里会出现两份请求层，各自一套 axios 拦截器与登录态；`monitor-static` 外置还能
 *    省掉图标字体在 CSS 里的 base64 内联（库模式下 Vite 会强制内联资源）。
 *    代价是这两个包都无法脱离蓝鲸监控工程独立使用。
 * 4. **`@blueking/monitor-trace-log` 必须 external**。它已是日志侧打好的 webpack CJS（main.js + css），
 *    内联会让 Vite 再解析一遍（产物多出十几万行 chunk，构建明显变慢），还会把包内
 *    `require("echarts")` 转成错误的 ESM default。宿主 webpack 直接吃这份 CJS 即可，
 *    与 `@blueking/monitor-apm-log` 同一路。
 * 5. **类名整体改前缀**（见 CLASS_PREFIX）：源码里的类名 token 与编译后 CSS 选择器一起改，
 *    再由入口把 bkui-vue 运行时前缀设成同一个值，做到在任何宿主里都不与 `.bk-*` 冲突。
 * 6. **不再有条件编译**。原先的 `IS_APM_MONITOR` 差异已全部改为运行时判断，
 *    见 `src/trace/common/embed-context.ts`。
 */
import vueTsx from '@vitejs/plugin-vue-jsx';
import { resolve } from 'node:path';
import { analyzer } from 'vite-bundle-analyzer';
import { viteStaticCopy } from 'vite-plugin-static-copy';

import type { Plugin as PostcssPlugin } from 'postcss';
import type { UserConfig, Plugin as VitePlugin } from 'vite';

const traceDir = resolve(__dirname, '../../src/trace');

/** 单个发布包的差异项，其余构建选项由本工厂统一给出 */
interface Vue3LibOptions {
  /** 库入口源文件绝对路径 */
  entry: string;
  /** 产物目录绝对路径（JS / CSS / chunk） */
  outputDir: string;
  /**
   * 随包元数据落地目录，默认等于 outputDir。
   * workspace 包把 JS 打进 dist/、package.json 留在包根时，传入包根路径。
   */
  metaDir?: string;
  /** 要拷贝到 metaDir 的 package.json；省略则不拷（包根已提交 package.json 时） */
  packageJsonFile?: string;
  /** 随产物一起发布的说明文档绝对路径，会重命名为 readme.md */
  readmeFile: string;
}

/**
 * 蓝鲸组件库类名前缀。
 * 宿主页面可能已有一套 Vue2 版 `.bk-*` 样式，同名不同实现会互相覆盖，
 * 因此本包把自己用到的 `bk-` 类名整体改名到该前缀下，与宿主彻底隔离。
 */
const CLASS_PREFIX = 'bkmv3-';

/**
 * Vue3 运行时的对外导入名。
 * 该包内容即 `export * from '@vue/runtime-dom'`，用中性包名避免与 Vue2 宿主自带的 `vue` 撞车。
 */
const VUE_RUNTIME_PACKAGE = '@blueking/bkui-library';

/**
 * 自定义元素名不参与前缀改写。
 * `bk-user-display-name` 由 @blueking/bk-user-display-name 在 node_modules 内注册（不会被改写），
 * 若源码里的同名字符串被改写，customElements 注册名与模板标签就对不上了。
 */
const PRESERVED_TOKEN = 'bk-user-display-name';

export function createVue3LibConfig({
  entry,
  outputDir,
  metaDir,
  packageJsonFile,
  readmeFile,
}: Vue3LibOptions): UserConfig {
  const copyDest = metaDir ?? outputDir;
  const copyTargets = [
    ...(packageJsonFile
      ? [{ src: packageJsonFile, dest: copyDest, rename: 'package.json' }]
      : []),
    { src: readmeFile, dest: copyDest, rename: 'readme.md' },
  ];
  return {
    define: {
      // 内联进来的 monitor-* 代码会读取这两个变量
      'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV),
      'process.env.APP': JSON.stringify(''),
    },
    resolve: {
      alias: [
        { find: '@store', replacement: resolve(traceDir, 'store') },
        { find: '@', replacement: traceDir },
        { find: 'trace', replacement: traceDir },
        /**
         * 精确匹配裸 `vue`（不影响 `vue-router` / `vue-i18n` 等），连同内联依赖（bkui-vue、tdesign 等）
         * 一起改为从 VUE_RUNTIME_PACKAGE 取运行时，保证产物里只有一个 Vue3 实例来源。
         */
        { find: /^vue$/, replacement: VUE_RUNTIME_PACKAGE },
        /**
         * fork-mermaid 默认入口 mermaid.core.mjs 里的 `import { select } from "d3"` 是裸路径，
         * 会交给宿主打包器解析；宿主未装 d3 或版本不匹配时，序列图的 d3 操作会全部返回空 selection。
         * 指向 mermaid.esm.mjs 可让 d3 自包含在同一 bundle 内。
         */
        {
          find: 'fork-mermaid',
          replacement: resolve(traceDir, 'node_modules/fork-mermaid/dist/mermaid.esm.mjs'),
        },
      ],
    },
    plugins: [
      classPrefixSourcePlugin(),
      // svgRequireInlinePlugin(),
      // patchTDesignPopupTimingPlugin(),
      vueTsx({
        /** 与 Vue 文档一致：TSX 中自定义标签默认会走 resolveComponent，需显式标成 custom element */
        isCustomElement: tag => tag === PRESERVED_TOKEN,
      }),
      // flattenCssVarsInPseudoElementRulesPlugin(),
      viteStaticCopy({
        targets: copyTargets,
      }),
      // 体积分析默认关闭：会打开浏览器并写出报告。与主站 `bkmonitor-cli build -a` 对齐，
      // 只在命令行带 `-a` / `--analyze` 时开启（pnpm build:apm-vue3-for-vue2 -- -a）
      process.argv.includes('-a') || process.argv.includes('--analyze') ? analyzer() : null,
    ],
    css: {
      postcss: {
        plugins: [classPrefixPostcssPlugin()],
      },
    },
    build: {
      /** 不拷贝项目根 public：库产物不应包含站点级静态资源 */
      copyPublicDir: false,
      /** 每次构建前清空，避免改名入口或删源码后旧 chunk 残留 */
      emptyOutDir: true,
      outDir: outputDir,
      /** 库会被宿主二次打包；保留可读性便于排查，也避免与宿主压缩链重复处理 */
      minify: false,
      /** 字体、图片等资源统一放这里，随包发布（见 package.json 的 files） */
      assetsDir: 'assets',
      /**
       * 仍把 echarts 当成 ESM external：其它 CJS 依赖若 `require("echarts")`，Rollup 默认会写成
       * `import x from "echarts"`。echarts 5 的 ESM 入口只有 named export，Vue2 宿主二次打包会报
       * `export 'default' was not found in 'echarts'`。
       * 不能全局 `esmExternals: true`：dayjs plugin 等真正的 CJS default 会被改坏。
       */
      commonjsOptions: {
        esmExternals: (id: string) => id === 'echarts' || id.startsWith('echarts/'),
      },
      lib: {
        entry,
        name: 'monitor-vue3-lib',
        /**
         * 产物用 `.js` 而非 Rollup 默认的 `.mjs`：宿主（APM 主站的 webpack）解析来自 `.mjs`
         * 的 import 时会启用 fullySpecified，要求 `monitor-api/api`、`dayjs/plugin/utc` 这类
         * 无后缀子路径也带扩展名，会整包报错。`.js` 在未声明 `"type":"module"` 的目录下按
         * javascript/auto 处理，与主站其它 TS 入口一致。
         */
        fileName: () => 'index.js',
        cssFileName: 'index',
        formats: ['es'],
      },
      rollupOptions: {
        output: {
          chunkFileNames: '[name]-[hash].js',
        },
        /**
         * external 分三类：
         * - Vue3 运行时（@blueking/bkui-library）—— 必须与使用方保持单实例；
         * - 不依赖 vue 的重型库（echarts / monaco / dayjs / toast-ui / promql 语法）—— 宿主往往已有一份，
         *   重复打包会显著增大体积；
         * - 工程内公共包 monitor-*（api / common / ui / pc / static）—— 由使用方提供同一份实现，
         *   避免请求层等有状态模块出现双实例，也避免图标字体被内联进 CSS。
         * - `@blueking/monitor-trace-log` —— 已是预编译 CJS，交给宿主 webpack，避免 Vite 二次解析；
         * 其余（bkui-vue、tdesign、pinia、vue-router、vue-i18n、其它 @blueking/*）一律内联，
         * 见文件头说明。
         */
        external: [
          VUE_RUNTIME_PACKAGE,
          /^echarts[/]?[\w/]*/,
          /^monaco-editor[/]?[\w/]*/,
          /^dayjs[/]?[\w/]*/,
          /^@toast-ui\/editor(\/.*)?$/,
          /^@toast-ui\/editor-plugin-code-syntax-highlight(\/.*)?$/,
          '@prometheus-io/lezer-promql',
          /^@blueking\/monitor-trace-log(\/.*)?$/,
          /^monitor-api(\/.*)?$/,
          /^monitor-common(\/.*)?$/,
          /^monitor-ui(\/.*)?$/,
          /^monitor-pc(\/.*)?$/,
          /^monitor-static(\/.*)?$/,
        ],
      },
    },
  };
}

/**
 * PostCSS 插件：在样式已展开为最终选择器后，把类选择器里的 `.bk-` 换成 CLASS_PREFIX。
 * 与源码侧插件成对使用：源码侧改模板/TSX 里的类名字符串，这里改编译后 CSS 的选择器，
 * 覆盖范围包含 bkui-vue、tdesign 等第三方样式。
 */
function classPrefixPostcssPlugin(): PostcssPlugin {
  return {
    postcssPlugin: 'class-prefix',
    /** OnceExit：所有规则展开完毕后再改 selector，避免与嵌套插件的顺序问题 */
    OnceExit(root) {
      root.walkRules(rule => {
        if (rule.selector) {
          // 仅替换类选择器片段 .bk-，不动标签名
          rule.selector = rule.selector.replace(/\.bk-/g, `.${CLASS_PREFIX}`);
        }
      });
    },
  };
}

/**
 * Vite 插件：把源码中作为类名的 `bk-` token 改写为 CLASS_PREFIX。
 *
 * - `enforce: 'pre'`：在 JSX / 预处理器之前做字符串级替换，避免与其它转换互相干扰。
 * - 负向后顾 `(?<![</\w-])` 排除标签名（`<bk-button`）、`v-bk-*`、单词内部以及已带前缀的片段；
 *   正向前瞻 `(?=[a-z0-9])` 约束为类名 token 起始。
 * - `node_modules` 跳过（bkui-vue 等第三方样式由 postcss 侧统一处理）；
 *   `monitor-*` 虽由 node_modules 软链引入，但解析后的真实路径在 src 下，因此同样会被改写。
 */
function classPrefixSourcePlugin(): VitePlugin {
  const classTokenRe = /(?<![</\w-])bk-(?=[a-z0-9])/g;
  return {
    name: 'vite-plugin-class-prefix-source',
    enforce: 'pre',
    transform(code: string, id: string) {
      if (/node_modules/.test(id)) return;
      // 去掉 ?vue、?raw 等查询串，仅按真实文件后缀判断是否参与替换
      const pathOnly = id.split('?')[0];
      if (!/\.(m?[tj]sx?|vue|scss)$/.test(pathOnly)) return;
      // 无 bk- 子串则跳过后续正则，减轻大文件成本
      if (!code.includes('bk-')) return;
      const next = code.replace(classTokenRe, (matched, offset: number) =>
        code.startsWith(PRESERVED_TOKEN, offset) ? matched : CLASS_PREFIX
      );
      if (next === code) return;
      // 不生成 sourcemap：纯等长字符串替换，行号与源码一致
      return { code: next, map: null };
    },
  };
}
