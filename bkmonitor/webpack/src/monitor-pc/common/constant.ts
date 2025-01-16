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

// 是否中文
export const isZh = () => ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale);

// 空间类型对应map
export const SPACE_TYPE_MAP = {
  bkcc: {
    name: window.i18n.tc('业务'),
    dark: {
      color: '#478EFC',
      backgroundColor: '#2B354D',
    },
    light: {
      color: '#3A84FF',
      backgroundColor: '#EDF4FF',
    },
  },
  default: {
    name: window.i18n.tc('监控空间'),
    dark: {
      color: '#B3B3B3',
      backgroundColor: '#333333',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#F0F1F5',
    },
  },
  bkci: {
    name: window.i18n.tc('研发项目'),
    dark: {
      color: '#F85959',
      backgroundColor: '#4C3232',
    },
    light: {
      color: '#E71818',
      backgroundColor: '#FFEBEB',
    },
  },
  bcs: {
    name: window.i18n.tc('容器项目'),
    dark: {
      color: '#FC943B',
      backgroundColor: '#453921',
    },
    light: {
      color: '#E38B02',
      backgroundColor: '#FDEED8',
    },
  },
  paas: {
    name: window.i18n.tc('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B',
    },
    light: {
      color: '#14A568',
      backgroundColor: '#E4FAF0',
    },
  },
  bksaas: {
    name: window.i18n.tc('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B',
    },
    light: {
      color: '#14A568',
      backgroundColor: '#E4FAF0',
    },
  },
};

export const SPACE_FIRST_CODE_COLOR_MAP = {
  bkcc: {
    dark: {
      backgroundColor: '#3A84FF',
    },
    light: {
      backgroundColor: '#3A84FF',
    },
  },
  default: {
    dark: {
      backgroundColor: '#63656E',
    },
    light: {
      backgroundColor: '#63656E',
    },
  },
  bkci: {
    dark: {
      backgroundColor: '#FF5656',
    },
    light: {
      backgroundColor: '#FF5656',
    },
  },
  bcs: {
    dark: {
      backgroundColor: '#FF9C01',
    },
    light: {
      backgroundColor: '#FF9C01',
    },
  },
  paas: {
    dark: {
      backgroundColor: '#2DCB56',
    },
    light: {
      backgroundColor: '#2DCB56',
    },
  },
  bksaas: {
    dark: {
      backgroundColor: '#2DCB56',
    },
    light: {
      backgroundColor: '#2DCB56',
    },
  },
};

export const DEFAULT_TIME_RANGE_LIST = [
  {
    name: window.i18n.t('近{n}分钟', { n: 5 }),
    value: 5 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}分钟', { n: 15 }),
    value: 15 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}分钟', { n: 30 }),
    value: 30 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}小时', { n: 1 }),
    value: 1 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}小时', { n: 3 }),
    value: 3 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}小时', { n: 6 }),
    value: 6 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}小时', { n: 12 }),
    value: 12 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近{n}小时', { n: 24 }),
    value: 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 2 }),
    value: 2 * 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 7 }),
    value: 7 * 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('近 {n} 天', { n: 30 }),
    value: 30 * 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('今天'),
    value: 'today',
  },
  {
    name: window.i18n.t('昨天'),
    value: 'yesterday',
  },
  {
    name: window.i18n.t('前天'),
    value: 'beforeYesterday',
  },
  {
    name: window.i18n.t('本周'),
    value: 'thisWeek',
  },
];
export const DEFAULT_TIMESHIFT_LIST = [
  {
    id: '1h',
    name: window.i18n.t('1 小时前'),
  },
  {
    id: '1d',
    name: window.i18n.t('昨天'),
  },
  {
    id: '1w',
    name: window.i18n.t('上周'),
  },
  {
    id: '1M',
    name: window.i18n.t('一月前'),
  },
];
export const DEFAULT_REFLESH_LIST = [
  // 刷新间隔列表
  {
    name: 'off',
    id: -1,
  },
  {
    name: '1m',
    id: 60 * 1000,
  },
  {
    name: '5m',
    id: 5 * 60 * 1000,
  },
  {
    name: '15m',
    id: 15 * 60 * 1000,
  },
  {
    name: '30m',
    id: 30 * 60 * 1000,
  },
  {
    name: '1h',
    id: 60 * 60 * 1000,
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000,
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000,
  },
];
/** 小写英文字符集合 用于unifyquery experssion alias等 */
export const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
