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
 * 实体跳转链接占位符方案
 *
 * 背景：
 * - toast-ui Viewer 会把 Markdown 中的原始 HTML（如 <a>）转义成纯文本
 * - Markdown 的 [text](url) 在 text 含 `[`/`]` 时会语法破坏
 *
 * 做法：
 * 1. Markdown 阶段只插入 ASCII 安全占位符 %%BKENTITY:...%%
 * 2. toast-ui 渲染前（beforePreviewRender）再把占位符替换成真实 <a>
 *
 * 注意：
 * - encodeURIComponent 不会编码 *！若 display_name 为 **10998**，占位符中会残留 **，
 *   被 Markdown 解析成 <strong>，占位符被拆断，水合失败。
 * - 因此必须对 * 等残留字符做二次编码（见 encodePlaceholderPayload）
 */

/** 匹配实体链接占位符；payload 仅含 %XX / 字母数字等，不会出现连续 %% */
export const ENTITY_LINK_PLACEHOLDER_RE = /%%BKENTITY:([A-Za-z0-9\-._~%]+)%%/g;

/**
 * 比 encodeURIComponent 更严格：补编码 * 等 Markdown 敏感字符
 * 参见 MDN fixedEncodeURIComponent
 */
const encodePlaceholderPayload = (text: string): string => {
  return encodeURIComponent(text).replace(/[!'()*]/g, char => {
    return `%${char.charCodeAt(0).toString(16).toUpperCase()}`;
  });
};

const isValidUrl = (url: string): boolean => {
  return !!url && /^https?:\/\/.+/.test(url.trim());
};

const escapeHtmlAttr = (text: string): string => {
  return text
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
};

const escapeHtmlText = (text: string): string => {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
};

/**
 * 将 display_name 中的 **bold** 转为 <strong>，其余文本做 HTML 转义
 */
const formatEntityLinkContent = (displayName: string): string => {
  const boldPattern = /\*\*(.+?)\*\*/g;
  let result = '';
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = boldPattern.exec(displayName)) !== null) {
    if (match.index > lastIndex) {
      result += escapeHtmlText(displayName.slice(lastIndex, match.index));
    }
    result += `<strong>${escapeHtmlText(match[1])}</strong>`;
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < displayName.length) {
    result += escapeHtmlText(displayName.slice(lastIndex));
  }

  return result;
};

export const buildEntityLinkHtml = (displayName: string, url: string): string => {
  return `<a href="${escapeHtmlAttr(url)}" target="_blank" rel="noopener noreferrer">${formatEntityLinkContent(
    displayName
  )}</a>`;
};

/** 生成可安全嵌入 Markdown 的实体链接占位符（payload 中不含 * [ ] 等 Markdown 语法字符） */
export const encodeEntityLinkPlaceholder = (displayName: string, url: string): string => {
  const payload = encodePlaceholderPayload(JSON.stringify({ displayName, url }));
  return `%%BKENTITY:${payload}%%`;
};

/**
 * 将渲染后的 HTML 中的实体占位符替换为真实 <a> 标签
 */
export const hydrateEntityLinkPlaceholders = (html: string): string => {
  if (!html || !html.includes('%%BKENTITY:')) return html;

  return html.replace(ENTITY_LINK_PLACEHOLDER_RE, (raw, payload: string) => {
    try {
      const { displayName, url } = JSON.parse(decodeURIComponent(payload)) as {
        displayName?: string;
        url?: string;
      };
      if (!displayName) return raw;
      if (!isValidUrl(url || '')) return formatEntityLinkContent(displayName);
      return buildEntityLinkHtml(displayName, url as string);
    } catch {
      return raw;
    }
  });
};
