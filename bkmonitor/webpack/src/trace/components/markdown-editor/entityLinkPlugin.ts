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

import { hydrateEntityLinkPlaceholders } from './entity-link-placeholder';

import type { PluginContext } from '@toast-ui/editor/types/editor';

/**
 * Toast-ui 编辑器插件：
 * 1. 在 beforePreviewRender 阶段，将实体链接占位符 %%BKENTITY:...%% 水合为真实 <a>
 * 2. 渲染完成后，为所有 <a> 补充 target="_blank" / rel
 *
 * 为什么不用 Markdown [text](url) 或直接塞 HTML：
 *   - display_name 含 `[`/`]` 会破坏 Markdown 链接语法
 *   - toast-ui Viewer 会把 Markdown 里的原始 HTML 转义成纯文本
 *
 * 时序说明：
 *   - beforePreviewRender：在 HTML 写入 DOM 前替换占位符（无闪烁）
 *   - fixUrlPlugin 在 setTimeout(100ms) 后修改 innerHTML（修复 URL）
 *   - 本插件在 setTimeout(150ms) 后设置 target（须晚于 fixUrlPlugin）
 */
export default function entityLinkPlugin(context: PluginContext) {
  // emitReduce：返回值会作为下一轮 HTML 继续传递
  context.eventEmitter.listen('beforePreviewRender', (html: string) => {
    return hydrateEntityLinkPlaceholders(html);
  });

  context.eventEmitter.listen('afterPreviewRender', () => {
    setTimeout(() => {
      const previewArea = context.instance.options.el;
      if (!previewArea) return;

      // 兜底：若 fixUrlPlugin 的 innerHTML 重写意外带回占位符原文，再水合一次
      if (previewArea.innerHTML.includes('%%BKENTITY:')) {
        previewArea.innerHTML = hydrateEntityLinkPlaceholders(previewArea.innerHTML);
      }

      const links = previewArea.querySelectorAll('a');
      for (const link of links) {
        const anchor = link as HTMLAnchorElement;
        anchor.setAttribute('target', '_blank');
        // 安全性：添加 rel="noopener noreferrer" 防止 window.opener 泄漏
        anchor.setAttribute('rel', 'noopener noreferrer');
      }
    }, 150);
  });

  return {
    name: 'entityLinkPlugin',
  };
}
