/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export const stripMark = (value: string) => value.replace(/<mark>/g, '').replace(/<\/mark>/g, '');

export const flattenLogParams = (row: Record<string, any>) => {
  const params: Record<string, string> = {};

  const walk = (obj: any, prefix = '') => {
    if (obj === null || obj === undefined) {
      if (prefix) params[prefix] = '';
      return;
    }

    Object.keys(obj).forEach(key => {
      const prefixKey = prefix ? `${prefix}.${key}` : key;
      const value = obj[key];
      if (value && typeof value === 'object' && !value._isBigNumber) {
        walk(value, prefixKey);
        return;
      }
      params[prefixKey] = stripMark(value?._isBigNumber ? value.toString() : String(value ?? ''));
    });
  };

  walk(row);
  return params;
};

export const createRealtimeCursor = (row: Record<string, any> | null | undefined) => flattenLogParams(row || {});

/** 本批最后一条作为下一次 tail_f 游标；空结果不推进 */
export const advanceRealtimeCursor = (list: Record<string, any>[] | null | undefined) => {
  if (!list?.length) return null;
  return flattenLogParams(list[list.length - 1]);
};

/** 轮询控制字段放在游标之后，避免日志字段覆盖 order / size / zero */
export const buildRealtimeTailRequest = (
  cursorParams: Record<string, string>,
  zero: boolean,
  dtEventTimeStamp: unknown = cursorParams.dtEventTimeStamp,
) => ({
  ...cursorParams,
  order: '-',
  size: 50,
  zero,
  dtEventTimeStamp,
});
