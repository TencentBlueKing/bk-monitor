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
  __virtual__: {
    color: '#EAE4EB',
    icon: 'bklog-icon bklog-ext-2',
    name: i18n.t('内置字段'),
    textColor: '#B68ABB',
  },
  any: {
    color: '#DCDEE5',
    icon: 'bk-icon icon-check-line',
    name: i18n.t('不限'),
  },
  boolean: {
    color: '#F0DFDF',
    icon: 'bklog-icon bklog-buer-2',
    name: i18n.t('布尔'),
    textColor: '#CB7979',
  },
  conflict: {
    color: '#EDE7DB',
    icon: 'bk-icon icon-clock',
    name: i18n.t('冲突字段'),
    textColor: '#CDAE71',
  },
  date: {
    color: '#EDE7DB',
    icon: 'bklog-icon bklog-time-2',
    name: i18n.t('时间'),
    textColor: '#CDAE71',
  },
  date_nanos: {
    color: '#EDE7DB',
    icon: 'bklog-icon bklog-time-2',
    name: i18n.t('时间'),
    textColor: '#CDAE71',
  },
  double: {
    color: '#DDEBE6',
    icon: 'bklog-icon bklog-number-2',
    name: i18n.t('数字'),
    textColor: '#60A087',
  },
  integer: {
    color: '#DDEBE6',
    icon: 'bklog-icon bklog-number-2',
    name: i18n.t('数字'),
    textColor: '#60A087',
  },
  keyword: {
    color: '#D9E5EB',
    icon: 'bklog-icon bklog-str-2',
    name: i18n.t('字符串'),
    textColor: '#6498B3',
  },
  long: {
    color: '#DDEBE6',
    icon: 'bklog-icon bklog-number-2',
    name: i18n.t('数字'),
    textColor: '#60A087',
  },
  number: {
    color: '#DDEBE6',
    icon: 'bklog-icon bklog-number-2',
    name: i18n.t('数字'),
    textColor: '#60A087',
  },
  object: {
    color: '#E8EAF0',
    icon: 'bklog-icon bklog-object-2',
    name: i18n.t('对象'),
    textColor: '#979BA5',
  },
  text: {
    color: '#E1E7F2',
    icon: 'bklog-icon bklog-text-2',
    name: i18n.t('文本'),
    textColor: '#508CC8',
  },
};

export const SPACE_TYPE_MAP = {
  bcs: {
    dark: {
      backgroundColor: '#453921',
      color: '#FC943B',
    },
    light: {
      backgroundColor: '#FFF2C9',
      color: '#63656E',
    },
    name: i18n.t('容器项目'),
  },
  bkcc: {
    dark: {
      backgroundColor: '#2B354D',
      color: '#478EFC',
    },
    light: {
      backgroundColor: '#CDE8FB',
      color: '#63656E',
    },
    name: i18n.t('业务'),
  },
  bkci: {
    dark: {
      backgroundColor: '#4C3232',
      color: '#F85959',
    },
    light: {
      backgroundColor: '#F8D8D4',
      color: '#63656E',
    },
    name: i18n.t('研发项目'),
  },
  bksaas: {
    dark: {
      backgroundColor: '#223B2B',
      color: '#2BB950',
    },
    light: {
      backgroundColor: '#D8EDD9',
      color: '#63656E',
    },
    name: i18n.tc('蓝鲸应用'),
  },
  default: {
    dark: {
      backgroundColor: '#333333',
      color: '#B3B3B3',
    },
    light: {
      backgroundColor: '#DEDEDE',
      color: '#63656E',
    },
    name: i18n.t('监控空间'),
  },
  paas: {
    dark: {
      backgroundColor: '#223B2B',
      color: '#2BB950',
    },
    light: {
      backgroundColor: '#D8EDD9',
      color: '#63656E',
    },
    name: i18n.t('蓝鲸应用'),
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
