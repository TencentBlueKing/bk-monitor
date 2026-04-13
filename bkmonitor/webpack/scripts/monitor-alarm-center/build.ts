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
 * monitor-alarm-center 独立库的 Vite 构建配置。
 *
 * ## 背景与目标
 * - 将告警中心相关 UI 以 **库模式（lib mode）** 打成单一 ES 模块 `index.js`，由 APM 等宿主在运行时
 *   `import`，而不是与主站整包打进同一个 bundle。
 * - 好处：宿主可复用已有 Vue / 路由 / i18n 实例；本库只承载告警中心业务代码，体积与升级面更可控。
 *
 * ## 与本仓库其它构建的关系
 * - 主 trace 应用仍由 webpack 构建；本脚本是 **旁路产物**，专供「嵌入 APM」场景。
 * - `resolve.alias` 把 `vue`、`vue-router`、`vue-i18n` 指到 `src/trace/node_modules`，与 trace 子应用
 *   锁定的版本一致，避免宿主与本库各解析到一份不同 minor 的 Vue。
 *
 * ## 产物位置与入口
 * - 输出目录：`bkmonitor/webpack/monitor-alarm-center/`（见下方 `outputDir`）。
 * - 库入口：`src/trace/pages/alarm-center/alarm-center-apm-entry`（对外导出可被宿主消费的 API）。
 */
import vueTsx from '@vitejs/plugin-vue-jsx';
import { parse as ifdefParse } from 'ifdef-loader/preprocessor';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import type { Plugin as PostcssPlugin } from 'postcss';
import type { Plugin as VitePlugin } from 'vite';
import { defineConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { viteStaticCopy } from 'vite-plugin-static-copy';

/**
 * 库构建输出根目录（相对本脚本所在目录解析为 `webpack/monitor-alarm-center`）。
 * 与 `viteStaticCopy` 复制的 `package.json`、Rollup 输出的 `index.js` 同处一层，便于作为 npm 包或静态资源目录发布。
 */
const outputDir = resolve(__dirname, '../../monitor-alarm-center');

export default defineConfig({
  /**
   * 编译期注入的全局常量（等价于 webpack DefinePlugin）。
   * - `__VUE_OPTIONS_API__`：告警中心仍可能混用 Options API 写法，需为 true，否则相关代码会被摇树裁掉。
   * - `__VUE_PROD_DEVTOOLS__`：生产包不应挂载 Vue DevTools 后端，false 减小体积并避免意外暴露。
   * - `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__`：SSR/注水场景外的纯 CSR 库可关详细 mismatch 日志，减包体。
   * 显式写出可避免不同 Vite/Vue 版本默认值差异导致的「本地与 CI 行为不一致」。
   */
  define: {
    __VUE_OPTIONS_API__: 'true',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
  },
  resolve: {
    /**
     * 解析去重：即使依赖图里出现多份 `vue` / `@vue/*`（例如 workspace + 嵌套 node_modules），
     * Rollup 也会尽量合并到同一物理模块，避免出现 **两个 Vue 运行时**（响应式对象不互通、inject/provide 失效等）。
     */
    dedupe: ['vue', '@vue/runtime-core', '@vue/runtime-dom', '@vue/reactivity', '@vue/shared'],
    /**
     * 路径别名（顺序自上而下匹配）：
     * - `@` / `trace`：与 trace 源码中的模块路径约定一致，避免为库单独维护一套目录结构。
     * - `@store`：trace 内 Pinia store 的快捷入口。
     * - `vue*`：强制使用 trace 子包安装的 ESM 构建（`vue.esm-bundler.js` 等），与宿主侧期望的编译特性对齐。
     */
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
    ],
  },
  /**
   * 插件流水线（顺序敏感）：
   * 1. `ifdefPlugin` — 条件编译，先砍掉无关分支，减轻后续插件工作量。
   * 2. `apmBkClassPrefixSourcePlugin` — 源码里蓝鲸类名加 `apm-` 前缀，需在 JSX/TS 解析前完成字符串级改写。
   * 3. `svgRequireInlinePlugin` — 将 webpack 风格的 `require('*.svg')` 转为 data URL，避免 Rollup 无法解析 require。
   * 4. `patchTDesignPopupTimingPlugin` — 对 tdesign-vue-next 的 Popup 做补丁，修复 Vue2 宿主嵌 Vue3 时的交互问题。
   * 5. `vueTsx` — 编译 `.tsx` / Vue SFC 中的 TSX。
   * 6. `viteStaticCopy` — 把本脚本旁的 `package.json` 复制到产物根，便于版本与依赖元数据对齐。
   * 7. `cssInjectedByJsPlugin` — 构建结束时把 CSS 注入到 JS 入口，宿主只需 `import` 一个模块即可带上样式。
   */
  plugins: [
    ifdefPlugin(),
    apmBkClassPrefixSourcePlugin(),
    svgRequireInlinePlugin(),
    patchTDesignPopupTimingPlugin(),
    vueTsx({}),
    viteStaticCopy({
      targets: [
        {
          /** 发布/对齐依赖声明用，与构建出的 `index.js` 同目录。 */
          src: resolve(__dirname, './package.json'),
          dest: outputDir,
        },
      ],
    }),
    cssInjectedByJsPlugin({
      /**
       * 在 CSS 注入前对字符串做最后一道处理（PostCSS 已跑完之后的「整段 CSS 文本」阶段）。
       * 背景：部分宿主用 Vue2/webpack 再次处理本库注入的 CSS 时，会错误拆分包含伪元素与 CSS 变量的规则；
       * 这里只在「选择器含 ::after/::before」的规则块内递归展开 `var(--x)`，减少对全局样式的侵入。
       */
      preRenderCSSCode(cssCode: string) {
        return replaceVarsInPseudoElementRulesOnly(cssCode);
      },
    }),
  ],
  css: {
    postcss: {
      /**
       * 与 `apmBkClassPrefixSourcePlugin` 成对使用：前者改 **模板/TSX 里的类名字符串**，
       * 此处改 **已编译 CSS 中的 `.bk-*` 选择器**，避免嵌入 APM 页面时与页面其它蓝鲸组件的样式层叠冲突。
       */
      plugins: [apmBkClassPrefixPostcssPlugin()],
    },
  },
  build: {
    /** 不拷贝项目根 `public`：库产物不应包含站点级静态资源。 */
    copyPublicDir: false,
    /** 每次构建前清空 `outDir`，避免重命名入口或删源码后旧 chunk 残留在产物目录。 */
    emptyOutDir: true,
    outDir: outputDir,
    /**
     * 不启用 terser/esbuild 压缩：库会被宿主二次打包；保留可读性便于排查与 sourcemap 对齐，
     * 也避免与宿主压缩链重复处理带来的调试困难。
     */
    minify: false,
    lib: {
      /** 单入口 ESM 库：对外暴露的 API 以该文件及其静态依赖为准。 */
      entry: resolve(__dirname, '../../src/trace/pages/alarm-center/alarm-center-apm-entry'),
      /** Rollup `output.name`：若将来生成 IIFE/UMD 时作为全局变量名；当前 `formats: ['es']` 下影响较小。 */
      name: 'monitor-alarm-center',
      fileName: () => 'index.js',
      /** 仅输出 ES 模块，便于宿主按 ESM 规范做静态分析与 tree-shaking。 */
      formats: ['es'],
    },
    rollupOptions: {
      /**
       * 标记为 external 的模块不会被打进 `index.js`，而是保留为 `import 'xxx'` 由宿主解析。
       * - `dayjs` / `monaco-*`：体积大、且宿主往往已有一份，重复打包会显著增大体积并可能导致多实例。
       * - `monitor-*`：工程内其它子包，由宿主统一提供路径别名或打包进主包，避免库内再嵌一份。
       * 正则形式用于匹配带子路径的导入（如 `dayjs/plugin/utc`、`monitor-ui/xxx`）。
       */
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
 * 扫描整段 CSS 文本，收集所有自定义属性声明 `--name: value` 到字典。
 * 后续仅在伪元素相关规则体内用该表做 `var(--name)` 展开；**不**尝试做完整 CSS 解析，以控制实现复杂度。
 */
function extractCssVarMap(cssCode: string): Record<string, string> {
  const cssVarMap: Record<string, string> = {};
  // 要求 `--` 出现在行首、分号后或空白后，降低把普通值里的 `--` 误当成变量名的概率
  const cssVarDeclRe = /(^|[;{\s])(--[\w-]+)\s*:\s*([^;{}]+);/g;
  let matched: RegExpExecArray | null = cssVarDeclRe.exec(cssCode);
  while (matched) {
    // matched[2] 是变量名（--xxx），matched[3] 是原始值（可能仍包含 var()）
    cssVarMap[matched[2]] = matched[3].trim();
    matched = cssVarDeclRe.exec(cssCode);
  }
  return cssVarMap;
}

/**
 * 判断「选择器文本」是否涉及伪元素 `::after` / `::before`（含单冒号旧写法 `:after`/`:before`）。
 * `[^:]:(after|before)` 用于区分类名中的子串（如 `.foo:before-bar` 不应命中）。
 */
function selectorHasPseudoAfterBefore(selector: string): boolean {
  return /::after\b|::before\b|[^:]:(after|before)\b/.test(selector);
}

/**
 * 在单个规则块 **声明体**（花括号内、非嵌套片段）中，将 `var(--token)` 按 `cssVarMap` 递归替换为具体值。
 * 找不到定义或存在循环依赖时保留原始 `var(...)`，避免生成非法 CSS。
 */
function replaceVarsInDeclarations(declarations: string, cssVarMap: Record<string, string>): string {
  // `seen`：同一展开链上已访问过的变量名，用于打破 `var(--a)`→`var(--b)`→`var(--a)` 的死循环
  const resolveValue = (value: string, seen: Set<string>): string => {
    return value.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_, varName: string) => {
      if (seen.has(varName)) return `var(${varName})`;
      const raw = cssVarMap[varName];
      if (!raw) return `var(${varName})`;
      seen.add(varName);
      const resolved = resolveValue(raw, seen);
      seen.delete(varName);
      return resolved;
    });
  };

  // 第一层替换：声明串里出现的每个 var(--x) 都尝试向下解析
  return declarations.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_, varName: string) => {
    const raw = cssVarMap[varName];
    if (!raw) return `var(${varName})`;
    return resolveValue(raw, new Set([varName]));
  });
}

/**
 * 剥离样式表最前面的 `@charset` 与连续 `@import`，剩余部分再按 `{`/`}` 做规则块遍历。
 * 若不先剥离，`@charset "utf-8";` 等可能被 naive 的 `{` 定位误当成选择器前缀。
 */
function splitLeadingCharsetAndImports(cssCode: string): { head: string; body: string } {
  let rest = cssCode;
  let head = '';
  // @charset 只能出现在样式最前面，这里先剥离，避免后续按 `{` 切规则时被混入 selector 文本
  const ch = rest.match(/^\s*@charset\s+[^;]+;/i);
  if (ch) {
    head += ch[0];
    rest = rest.slice(ch[0].length);
  }
  // 连续剥离头部 @import，保留原顺序，后续再与处理后的 body 拼回
  while (/^\s*@import\s+[^;]+;/i.test(rest)) {
    const imp = rest.match(/^\s*@import\s+[^;]+;/i);
    if (!imp) break;
    head += imp[0];
    rest = rest.slice(imp[0].length);
  }
  return { head, body: rest };
}

/**
 * `preRenderCSSCode` 的入口：先建全局变量表，再对「伪元素相关规则块」内的声明做变量折叠，最后拼回 `@charset`/`@import` 头。
 */
function replaceVarsInPseudoElementRulesOnly(cssCode: string): string {
  const cssVarMap = extractCssVarMap(cssCode);
  const { head, body } = splitLeadingCharsetAndImports(cssCode);
  return head + walkRuleBlocks(body, cssVarMap);
}

/**
 * 轻量级 CSS 分块扫描：用花括号深度匹配规则体，支持 `@media` 等嵌套；**非**完整 CSS 解析器。
 * - `@` 开头：递归处理内层，以便在嵌套规则中找到伪元素选择器。
 * - 普通规则：仅当 selector 命中 `selectorHasPseudoAfterBefore` 时替换声明体内的 var。
 */
function walkRuleBlocks(css: string, cssVarMap: Record<string, string>): string {
  let out = '';
  let i = 0;
  while (i < css.length) {
    const open = css.indexOf('{', i);
    if (open === -1) {
      out += css.slice(i);
      break;
    }
    const selector = css.slice(i, open);
    // 从第一个 `{` 起做括号配对，处理 `@media { ... }` 内多层 `{` 的情况
    let depth = 1;
    let j = open + 1;
    while (j < css.length && depth > 0) {
      const c = css[j];
      if (c === '{') depth++;
      else if (c === '}') depth--;
      j++;
    }
    // 遍历结束仍 depth>0：输入可能截断或非标准，原样输出剩余片段避免静默丢内容
    if (depth > 0) {
      out += css.slice(i);
      break;
    }
    const body = css.slice(open + 1, j - 1);
    const selTrim = selector.trimStart();
    if (selTrim.startsWith('@')) {
      // @规则内部递归扫描，确保伪元素规则在 @media 内也能被处理
      out += `${selector}{${walkRuleBlocks(body, cssVarMap)}}`;
    } else if (selectorHasPseudoAfterBefore(selector)) {
      // 仅命中伪元素规则时才做变量折叠，降低对普通规则的行为干扰
      out += `${selector}{${replaceVarsInDeclarations(body, cssVarMap)}}`;
    } else {
      // 非目标规则原样回写
      out += `${selector}{${body}}`;
    }
    // 游标推进到当前规则块结束位置，继续解析后续文本
    i = j;
  }
  return out;
}

/**
 * PostCSS 插件：在样式**已展开为最终选择器**之后，把 `.bk-` 批量替换为 `.apm-bk-`。
 *
 * 作用范围：业务侧 scss、以及 bkui-vue 等编译生成的 css/less 中的蓝鲸类名；
 * 与源码里的 `apmBkClassPrefixSourcePlugin` 形成「模板/HTML 侧 + 样式侧」双通道前缀，避免嵌入 APM 时与页面其他蓝鲸组件样式串扰。
 */
function apmBkClassPrefixPostcssPlugin(): PostcssPlugin {
  return {
    /** 插件名：出现在 PostCSS 报错栈中便于识别。 */
    postcssPlugin: 'apm-bk-class-prefix',
    /** `OnceExit`：所有规则已展开完毕后再改 selector，避免与嵌套插件顺序打架。 */
    OnceExit(root) {
      root.walkRules(rule => {
        if (rule.selector) {
          // 仅替换类选择器片段 .bk-，不动 HTML 标签名等
          rule.selector = rule.selector.replace(/\.bk-/g, '.apm-bk-');
        }
      });
    },
  };
}

/**
 * Vite 插件：在 TS/TSX/Vue 源码中把蓝鲸组件类名前缀 `bk-` 改写为 `apm-bk-`（仅类名字面量）。
 *
 * - `enforce: 'pre'`：尽量在其他转换之前执行，减少与 JSX/宏等插件的交互问题。
 * - 正则 `apmBkClassTokenRe`：负向后顾 `(?<![</\w-])` 避免误改标签名（`<bk-button`）、`v-bk-*`、
 *   单词内部的 `bk-`、以及已是 `apm-bk-` 的片段；正向前瞻 `(?=[a-z0-9])` 约束为类名 token 起始。
 * - 跳过 `node_modules`，仅处理 `.ts/.tsx/.js/.jsx/.vue`（忽略 query，如 `?vue&type=script`）。
 */
function apmBkClassPrefixSourcePlugin(): VitePlugin {
  /** 匹配「作为蓝鲸组件类名前缀的 `bk-`」，排除标签名、已是 `apm-bk-`、以及单词内部的 bk-。 */
  const apmBkClassTokenRe = /(?<![</\w-])bk-(?=[a-z0-9])/g;
  return {
    name: 'vite-plugin-apm-bk-class-prefix-source',
    enforce: 'pre',
    transform(code: string, id: string) {
      if (/node_modules/.test(id)) return;
      // 去掉 ?vue、?raw 等查询串，仅按真实文件后缀判断是否参与替换
      const pathOnly = id.split('?')[0];
      if (!/\.(m?[tj]sx?|vue)$/.test(pathOnly)) return;
      // 无 bk- 子串则跳过后续正则，减轻大文件成本
      if (!code.includes('bk-')) return;
      // 只替换明确属于类名 token 的 bk-，避免误伤标签名或指令名
      const next = code.replace(apmBkClassTokenRe, 'apm-bk-');
      // 正则未命中时保持 undefined，避免无意义地触发下游插件
      if (next === code) return;
      // 不生成 sourcemap：纯字符串替换且与行号大致一致，宿主调试以未前缀源码为准
      return { code: next, map: null };
    },
  };
}

/**
 * Vite 插件：把源码中的 `require('*.svg')` 在构建期展开为内联 `data:image/svg+xml;base64,...`。
 *
 * 背景：Rollup/Vite 以 ESM 为主，不会像 webpack 那样解析并打包 `require()`；
 * 若保留 `require`，产物在浏览器或纯 ESM 宿主中会报错或路径失效。内联后不再依赖运行时文件路径。
 * 仅处理当前模块相对路径引用的 svg；`node_modules` 跳过。
 */
function svgRequireInlinePlugin(): VitePlugin {
  return {
    name: 'vite-plugin-svg-require-inline',
    transform(code: string, id: string) {
      if (/node_modules/.test(id)) return;
      const svgRequireRe = /require\(\s*['"]([^'"]+\.svg)['"]\s*\)/g;
      // 带 `g` 的正则在 `test()` 后会推进 lastIndex；先 test 再 replace 前须归零，否则会漏匹配
      if (!svgRequireRe.test(code)) return;
      svgRequireRe.lastIndex = 0;
      const transformed = code.replace(svgRequireRe, (_, svgRelPath: string) => {
        // 相对当前模块解析 svg 物理路径，与 webpack file-loader 行为类似
        const svgAbsPath = resolve(dirname(id), svgRelPath);
        // 读入原始 svg 文本并直接内联，运行时不再依赖静态资源路径
        const svgContent = readFileSync(svgAbsPath, 'utf-8');
        const base64 = Buffer.from(svgContent).toString('base64');
        // 产出合法 JS 字符串字面量，供 img src 或 CSS url 使用
        return `"data:image/svg+xml;base64,${base64}"`;
      });
      return { code: transformed, map: null };
    },
  };
}

/**
 * Vite 插件：修补 TDesign Popup 在 Vue 2 宿主 + Vue 3 子应用场景下的弹窗关闭异常。
 *
 * 核心问题 —— 点击弹窗内部元素导致弹窗自动关闭：
 *   ColumnSettings 的 Popup（trigger="click"）被 Teleport 到 document.body。
 *   当用户在弹窗内操作（如切换 checkbox）时，触发了 Vue 3 组件树 re-render。
 *   re-render 期间 table header 中的 trigger 元素（设置图标）被临时从 DOM 卸载重建，
 *   导致 Popup 的 `updatePopper` 中 `isHidden` 检测为 true，调用 `setVisible(false)` 关闭弹窗。
 *
 *   → 对 trigger="click" 的 Popup 禁用 `isHidden` 自动关闭逻辑。
 *     该逻辑是为 hover 触发的弹窗设计的（trigger 消失 → 弹窗关闭）；
 *     click 触发的弹窗仅应通过用户点击外部或再次点击 trigger 来关闭。
 *
 * 辅助修补：
 *   1. 注入 `_showTs` 时间戳，在打开后 200ms 内忽略 `onDocumentMouseDown`，
 *      防止打开同一帧内的误触发。
 *   2. 在 `onDocumentMouseDown` 增加 `closest('[data-td-popup]')` DOM 回溯守卫，
 *      作为 `popperEl.value.contains(ev.target)` 的备用。
 *   3. 在 overlay div 上拦截所有鼠标/指针事件的冒泡 (`stopPropagation`)，
 *      阻止 bkui-vue `v-clickoutside` 指令（冒泡阶段注册在 document 上）的误判。
 *
 * 同时支持两种来源：
 * - `tdesign-vue-next/es/popup/popup.mjs`（trace 直接依赖，空格缩进）
 * - `@blueking/tdesign-ui/vue3/index.es.min.js`（bundled 产物，tab 缩进，部分逻辑内联）
 *
 * 所有替换均使用正则 + 捕获缩进的方式，自适应空格与 tab 两种格式。
 *
 * **维护提示**：TDesign 升级若改动上述字符串，插件会 `console.warn` 且不打补丁；
 * 需对照新版本源码调整 `replace` 的锚点正则，或评估是否可移除本插件。
 */
function patchTDesignPopupTimingPlugin(): VitePlugin {
  /** 打开弹窗后短时间内忽略 document mousedown，避免与打开手势同一事件环冲突。 */
  const GUARD_MS = 200;
  return {
    name: 'vite-plugin-patch-tdesign-popup-timing',
    enforce: 'pre',
    transform(code: string, id: string) {
      const isTDesignPopupModule = id.includes('tdesign-vue-next') && id.endsWith('popup/popup.mjs');
      const isBundledTDesignUI =
        id.includes('@blueking/tdesign-ui') && id.endsWith('.js') && code.includes('function onDocumentMouseDown');
      if (!isTDesignPopupModule && !isBundledTDesignUI) return;

      let patched = code;

      // 1) 在 showTimeout / hideTimeout 后面插入 _showTs 变量
      patched = patched.replace(
        /var showTimeout;\s*\n(\s*)var hideTimeout;/,
        (_, indent) => `var showTimeout;\n${indent}var hideTimeout;\n${indent}var _showTs = 0;`
      );

      // 2) show() 函数入口处记录时间戳
      patched = patched.replace(
        /function show\(ev\) \{\s*\n(\s*)clearAllTimeout\(\);/,
        (_, indent) => `function show(ev) {\n${indent}_showTs = Date.now();\n${indent}clearAllTimeout();`
      );

      // 3) onDocumentMouseDown 增加：时间守卫 + DOM 属性回溯守卫
      patched = patched.replace(
        /function onDocumentMouseDown\(ev\) \{\s*\n(\s*)var _popperEl\$value, _triggerEl\$value;/,
        (_, indent) =>
          [
            'function onDocumentMouseDown(ev) {',
            `${indent}if (Date.now() - _showTs < ${GUARD_MS}) return;`,
            `${indent}if (ev.target.closest && ev.target.closest('[data-td-popup="' + id + '"]')) return;`,
            `${indent}var _popperEl$value, _triggerEl$value;`,
          ].join('\n')
      );

      // 4) updatePopper 的 isHidden 关闭分支：对 click 触发的 Popup 完全跳过。
      //    trigger 元素在父组件 re-render 期间被临时从 DOM 卸载是正常行为，
      //    不应导致 click 触发的弹窗关闭。
      //    非 bundled 版本：} else { setVisible(false, { ... })
      patched = patched.replace(
        /(popper\.update\(\);\s*\n(\s*)\})\s*else\s*\{\s*\n(\s*)setVisible\(false,\s*\{/,
        (_, prefix, _closeIndent, setVisibleIndent) =>
          `${prefix} else if (props2.trigger !== "click") {\n${setVisibleIndent}setVisible(false, {`
      );
      //    bundled 版本：} else setVisible(false, { trigger: ... });
      patched = patched.replace(
        /(popper\.update\(\);\s*\n(\s*)\})\s*else\s+setVisible\(false,/,
        (_, prefix) => `${prefix} else if (props2.trigger !== "click") setVisible(false,`
      );

      // 5) 在 overlay 上拦截所有鼠标/指针事件的冒泡，
      //    阻止 bkui-vue v-clickoutside 等全局冒泡阶段 handler 的误判。
      //    TDesign 自身的 onDocumentMouseDown 使用 capture 阶段，不受影响。
      patched = patched.replace(
        /"onClick": onOverlayClick,\s*\n(\s*)"onMouseenter": onMouseenter,\s*\n\s*"onMouseleave": onMouseLeave/,
        (_, indent) =>
          [
            '"onClick": function(e) { e.stopPropagation(); onOverlayClick(e); },',
            `${indent}"onMousedown": function(e) { e.stopPropagation(); },`,
            `${indent}"onMouseup": function(e) { e.stopPropagation(); },`,
            `${indent}"onPointerdown": function(e) { e.stopPropagation(); },`,
            `${indent}"onPointerup": function(e) { e.stopPropagation(); },`,
            `${indent}"onMouseenter": onMouseenter,`,
            `${indent}"onMouseleave": onMouseLeave`,
          ].join('\n')
      );

      if (patched === code) {
        console.warn('[patch-tdesign-popup-timing] No replacements matched — TDesign Popup source may have changed.');
        return;
      }
      return { code: patched, map: null };
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
