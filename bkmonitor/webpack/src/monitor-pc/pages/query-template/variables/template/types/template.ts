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
/** biome-ignore-all lint/complexity/noBannedTypes: <explanation> */

import type { ScopedVars, TimeRange } from './scoped-var';
export enum VariableFormatID {
  CSV = 'csv',
  Date = 'date',
  Distributed = 'distributed',
  DoubleQuote = 'doublequote',
  Glob = 'glob',
  HTML = 'html',
  JSON = 'json',
  Lucene = 'lucene',
  PercentEncode = 'percentencode',
  Pipe = 'pipe',
  QueryParam = 'queryparam',
  Raw = 'raw',
  Regex = 'regex',
  SingleQuote = 'singlequote',
  SQLString = 'sqlstring',
  Text = 'text',
  UriEncode = 'uriencode',
}
export interface BaseTemplateSrv {
  /**
   * 检查目标字符串是否包含模板变量
   */
  containsTemplate(target?: string): boolean;

  /**
   * 替换目标字符串中的值
   * @param target 目标字符串
   * @param scopedVars 变量map
   * @param format 格式
   * @param interpolations 插值
   */
  replace(
    target?: string,
    scopedVars?: ScopedVars,
    format?: Function | string,
    interpolations?: VariableInterpolation[]
  ): string;

  /**
   * 更新时间范围
   * @param timeRange 时间范围
   */
  updateTimeRange(timeRange: TimeRange): void;
}

export interface VariableInterpolation {
  /** In the expression ${varName.fields[0].name:regex} the fieldPath is fields[0].name */
  fieldPath?: string;
  /** In the expression ${varName:regex} the regex part is the format */
  format?: string;
  // When value === match this will be true, meaning the variable was not found
  found?: boolean;
  /** The full matched expression including, example: ${varName.field:regex} */
  match: string;
  /** The formatted value of the variable expression. Will equal match when variable not found or scopedVar was undefined or null **/
  value: string;
  /** In the expression ${varName.field:regex} variableName is varName */
  variableName: string;
}
