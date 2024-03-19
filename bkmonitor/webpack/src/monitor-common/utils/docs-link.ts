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

import { DocLinkType } from '../typings';

import { rstrip } from './utils';

function linkJump(type: DocLinkType, path: string) {
  const url = type === DocLinkType.Splice ? `${rstrip(window.bk_docs_site_url, '/')}/markdown/${path}` : path;
  window.open(url, '_blank');
}

/**
 * @desc 文档跳转统一方案处理
 * @param { string } id
 * @param { Record<string, string> } localMap
 * @param { Record<string, IDocLinkData> } remoteMap
 */
export function jumpToDocsLink(id, localMap, remoteMap) {
  // 先匹配接口返回文档链接
  if (remoteMap[id]) {
    const { type, value } = remoteMap[id];
    linkJump(type, value);
  } else {
    const path = localMap[id] || id;
    if (path) {
      linkJump(DocLinkType.Splice, path);
    }
  }
}
