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

import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import type VueI18n from 'vue-i18n';

export type ProfileDataUnit = 'bytes' | 'count' | 'nanoseconds' | 'seconds'; // 字节 ｜ 计数 ｜ 纳秒 ｜ 秒

interface ProfileDataValue {
  text?: VueI18n.TranslateResult;
  value: number | string;
}

/**
 * @desc 解析不同数据类型单位处理值
 * @param { Number } data 原始数据
 * @param { ProfileDataUnit } unit 单位
 * @param { Boolean } needDataText 是否需要返回数据类型文案
 * @param { String } percent 带占比展示
 * @returns { ProfileDataValue } 返回值
 */
export const parseProfileDataTypeValue = (
  data: number,
  unit: ProfileDataUnit,
  needDataText?: boolean,
  percent?: string
): ProfileDataValue => {
  switch (unit) {
    case 'nanoseconds':
    case 'seconds': {
      const timeFormat = getValueFormat(unit === 'seconds' ? 's' : 'ns');
      const { text, suffix } = timeFormat(data);
      return {
        value: percent ? `(${percent}, ${text}${suffix})` : text + suffix,
        ...(needDataText ? { text: window.i18n.t('耗时') } : {}),
      };
    }
    case 'bytes': {
      const bytesFormat = getValueFormat('bytes');
      const { text, suffix } = bytesFormat(data);
      return {
        value: percent ? `(${percent}, ${text}${suffix})` : text + suffix,
        ...(needDataText ? { text: window.i18n.t('大小') } : {}),
      };
    }
    case 'count': {
      return {
        value: percent ? `(${percent}, ${data})` : data,
        ...(needDataText ? { text: window.i18n.t('数量') } : {}),
      };
    }
    default:
      return { value: '' };
  }
};
