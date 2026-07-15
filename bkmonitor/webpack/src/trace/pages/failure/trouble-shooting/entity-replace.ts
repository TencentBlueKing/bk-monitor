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

import type { IExtractedInfo } from '../types';

/**
 * 验证是否为有效 URL
 * 规则：非空字符串，且以 http:// 或 https:// 开头
 */
const isValidUrl = (url: string): boolean => {
  return !!url && /^https?:\/\/.+/.test(url.trim());
};

/**
 * 仅转义会破坏 markdown 链接语法的字符：[ 和 ]
 * display_name 中的其他 markdown 格式（如 **bold**）不转义，保留渲染效果
 */
const escapeLinkText = (text: string): string => {
  return text.replace(/([[\]])/g, '\\$1');
};

/**
 * 替换文本中的 ${...} 实体占位符
 *
 * 匹配模式：\$\{...} 格式（如 ${K8sPod:bkm-user-589949c775-pqjmb}）
 * 替换规则：
 *   - 如果实体存在且有有效 jump_target → 替换为 [display_name](jump_target)（Markdown 链接）
 *   - 如果实体存在但无有效 jump_target → 替换为纯文本 display_name（保留 markdown 格式如 **bold**）
 *   - 如果实体不存在或 display_name 为空 → 保留原始占位符文本不变
 *   - 如果 extractedInfo 为 undefined → 保留原文（兼容旧 API 不返回此字段）
 *
 * @param text - 原始文本（可能包含 ${...} 占位符）
 * @param extractedInfo - 该 sub_panel 对应的 extracted_info（可为 undefined）
 * @returns 替换后的文本
 */
export const replaceEntityInText = (text: string, extractedInfo?: IExtractedInfo): string => {
  // 边界情况：无文本或无 extracted_info，直接返回原文本
  if (!text || !extractedInfo?.entities) return text;

  // 正则匹配所有 ${...} 格式的占位符
  const entityPattern = /\$\{[^}]+\}/g;

  return text.replace(entityPattern, match => {
    const entity = extractedInfo.entities[match];

    // 边界情况：占位符在 entities 中不存在或 display_name 为空 → 保留原文
    if (!entity?.display_name) return match;

    // 判断是否有有效跳转 URL
    if (isValidUrl(entity.jump_target)) {
      // 有有效 URL：生成 Markdown 链接 [display_name](jump_target)
      // 仅转义链接文本中的 [ ]，防止破坏 markdown 链接语法
      return `[${escapeLinkText(entity.display_name)}](${entity.jump_target})`;
    }

    // 无有效 URL：替换为纯文本 display_name
    // 保留 display_name 中的 markdown 格式（如 **bold**），让 MarkdownViewer 正确渲染
    return entity.display_name;
  });
};
