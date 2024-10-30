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

import type { IFilterCondition } from '../plugins/apm-service-caller-callee/type';

export function replaceRegexWhere(filter: IFilterCondition[]): IFilterCondition[] {
  /** 前端处理数据：
   * 前匹配：调用后台、跳转数据检索时补成 example.*
   * 后匹配：调用后台、跳转数据检索时补成 .*example
   * */
  if (!filter?.length) return [];
  return filter.map(({ method, value, condition, key }) => {
    if (method === 'before_req' || method === 'after_req') {
      const list = value.map(value => {
        if (method === 'before_req' && !value.endsWith('.*')) {
          return `${value}.*`;
        }
        if (method === 'after_req' && !value.startsWith('.*')) {
          return `.*${value}`;
        }
        return value;
      });
      return {
        value: list,
        method: 'reg',
        condition,
        key,
      };
    }
    return { method, value, condition, key };
  });
}
