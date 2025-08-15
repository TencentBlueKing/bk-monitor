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

import type { TranslateResult } from 'vue-i18n';

// AI 快捷方式类型
export interface AIBluekingShortcut {
  components: ComponentConfig[];
  icon?: string;
  id: string;
  name: string | TranslateResult; // 兼容 i18n 翻译结果
}

// AI 快捷方式数组类型
export type AIBluekingShortcuts = AIBluekingShortcut[];

// 组件配置类型
export interface ComponentConfig {
  default?: string;
  fillBack: boolean;
  key: string;
  name: string | TranslateResult; // 兼容 i18n 翻译结果
  options?: ComponentOption[];
  placeholder: string | TranslateResult; // 兼容 i18n 翻译结果
  required?: boolean;
  selectedText?: string;
  type: 'select' | 'textarea';
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
} as const;
export type AIBluekingShortcutId = (typeof AI_BLUEKING_SHORTCUTS_ID)[keyof typeof AI_BLUEKING_SHORTCUTS_ID];
export const AI_BLUEKING_SHORTCUTS: AIBluekingShortcuts = [
  {
    id: AI_BLUEKING_SHORTCUTS_ID.EXPLANATION,
    name: window.i18n.t('解读'),
    // icon: 'bkai-help',
    components: [
      {
        type: 'textarea',
        key: 'content',
        name: window.i18n.t('内容'),
        fillBack: true,
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
        required: true,
        name: window.i18n.t('用户指令'),
        placeholder: window.i18n.t('请输入用户指令'),
      },
    ],
  },
  // {
  //   id: AI_BLUEKING_SHORTCUTS_ID.TRACING_ANALYSIS,
  //   name: window.i18n.t('Trace 助手'),
  //   // icon: 'icon-monitor icon-mc-help-fill',
  //   components: [
  //     {
  //       type: 'textarea',
  //       key: 'trace_id',
  //       fillBack: true,
  //       required: true,
  //       name: window.i18n.t('Trace ID'),
  //       placeholder: window.i18n.t('请输入Trace ID'),
  //     },
  //     {
  //       type: 'textarea',
  //       key: 'app_name',
  //       fillBack: false,
  //       required: true,
  //       name: window.i18n.t('应用名称'),
  //       placeholder: window.i18n.t('请输入应用名称'),
  //     },
  //   ],
  // },
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
