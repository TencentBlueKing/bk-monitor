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

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import postcss from 'postcss';

import type { Plugin } from 'vite';

/** 宿主容器需要挂上的类名，与产出的选择器前缀一致 */
export const VUE2_CSS_SCOPE = '.monitor-vue2-scope';

const ROOT_SELECTOR = /^(html|body|:root)$/;
const ROOT_DESCENDANT = /^(html|body)\b\s*/;

const scopeSelector = (selector: string) => {
  const value = selector.trim();
  if (!value || value.startsWith(VUE2_CSS_SCOPE)) return selector;
  // 根级选择器落到容器自身，:root 上的 CSS 变量因此仍能被容器内元素继承
  if (ROOT_SELECTOR.test(value)) return VUE2_CSS_SCOPE;
  if (ROOT_DESCENDANT.test(value)) return `${VUE2_CSS_SCOPE} ${value.replace(ROOT_DESCENDANT, '')}`;
  return `${VUE2_CSS_SCOPE} ${value}`;
};

const isInsideKeyframes = (rule: postcss.Rule) => {
  for (let node: postcss.Container | postcss.Document | undefined = rule.parent; node; node = node.parent) {
    if (node.type === 'atrule' && /keyframes$/.test((node as postcss.AtRule).name)) return true;
  }
  return false;
};

interface IOptions {
  outDir: string;
  /** 构建产出的原始样式文件名 */
  source?: string;
  /** 加了作用域前缀的副本文件名 */
  output?: string;
}

/**
 * 额外产出一份带作用域前缀的样式副本。
 *
 * 包内自带整套 bkui-vue2 样式，其中数百个 .bk-* 类名与 bkui-vue3 同名，
 * 宿主若是 vue3 项目，全局引入原始样式会双向污染。改用这份副本、并给组件的挂载容器
 * （以及 bk-magic-vue 挂在 body 下的全局弹层容器）加上 VUE2_CSS_SCOPE 类名，
 * 规则就只在容器内生效，且特异性比裸类名高一级，容器内由 vue2 的样式胜出。
 */
export function scopeVue2Css(options: IOptions): Plugin {
  const { outDir, source = 'index.css', output = 'index.scoped.css' } = options;
  return {
    name: 'monitor-scope-vue2-css',
    // lib 模式下多入口会多次触发 writeBundle，这里只需在全部产物落盘后跑一次
    closeBundle() {
      const sourcePath = resolve(outDir, source);
      if (!existsSync(sourcePath)) return;

      const root = postcss.parse(readFileSync(sourcePath, 'utf8'));
      let scopedCount = 0;
      root.walkRules(rule => {
        // @keyframes 内是 from/to/百分比，加前缀会让动画失效
        if (isInsideKeyframes(rule)) return;
        rule.selectors = rule.selectors.map(scopeSelector);
        scopedCount += 1;
      });

      const result = root.toString();
      writeFileSync(resolve(outDir, output), result);
      console.log(`${output}  ${(result.length / 1024).toFixed(2)} kB │ ${scopedCount} 条规则加上 ${VUE2_CSS_SCOPE}`);
    },
  };
}
