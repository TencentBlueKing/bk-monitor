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

import type { PluginContext } from '@toast-ui/editor/types/editor';

/**
 * Toast-ui 编辑器插件：为所有 <a> 标签添加 target="_blank" 和 rel="noopener noreferrer"
 *
 * 设计原理：
 *   - Markdown 文本中 [display_name](jump_target) 经 toast-ui 渲染后生成 <a href="url">text</a>
 *   - 默认 <a> 标签没有 target 属性，点击会在当前页面跳转
 *   - 本插件监听 afterPreviewRender 事件，在渲染完成后为所有 <a> 添加 target="_blank"
 *
 * 时序说明：
 *   - fixUrlPlugin 在 setTimeout(100ms) 后修改 innerHTML（修复 URL）
 *   - 本插件在 setTimeout(150ms) 后操作 DOM 元素（添加 target）
 *   - innerHTML 替换会重建 DOM 树，因此本插件必须延迟至 fixUrlPlugin 完成后执行
 *   - 否则 fixUrlPlugin 的 innerHTML 赋值会覆盖本插件设置的 target 属性
 */
export default function entityLinkPlugin(context: PluginContext) {
  context.eventEmitter.listen('afterPreviewRender', () => {
    setTimeout(() => {
      const previewArea = context.instance.options.el;
      if (previewArea) {
        const links = previewArea.querySelectorAll('a');
        for (const link of links) {
          const anchor = link as HTMLAnchorElement;
          anchor.setAttribute('target', '_blank');
          // 安全性：添加 rel="noopener noreferrer" 防止 window.opener 泄漏
          anchor.setAttribute('rel', 'noopener noreferrer');
        }
      }
    }, 150);
  });

  return {
    name: 'entityLinkPlugin',
  };
}
