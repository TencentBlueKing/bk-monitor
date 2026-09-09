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

export const DiagnosticTypeEnum = {
  DIMENSION: 'dimension',
  LINK: 'link',
  LOG: 'log',
  EVENT: 'event',
} as const;

export const DiagnosticTypeMap = {
  [DiagnosticTypeEnum.DIMENSION]: window.i18n.t('告警异常维度分析'),
  [DiagnosticTypeEnum.LINK]: window.i18n.t('Trace 分析'),
  [DiagnosticTypeEnum.LOG]: window.i18n.t('日志分析'),
  [DiagnosticTypeEnum.EVENT]: window.i18n.t('事件分析'),
};

export const DiagnosticTypeIconMap = {
  [DiagnosticTypeEnum.DIMENSION]: 'icon-dimension-line',
  [DiagnosticTypeEnum.LINK]: 'icon-Tracing',
  [DiagnosticTypeEnum.LOG]: 'icon-a-logrizhi',
  [DiagnosticTypeEnum.EVENT]: 'icon-shijianjiansuo',
};
