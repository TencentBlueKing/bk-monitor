/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type { Span } from '../typings';

type IToggleStatus = 'collpase' | 'expand';

/** 基于 traceTree 进行折叠分组
 * 折叠条件：
 * 1. 没有分组信息 group_info
 * 2. 有分组信息 group_info 当前节点为折叠的聚合节点 group_info.id === span_id
 */
export const handleTraceTreeGroup = (spans: Span[]) => {
  const list = [];
  spans.forEach(span => {
    if (!span.group_info || span.group_info?.id === span.span_id || span.is_expand) {
      list.push(span);
    }
  });

  return list;
};

/** 切换 traceTree 分组的折叠状态 */
export const handleToggleCollapse = (spans: Span[], groupID: string, status: IToggleStatus) => {
  let list = [];
  // 点击切换折叠状态时 只需要更改 is_expand 的值
  list = spans.map(span => ({
    ...span,
    is_expand: span.group_info?.id === groupID ? status === 'expand' : span.is_expand,
  }));

  return list;
};
