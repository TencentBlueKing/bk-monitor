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

import { isEn } from 'monitor-pc/i18n/lang';

import type { TranslateResult } from 'vue-i18n';

// AI 快捷方式类型
export interface AIBluekingShortcut {
  components: ComponentConfig[];
  icon?: string;
  id: string;
  name: string | TranslateResult; // 兼容 i18n 翻译结果
  iconRender?: (h: any) => any;
}

// AI 快捷方式数组类型
export type AIBluekingShortcuts = AIBluekingShortcut[];

// 组件配置类型
export interface ComponentConfig {
  default?: number | string;
  fillBack: boolean;
  hide?: boolean;
  key: string;
  name: string | TranslateResult; // 兼容 i18n 翻译结果
  options?: ComponentOption[];
  placeholder: string | TranslateResult; // 兼容 i18n 翻译结果
  required?: boolean;
  selectedText?: string;
  type: 'input' | 'select' | 'textarea';
}

// 组件选项类型
export interface ComponentOption {
  label: string;
  value: string;
}
export const AI_BLUEKING_SHORTCUTS_ID = {
  EXPLANATION: 'explanation',
  TRANSLATE: 'translate',
  PROMQL_HELPER: 'promql_helper',
  METADATA_DIAGNOSIS: 'metadata_diagnosis',
  TRACING_ANALYSIS: 'tracing_analysis',
  PROFILING_ANALYSIS: 'profiling_analysis',
  GENERATE_DASHBOARD: 'generate_dashboard',
} as const;
export type AIBluekingShortcutId = (typeof AI_BLUEKING_SHORTCUTS_ID)[keyof typeof AI_BLUEKING_SHORTCUTS_ID];
export const AI_BLUEKING_SHORTCUTS: AIBluekingShortcuts = [
  {
    id: AI_BLUEKING_SHORTCUTS_ID.EXPLANATION,
    name: window.i18n.t('问问小鲸'),
    iconRender: h =>
      h(
        'svg',
        {
          xmlns: 'http://www.w3.org/2000/svg',
          xmlnsXlink: 'http://www.w3.org/1999/xlink',
          width: '16px',
          height: '16px',
          viewBox: '0 0 32 32',
          style: {
            marginRight: '4px',
          },
        },
        [
          h('defs', [
            h(
              'linearGradient',
              {
                id: 'linearGradient-1',
                x1: '45.02491%',
                y1: '35.5927467%',
                x2: '99.2803929%',
                y2: '81.0358394%',
              },
              [
                h('stop', { 'stop-color': '#235DFA', offset: '0%' }),
                h('stop', { 'stop-color': '#EB8CEC', offset: '100%' }),
              ]
            ),
            h(
              'linearGradient',
              {
                id: 'linearGradient-2',
                x1: '50%',
                y1: '0%',
                x2: '50%',
                y2: '100%',
              },
              [
                h('stop', { 'stop-color': '#FFFFFF', 'stop-opacity': '0.885701426', offset: '0%' }),
                h('stop', { 'stop-color': '#FFFFFF', 'stop-opacity': '0.29', offset: '100%' }),
              ]
            ),
            h(
              'linearGradient',
              {
                id: 'linearGradient-3',
                x1: '50%',
                y1: '0%',
                x2: '50%',
                y2: '100%',
              },
              [
                h('stop', { 'stop-color': '#1562FC', offset: '0%' }),
                h('stop', { 'stop-color': '#EB8CEC', offset: '100%' }),
              ]
            ),
            h(
              'linearGradient',
              {
                id: 'linearGradient-4',
                x1: '50%',
                y1: '95.0902604%',
                x2: '35.112422%',
                y2: '19.6450217%',
              },
              [
                h('stop', { 'stop-color': '#DC63FE', offset: '0.0150240385%' }),
                h('stop', { 'stop-color': '#235DFA', offset: '100%' }),
              ]
            ),
            h(
              'linearGradient',
              {
                id: 'linearGradient-5',
                x1: '46.6072083%',
                y1: '95.8855311%',
                x2: '46.6072083%',
                y2: '50%',
              },
              [
                h('stop', { 'stop-color': '#B962FD', offset: '0%' }),
                h('stop', { 'stop-color': '#565FFB', offset: '99.984976%' }),
              ]
            ),
            h(
              'linearGradient',
              {
                id: 'linearGradient-6',
                x1: '50%',
                y1: '0%',
                x2: '50%',
                y2: '100%',
              },
              [
                h('stop', { 'stop-color': '#235DFA', offset: '0%' }),
                h('stop', { 'stop-color': '#A826E2', offset: '100%' }),
              ]
            ),
          ]),
          h('g', { stroke: 'none', 'stroke-width': '1', fill: 'none', 'fill-rule': 'evenodd' }, [
            h('g', { transform: 'translate(-1561, -1181)' }, [
              h('g', { transform: 'translate(1553, 1174)' }, [
                h('g', { transform: 'translate(8, 7)' }, [
                  h('g', { transform: 'translate(1.3333, 1.677)' }, [
                    h('path', {
                      d: 'M2.66705252,15.6739704 L2.66666667,14.3229852 C2.66666667,9.9047072 6.24838867,6.3229852 10.6666667,6.3229852 L14.6666667,6.3229852 C19.0849447,6.3229852 22.6666667,9.9047072 22.6666667,14.3229852 L22.6671955,23.7678689 C25.0214528,24.0035841 26.6666667,24.6713549 26.6666667,26.3034961 C26.6605025,26.3124265 26.656393,26.3137104 26.6495438,26.3148556 L26.6370784,26.3164707 C26.6173529,26.318489 26.5844771,26.3199738 26.5296841,26.3210118 L26.4843429,26.3217078 C26.4760555,26.3218103 26.4673913,26.3219061 26.4583333,26.3219955 L25.6509582,26.3220036 C25.6249144,26.321929 25.5982028,26.3218506 25.5708063,26.3217686 L25.3980713,26.3212348 C25.3678666,26.3211391 25.3369428,26.3210401 25.3052827,26.320938 L25.1063498,26.3202896 C25.0716761,26.3201758 25.0362319,26.3200592 25,26.31994 L24.7730199,26.3191953 C24.654667,26.3188088 24.528917,26.318402 24.3953077,26.3179795 L24.1174728,26.3171149 C23.70457,26.3158517 23.2247877,26.3144847 22.6672933,26.3131209 L22.6666667,26.3229852 L10.6666667,26.3229852 C6.63303794,26.3229852 3.29664679,23.3377563 2.74629514,19.4561004 C1.15124173,18.9334343 0,17.4384093 0,15.6758076 L1.73233032,15.6750674 C1.83856201,15.6749729 1.94299316,15.6748702 2.0456543,15.6747598 L2.66705252,15.6739704 Z',
                      fill: 'url(#linearGradient-1)',
                    }),
                    h('path', {
                      d: 'M11.3333333,8.98965186 L14,8.98965186 C17.3137085,8.98965186 20,11.6759434 20,14.9896519 L20,21.6563185 C20,22.760888 19.1045695,23.6563185 18,23.6563185 L11.3333333,23.6563185 C8.01962483,23.6563185 5.33333333,20.970027 5.33333333,17.6563185 L5.33333333,14.9896519 C5.33333333,11.6759434 8.01962483,8.98965186 11.3333333,8.98965186 Z',
                      fill: 'url(#linearGradient-2)',
                    }),
                    h('rect', {
                      fill: 'url(#linearGradient-3)',
                      x: '24',
                      y: '10.3229852',
                      width: '2.66666667',
                      height: '12',
                      rx: '1',
                    }),
                    h('path', {
                      d: 'M25.3125069,1.33333333 C25.3125069,3.37253856 26.8384476,5.05534124 28.8107554,5.30216765 L29.3125069,5.33333333 C27.2733017,5.33333333 25.590499,6.85927407 25.3436726,8.83158183 L25.3125069,9.33333333 C25.3125069,7.2941281 23.7865662,5.61132543 21.8142584,5.36449901 L21.3125069,5.33333333 C23.3517121,5.33333333 25.0345148,3.8073926 25.2813412,1.83508483 L25.3125069,1.33333333 Z',
                      fill: 'url(#linearGradient-4)',
                      'fill-rule': 'nonzero',
                    }),
                    h('path', {
                      d: 'M19.9791736,1.92557081e-12 C19.9791736,1.35947015 20.9964674,2.4813386 22.3113392,2.64588955 L22.6458402,2.66666667 C21.2863701,2.66666667 20.1645016,3.68396049 19.9999507,4.99883233 L19.9791736,5.33333333 C19.9791736,3.97386318 18.9618797,2.85199473 17.6470079,2.68744379 L17.3125069,2.66666667 C18.671977,2.66666667 19.7938455,1.64937284 19.9583964,0.334501001 L19.9791736,1.92557081e-12 Z',
                      fill: 'url(#linearGradient-5)',
                      'fill-rule': 'nonzero',
                    }),
                    h('path', {
                      d: 'M21.3125069,6.66666667 C21.3125069,7.34640174 21.8211538,7.90733597 22.4785897,7.98961144 L22.6458402,8 C21.9661051,8 21.4051709,8.50864691 21.3228955,9.16608283 L21.3125069,9.33333333 C21.3125069,8.65359826 20.80386,8.09266403 20.1464241,8.01038856 L19.9791736,8 C20.6589086,8 21.2198429,7.49135309 21.3021183,6.83391717 L21.3125069,6.66666667 Z',
                      fill: '#8860FC',
                      'fill-rule': 'nonzero',
                    }),
                    h('rect', {
                      fill: '#16204D',
                      x: '8.66666667',
                      y: '14.3229852',
                      width: '2.66666667',
                      height: '4',
                      rx: '1.33333333',
                    }),
                    h('rect', {
                      fill: '#16204D',
                      x: '14',
                      y: '14.3229852',
                      width: '2.66666667',
                      height: '4',
                      rx: '1.33333333',
                    }),
                    h('path', {
                      d: 'M16.2528807,6.3229852 C15.8945981,4.54520742 15.1886712,3.65631853 14.1350999,3.65631853 C12.5547431,3.65631853 12.5718314,5.76879538 14.1350999,5.58194526 C14.9597452,5.48337929 15.51887,5.7303926 15.8124743,6.3229852 L16.2528807,6.3229852 Z',
                      fill: 'url(#linearGradient-6)',
                      transform: 'translate(14.6046, 4.9897) scale(-1, 1) translate(-14.6046, -4.9897)',
                    }),
                    h('path', {
                      d: 'M12.9562317,6.3229852 C12.5979491,4.54520742 11.8920221,3.65631853 10.8384509,3.65631853 C9.25809406,3.65631853 9.27518239,5.76879538 10.8384509,5.58194526 C11.6630962,5.48337929 12.2222209,5.7303926 12.5158252,6.3229852 L12.9562317,6.3229852 Z',
                      fill: 'url(#linearGradient-6)',
                    }),
                  ]),
                ]),
              ]),
            ]),
          ]),
        ]
      ),
    components: [
      {
        type: 'textarea',
        key: 'content',
        name: window.i18n.t('内容'),
        fillBack: true,
        required: true,
        placeholder: window.i18n.t('请输入需要解读的内容'),
      },
    ],
  },
  // {
  //   id: AI_BLUEKING_SHORTCUTS_ID.TRANSLATE,
  //   name: window.i18n.t('翻译'),
  //   // icon: 'bkai-translate',
  //   components: [
  //     {
  //       type: 'textarea',
  //       key: 'content',
  //       name: window.i18n.t('待翻译文本'),
  //       fillBack: true,
  //       placeholder: window.i18n.t('请输入需要翻译的内容'),
  //     },
  //     {
  //       type: 'select',
  //       key: 'language',
  //       name: window.i18n.t('语言'),
  //       fillBack: false,
  //       placeholder: window.i18n.t('请选择语言'),
  //       default: 'english',
  //       options: [
  //         { label: 'English', value: 'english' },
  //         { label: '中文', value: 'chinese' },
  //       ],
  //     },
  //   ],
  // },
  {
    id: AI_BLUEKING_SHORTCUTS_ID.PROMQL_HELPER,
    name: window.i18n.t('PromQL助手'),
    // icon: 'icon-monitor icon-mc-help-fill',
    components: [
      {
        type: 'textarea',
        key: 'promql',
        fillBack: true,
        required: true,
        name: window.i18n.t('指标/PromQL语句'),
        placeholder: window.i18n.t('请输入指标/PromQL语句'),
      },
      {
        type: 'textarea',
        key: 'user_demand',
        fillBack: false,
        required: false,
        default: '请根据我提供的PromQL语句，进行解释或者优化',
        name: window.i18n.t('用户指令'),
        placeholder: window.i18n.t('请输入用户指令'),
      },
    ],
  },
  {
    id: AI_BLUEKING_SHORTCUTS_ID.TRACING_ANALYSIS,
    name: window.i18n.t('Trace 助手'),
    // icon: 'icon-monitor icon-mc-help-fill',
    components: [
      {
        type: 'input',
        key: 'trace_id',
        fillBack: true,
        required: false,
        name: 'Trace ID',
        placeholder: window.i18n.t('请输入Trace ID'),
      },
      {
        type: 'input',
        key: 'app_name',
        fillBack: false,
        required: false,
        hide: true,
        name: window.i18n.t('应用名称'),
        placeholder: window.i18n.t('请输入应用名称'),
      },
      {
        type: 'input',
        key: 'bk_biz_id',
        fillBack: false,
        required: false,
        hide: true,
        name: window.i18n.t('业务ID'),
        placeholder: window.i18n.t('请输入业务ID'),
      },
    ],
  },
  {
    id: AI_BLUEKING_SHORTCUTS_ID.PROFILING_ANALYSIS,
    name: window.i18n.t('Profiling 助手'),
    // icon: 'icon-monitor icon-mc-help-fill',
    components: [
      {
        type: 'input',
        key: 'query_params',
        fillBack: true,
        required: false,
        hide: false,
        name: window.i18n.t('Profiling 查询参数'),
        placeholder: window.i18n.t('请输入Profiling 查询参数'),
      },
    ],
  },
  /*
  业务ID为{{ bk_biz_id }}
仪表盘名称为{{ name }}
仪表盘目录为{{ category }}
数据源类型为{{ datasource }}
结果表名称为{{ result_table }}
相关指标为{{ metrics }}
用户需求为{{ demands }}
  */
  {
    id: AI_BLUEKING_SHORTCUTS_ID.GENERATE_DASHBOARD,
    name: window.i18n.t('生成仪表盘'),
    // icon: 'icon-monitor icon-mc-help-fill',
    components: [
      {
        type: 'input',
        key: 'bk_biz_id',
        fillBack: false,
        required: false,
        hide: true,
        name: window.i18n.t('业务ID'),
        placeholder: window.i18n.t('请输入业务ID'),
      },
      {
        type: 'input',
        key: 'name',
        fillBack: true,
        required: true,
        hide: false,
        name: window.i18n.t('仪表盘名称'),
        placeholder: window.i18n.t('请输入仪表盘名称'),
      },
      {
        type: 'select',
        key: 'category',
        fillBack: false,
        required: true,
        hide: false,
        name: window.i18n.t('仪表盘目录'),
        placeholder: window.i18n.t('请输入仪表盘目录'),
        options: [],
      },
      {
        type: 'input',
        key: 'datasource',
        fillBack: false,
        required: false,
        hide: false,
        name: window.i18n.t('数据源'),
        placeholder: window.i18n.t('请输入数据源, 非必需'),
      },
      {
        type: 'input',
        key: 'result_table',
        fillBack: false,
        required: false,
        hide: false,
        name: window.i18n.t('结果表名称'),
        placeholder: window.i18n.t('请输入结果表名称, 非必需'),
      },
      {
        type: 'input',
        key: 'metrics',
        fillBack: false,
        required: false,
        hide: false,
        name: window.i18n.t('相关指标'),
        placeholder: window.i18n.t('请输入相关指标, 非必需'),
      },
      {
        type: 'textarea',
        key: 'demands',
        fillBack: false,
        required: true,
        hide: false,
        name: window.i18n.t('用户需求'),
        placeholder: isEn
          ? 'Please enter the dashboard description, such as: based on {$metrics}, with pod_name as the dimension, generate a line chart.'
          : '请输入仪表盘说明，如：基于{$指标}，以pod_name为维度，生成折线图。',
      },
    ],
  },
  // {
  //   id: AI_BLUEKING_SHORTCUTS_ID.METADATA_DIAGNOSIS,
  //   name: window.i18n.t('链路排障'),
  //   // icon: 'bk-icon icon-monitors-cog',
  //   components: [
  //     {
  //       type: 'textarea',
  //       key: 'bk_data_id',
  //       fillBack: true,
  //       name: window.i18n.t('数据源ID'),
  //       placeholder: window.i18n.t('请输入数据源ID'),
  //     },
  //   ],
  // },
];

export const getAIBluekingShortcutTips = (id: AIBluekingShortcutId) => {
  return (
    AI_BLUEKING_SHORTCUTS.find(shortcut => shortcut.id === id)?.name.toString() || window.i18n.t('AI 小鲸').toString()
  );
};
