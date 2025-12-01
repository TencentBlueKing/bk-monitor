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

import i18n from '@/language/i18n';

export const fieldTypeMap = {
  any: {
    name: i18n.t('不限'),
    icon: 'bk-icon icon-check-line',
    color: '#DCDEE5',
  },
  number: {
    name: i18n.t('数字'),
    icon: 'bklog-icon bklog-number-2',
    color: '#DDEBE6',
    textColor: '#60A087',
  },
  integer: {
    name: i18n.t('数字'),
    icon: 'bklog-icon bklog-number-2',
    color: '#DDEBE6',
    textColor: '#60A087',
  },
  double: {
    name: i18n.t('数字'),
    icon: 'bklog-icon bklog-number-2',
    color: '#DDEBE6',
    textColor: '#60A087',
  },
  keyword: {
    name: i18n.t('字符串'),
    icon: 'bklog-icon bklog-str-2',
    color: '#D9E5EB',
    textColor: '#6498B3',
  },
  long: {
    name: i18n.t('数字'),
    icon: 'bklog-icon bklog-number-2',
    color: '#DDEBE6',
    textColor: '#60A087',
  },
  text: {
    name: i18n.t('文本'),
    icon: 'bklog-icon bklog-text-2',
    color: '#E1E7F2',
    textColor: '#508CC8',
  },
  date: {
    name: i18n.t('时间'),
    icon: 'bklog-icon bklog-time-2',
    color: '#EDE7DB',
    textColor: '#CDAE71',
  },
  date_nanos: {
    name: i18n.t('时间'),
    icon: 'bklog-icon bklog-time-2',
    color: '#EDE7DB',
    textColor: '#CDAE71',
  },
  boolean: {
    name: i18n.t('布尔'),
    icon: 'bklog-icon bklog-buer-2',
    color: '#F0DFDF',
    textColor: '#CB7979',
  },
  conflict: {
    name: i18n.t('冲突字段'),
    icon: 'bk-icon icon-clock',
    color: '#EDE7DB',
    textColor: '#CDAE71',
  },
  __virtual__: {
    name: i18n.t('内置字段'),
    icon: 'bklog-icon bklog-ext-2',
    color: '#EAE4EB',
    textColor: '#B68ABB',
  },
  object: {
    name: i18n.t('对象'),
    icon: 'bklog-icon bklog-object-2',
    color: '#E8EAF0',
    textColor: '#979BA5',
  },
  flattened: {
    name: i18n.t('扁平化对象'),
    icon: 'bklog-icon bklog-fllatend',
    color: '#E8EAF0',
    textColor: '#63656e',
  },
};

export const SPACE_TYPE_MAP = {
  bkcc: {
    name: i18n.t('业务'),
    dark: {
      color: '#478EFC',
      backgroundColor: '#2B354D',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#CDE8FB',
    },
  },
  default: {
    name: i18n.t('监控空间'),
    dark: {
      color: '#B3B3B3',
      backgroundColor: '#333333',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#DEDEDE',
    },
  },
  bkci: {
    name: i18n.t('研发项目'),
    dark: {
      color: '#F85959',
      backgroundColor: '#4C3232',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#F8D8D4',
    },
  },
  bcs: {
    name: i18n.t('容器项目'),
    dark: {
      color: '#FC943B',
      backgroundColor: '#453921',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#FFF2C9',
    },
  },
  paas: {
    name: i18n.t('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#D8EDD9',
    },
  },
  bksaas: {
    name: i18n.tc('蓝鲸应用'),
    dark: {
      color: '#2BB950',
      backgroundColor: '#223B2B',
    },
    light: {
      color: '#63656E',
      backgroundColor: '#D8EDD9',
    },
  },
};

// echart图表颜色
export const lineColor = [
  '#A3C5FD', // 0: pale green
  '#EAB839', // 1: mustard
  '#6ED0E0', // 2: light blue
  '#EF843C', // 3: orange
  '#E24D42', // 4: red
  '#1F78C1', // 5: ocean
  '#BA43A9', // 6: purple
  '#705DA0', // 7: violet
  '#508642', // 8: dark green
  '#CCA300', // 9: dark sand
  '#447EBC',
  '#C15C17',
  '#890F02',
  '#0A437C',
  '#6D1F62',
  '#584477',
  '#B7DBAB',
  '#F4D598',
  '#70DBED',
  '#F9BA8F',
  '#F29191',
  '#82B5D8',
  '#E5A8E2',
  '#AEA2E0',
  '#629E51',
  '#E5AC0E',
  '#64B0C8',
  '#E0752D',
  '#BF1B00',
  '#0A50A1',
  '#962D82',
  '#614D93',
  '#9AC48A',
  '#F2C96D',
  '#65C5DB',
  '#F9934E',
  '#EA6460',
  '#5195CE',
  '#D683CE',
  '#806EB7',
  '#3F6833',
  '#967302',
  '#2F575E',
  '#99440A',
  '#58140C',
  '#052B51',
  '#511749',
  '#3F2B5B',
  '#E0F9D7',
  '#FCEACA',
  '#CFFAFF',
  '#F9E2D2',
  '#FCE2DE',
  '#BADFF4',
  '#F9D9F9',
  '#DEDAF7',
];
