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
 * monitor-trace-explore 独立库的 Vite 构建配置。
 *
 * ## 背景与目标
 * - 将 Trace 检索相关 UI 以 **库模式（lib mode）** 打成单一 ES 模块 `index.js`，由 APM 等宿主在运行时
 *   `import`，而不是与主站整包打进同一个 bundle。
 * - 好处：宿主可复用已有 Vue / 路由 / i18n 实例；本库只承载 Trace 检索业务代码，体积与升级面更可控。
 *
 * ## 与本仓库其它构建的关系
 * - 主 trace 应用仍由 webpack 构建；本脚本是 **旁路产物**，专供「嵌入 APM」场景。
 * - `resolve.alias` 把 `vue`、`vue-router`、`vue-i18n` 指到 `src/trace/node_modules`，与 trace 子应用
 *   锁定的版本一致，避免宿主与本库各解析到一份不同 minor 的 Vue。
 *
 * ## 产物位置与入口
 * - 输出目录：`bkmonitor/webpack/monitor-trace-explore/`（见下方 `outputDir`）。
 * - 库入口：`src/trace/pages/trace-explore/trace-explore-apm-entry`（对外导出可被宿主消费的 API）。
 *
 * ## 类名前缀隔离策略
 * 宿主 APM 为 Vue 2 应用，其 .bk-* CSS 来自 Vue 2 组件库；本库使用 bkui-vue（Vue 3 组件库），
 * 两者类名相同但样式不同，会互相污染。因此需要将 bkui-vue 的类名与样式统一加上 apm- 前缀：
 *
 * 1. apmBkClassPrefixPostcssPlugin — 将 bkui-vue CSS 中的 .bk- 选择器重命名为 .apm-bk-。
 * 2. apmBkClassPrefixSourcePlugin — 将业务源码中引用的 bk- 类名 token 替换为 apm-bk-。
 * 3. provideGlobalConfig({ prefix: 'apm-bk' }) — 运行时为主 app 注入前缀并设置 --bk-prefix CSS 变量。
 */
import vueTsx from '@vitejs/plugin-vue-jsx';
import { resolve } from 'node:path';
import { parse as ifdefParse } from 'ifdef-loader/preprocessor';
import type { Plugin as PostcssPlugin } from 'postcss';
import type { Plugin as VitePlugin } from 'vite';
import { defineConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { viteStaticCopy } from 'vite-plugin-static-copy';

const outputDir = resolve(__dirname, '../../monitor-trace-explore');

export default defineConfig({
  define: {
    __VUE_OPTIONS_API__: 'true',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
  },
  resolve: {
    // 强制所有依赖共享同一份 Vue 实例，避免宿主 Vue2 环境下因多副本导致 inject/provide 失效等问题
    dedupe: ['vue', '@vue/runtime-core', '@vue/runtime-dom', '@vue/reactivity', '@vue/shared'],
    alias: [
      { find: '@store', replacement: resolve(__dirname, '../../src/trace/store') },
      { find: '@', replacement: resolve(__dirname, '../../src/trace') },
      { find: 'trace', replacement: resolve(__dirname, '../../src/trace') },
      {
        find: 'vue',
        replacement: resolve(__dirname, '../../src/trace/node_modules/vue/dist/vue.esm-bundler.js'),
      },
      {
        find: 'vue-router',
        replacement: resolve(__dirname, '../../src/trace/node_modules/vue-router/dist/vue-router.mjs'),
      },
      {
        find: 'vue-i18n',
        replacement: resolve(__dirname, '../../src/trace/node_modules/vue-i18n/dist/vue-i18n.mjs'),
      },
      /**
       * fork-mermaid 发布了两种 dist 格式：
       * 入口	sequence diagram 的 select 来源	效果
       * mermaid.core.mjs (默认)
       * import { select } from "d3" — 裸路径，由宿主 webpack 解析
       * 宿主可能解析到错误/缺失的 d3
       * mermaid.esm.mjs
       * import { q as select } from "./mermaid-aafb0501.js" — 相对路径，同 bundle
       * d3 自包含，永远正确
       * 之前无论是 Vite 打包还是外置到宿主 webpack，
       * 序列图 chunk 里的 import { select } from "d3" 始终作为一个裸路径 bare specifier 被宿主 webpack 独立解析。
       * 宿主 Vue2 APM 项目如果没有安装 d3 或版本不匹配，
       * select 函数就会异常，导致所有 d3 DOM 操作返回空 selection，.node() 为 null，最终 getBBox() 报错。
       */
      {
        find: 'fork-mermaid',
        replacement: resolve(__dirname, '../../src/trace/node_modules/fork-mermaid/dist/mermaid.esm.mjs'),
      },
    ],
  },
  plugins: [
    ifdefPlugin(),
    apmBkClassPrefixSourcePlugin(),
    vueTsx({
      /** 与 Vue 文档一致：TSX 中自定义标签默认会走 resolveComponent，需显式标成 custom element */
      isCustomElement: tag => tag === 'bk-user-display-name',
    }),
    viteStaticCopy({
      targets: [
        {
          src: resolve(__dirname, './package.json'),
          dest: outputDir,
        },
      ],
    }),
    cssInjectedByJsPlugin(),
  ],
  css: {
    postcss: {
      plugins: [apmBkClassPrefixPostcssPlugin()],
    },
  },
  build: {
    copyPublicDir: false,
    emptyOutDir: true,
    outDir: outputDir,
    minify: false,
    lib: {
      entry: resolve(__dirname, '../../src/trace/pages/trace-explore/trace-explore-apm-entry'),
      name: 'monitor-trace-explore',
      fileName: () => 'index.js',
      formats: ['es'],
    },
    rollupOptions: {
      /**
       * 拆包文件名必须用 `.js` 而非 Rollup/Vite 默认的 `.mjs`。
       * 宿主（APM 主站的 webpack）在解析来自 `.mjs` 的 `import` 时会启用 fullySpecified，
       * 要求 `monitor-*` / `dayjs/*` 等裸路径也带扩展名，而工程别名解析的是无后缀的 `.ts`/`.js`，
       * 会整包报错。`.js` chunk 在未声明 `"type":"module"` 的目录下按 `javascript/auto` 处理，
       * 与主站其它 TS 入口一致，可正常解析别名。
       */
      output: {
        chunkFileNames: '[name]-[hash].js',
      },
      external: [
        /^dayjs[/]?\w*/,
        '@prometheus-io/lezer-promql',
        /^monaco-editor[/]?\w*/,
        /^monitor-api\/.*/,
        /^monitor-common\/.*/,
        /^monitor-pc\/.*/,
        /^monitor-ui\/.*/,
        /^monitor-static\/.*/,
      ],
    },
  },
});

/**
 * PostCSS 插件：将 bkui-vue 样式中的 .bk- 选择器重命名为 .apm-bk-，
 * 避免与宿主 Vue 2 组件库的 .bk-* 样式互相污染。
 * 仅处理 bkui-vue 的 CSS，不影响业务样式（业务样式由 source 插件处理）。
 */
function apmBkClassPrefixPostcssPlugin(): PostcssPlugin {
  return {
    postcssPlugin: 'apm-bk-class-prefix',
    OnceExit(root) {
      const filePath = root.source?.input?.file ?? '';
      if (!filePath.includes('bkui-vue')) return;
      root.walkRules(rule => {
        if (rule.selector) {
          rule.selector = rule.selector.replace(/\.bk-/g, '.apm-bk-');
        }
      });
    },
  };
}

/**
 * Vite 插件：将业务源码中作为类名的 bk- token 替换为 apm-bk-。
 * 仅处理非 node_modules 的 TS/TSX/Vue/SCSS 文件，不影响 bkui-vue 自身。
 */
function apmBkClassPrefixSourcePlugin(): VitePlugin {
  const apmBkClassTokenRe = /(?<![</\w-])bk-(?=[a-z0-9])/g;
  return {
    name: 'vite-plugin-apm-bk-class-prefix-source',
    enforce: 'pre',
    transform(code: string, id: string) {
      if (/node_modules/.test(id)) return;
      const pathOnly = id.split('?')[0];
      if (!/\.(m?[tj]sx?|vue|scss)$/.test(pathOnly)) return;
      if (!code.includes('bk-')) return;
      const next = code.replace(apmBkClassTokenRe, 'apm-bk-');
      if (next === code) return;
      return { code: next, map: null };
    },
  };
}

/**
 * Vite 插件：复用 `ifdef-loader/preprocessor` 的 `parse`。
 *
 * - **本脚本（告警中心 lib）**：`IS_APM_MONITOR: true`，专打嵌入 APM 的产物。
 * - **trace 主站 webpack**：`trace-ifdef-webpack.js`（本目录，由 `webpack.config.js` require），
 *   `IS_APM_MONITOR: false`，与下方 JSX 预处理及 ifdef 选项保持一致。
 * - JSX 预处理：将 JSX 块注释里包住的 `#if / elif / else / endif` 行展开为独立行（与 webpack 侧同正则）。
 */
function ifdefPlugin(): VitePlugin {
  /** 与业务源码中 `#if IS_APM_MONITOR` 等条件对应；本脚本专打 APM 库，故固定为 true。 */
  const defs = {
    IS_APM_MONITOR: true,
  };
  return {
    name: 'vite-plugin-ifdef',
    /**
     * 必须在 Sass/Less 等预处理器之前执行：`// #if` 在 SCSS 里是合法注释，若先被编译，
     * 指令行会被删掉而块内样式仍保留，条件编译会「永远不生效」。
     */
    enforce: 'pre',
    transform(code: string, id: string) {
      // 依赖方未使用条件编译时直接跳过；node_modules 内通常不含本工程 ifdef 语法
      if (/node_modules/.test(id) || !code.includes('#if')) return;
      // 将 JSX 中形如 { /* // #if ... */ } 的注释块展开成独立行，便于 ifdef 预处理器按行解析
      const normalized = code.replace(/\{\/\*\s*(\/\/\s*#(?:if|elif|else|endif)[^\n]*?)\s*\*\/\}/g, '$1');
      return {
        code: ifdefParse(
          normalized,
          defs,
          true, // verbose：分支判断失败时输出诊断信息
          false, // tripleSlash：false 表示使用 // #if 而非 /// #if
          id, // filePath：报错与日志中展示模块 id
          true, // fillWithBlanks：删除分支时用空格占位，避免行号剧烈偏移
          '// #code ' // uncommentPrefixString：与 webpack ifdef-loader 一致的行内前缀
        ),
        map: null,
      };
    },
  };
}
