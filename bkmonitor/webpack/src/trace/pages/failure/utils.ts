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
import { type ComputedRef, inject, provide } from 'vue';

export const INCIDENT_ID_KEY = 'INCIDENT_ID_KEY';
export const useIncidentProvider = (incidentId: ComputedRef<string>) => {
  provide(INCIDENT_ID_KEY, incidentId);
};
export const useIncidentInject = () => inject<ComputedRef<string>>(INCIDENT_ID_KEY);

export const replaceSpecialCondition = (qs: string) => {
  // 由于验证 queryString 不允许使用单引号，为提升体验，这里单双引号的空串都会进行替换。
  const regExp = new RegExp(`${window.i18n.t('通知人')}\\s*:\\s*(""|'')`, 'gi');
  return qs.replace(regExp, `NOT ${window.i18n.t('通知人')} : *`);
};

/**
 * @description 检查文本是否溢出（超过n行）
 * @param el 元素
 * @param n 行数，默认3行
 * @returns 是否溢出
 */
export const checkOverflow = (el: HTMLElement, n = 3) => {
  if (!el) return false;

  // 使用getComputedStyle获取精确样式
  const styles = getComputedStyle(el);
  const lineHeight = parseInt(styles.lineHeight) || 22; // 默认22px

  // 计算n行高度
  const maxHeight = lineHeight * n;

  return el.scrollHeight > maxHeight;
};
