/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import 'xss/dist/xss';
// <a style="color:red">dsafsd</a> <img src onerror="alert(1)" />
export const xssFilter = (str: string) => {
  if (!str) return str;
  try {
    return window.filterXSS(str);
  } catch (err) {
    console.error(err);
    return (
      str?.replace?.(/[&<>"]/gi, match => {
        switch (match) {
          case '&':
            return '&amp;';
          case '<':
            return '&lt;';
          case '>':
            return '&gt;';
          case '"':
            return '&quot;';
        }
      }) || str
    );
  }
};

// 允许通过的 data URI 协议（仅图片，限制 base64 编码）
const SAFE_DATA_IMAGE_REGEXP = /^data:image\/(png|jpe?g|gif|svg\+xml|webp);base64,[a-z0-9+/=]+$/i;
const COMMON_ATTRS = ['style', 'class', 'id'];
const TABLE_ATTRS = ['width', 'height', 'border', 'cellspacing', 'cellpadding', 'bgcolor', 'align', 'valign'];
const CELL_EXTRAS = ['rowspan', 'colspan'];

let mailFilterInstance: any = null;

const getMailFilter = () => {
  if (mailFilterInstance) return mailFilterInstance;
  // xss 浏览器 build (xss/dist/xss) 把 FilterXSS 类、getDefaultWhiteList 等 API 都挂在
  // window.filterXSS 这个函数对象上。
  const xssLib: any = window.filterXSS;
  const FilterXSSCtor: any = xssLib?.FilterXSS;
  const getDefaultWhiteList: any = xssLib?.getDefaultWhiteList;
  if (!FilterXSSCtor || !getDefaultWhiteList) return null;

  const whiteList = getDefaultWhiteList();
  const extend = (tag: string, attrs: string[]) => {
    whiteList[tag] = Array.from(new Set([...(whiteList[tag] || []), ...attrs]));
  };
  // 邮件布局常用块级 / 行内标签
  ['div', 'span', 'p', 'br', 'hr', 'a', 'img', 'small', 'strong', 'em', 'b', 'i', 'u'].forEach(tag =>
    extend(tag, COMMON_ATTRS),
  );
  // 表格相关
  extend('table', [...COMMON_ATTRS, ...TABLE_ATTRS]);
  ['tbody', 'thead', 'tfoot', 'tr', 'td', 'th', 'col', 'colgroup'].forEach(tag =>
    extend(tag, [...COMMON_ATTRS, ...TABLE_ATTRS, ...CELL_EXTRAS]),
  );
  // 链接与图片
  extend('a', ['target', 'rel', 'href', 'title']);
  extend('img', ['src', 'alt', 'title', 'width', 'height']);

  return (mailFilterInstance = new FilterXSSCtor({
    whiteList,
    stripIgnoreTag: false,
    stripIgnoreTagBody: ['script', 'style'],
    onTagAttr(tag: string, name: string, value: string) {
      // 允许 <img src="data:image/...;base64,..."> 这一图片内嵌资源
      if (tag === 'img' && name === 'src' && SAFE_DATA_IMAGE_REGEXP.test(value)) {
        return `${name}="${value}"`;
      }
      // 禁止链接 javascript: 等危险协议
      if (name === 'href' && /^\s*(javascript|vbscript|data):/i.test(value)) {
        return `${name}=""`;
      }
      return undefined;
    },
  }));
};

// 邮件通知模板预览专用：保留表格布局 / inline style / base64 内嵌图，过滤脚本与危险事件
export const sanitizeMailHtml = (html: string): string => {
  if (!html) return html;
  const filter = getMailFilter();
  try {
    if (filter) return filter.process(html);
    return window.filterXSS(html);
  } catch (err) {
    console.error(err);
    return xssFilter(html);
  }
};
