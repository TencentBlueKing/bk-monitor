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
  name: TranslateResult | string; // 兼容 i18n 翻译结果
}

// AI 快捷方式数组类型
export type AIBluekingShortcuts = AIBluekingShortcut[];

// 组件配置类型
export interface ComponentConfig {
  default?: number | string;
  fillBack: boolean;
  hide?: boolean;
  key: string;
  name: TranslateResult | string; // 兼容 i18n 翻译结果
  options?: ComponentOption[];
  placeholder: TranslateResult | string; // 兼容 i18n 翻译结果
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
  LOG_ANALYSIS: 'log_analysis',
} as const;

export type AIBluekingShortcutId = (typeof AI_BLUEKING_SHORTCUTS_ID)[keyof typeof AI_BLUEKING_SHORTCUTS_ID];

// index_set_id,
// log,
// context_count

export const AI_BLUEKING_SHORTCUTS: AIBluekingShortcuts = [
  {
    id: AI_BLUEKING_SHORTCUTS_ID.LOG_ANALYSIS,
    name: window.$t('日志解读'),
    components: [
      {
        type: 'textarea',
        key: 'index_set_id',
        name: window.$t('内容'),
        fillBack: true,
        required: true,
        hide: true,
        placeholder: window.$t('请输入需要解读的内容'),
      },
      {
        type: 'textarea',
        key: 'context_count',
        name: window.$t('内容'),
        default: 10,
        fillBack: true,
        required: true,
        hide: true,
        placeholder: window.$t('请输入需要解读的内容'),
      },
      {
        type: 'textarea',
        key: 'index',
        name: window.$t('内容'),
        fillBack: true,
        required: true,
        hide: true,
        placeholder: window.$t('请输入需要解读的内容'),
      },
      {
        type: 'textarea',
        key: 'log',
        name: window.$t('内容'),
        fillBack: true,
        required: true,
        placeholder: window.$t('请输入需要解读的内容'),
      },
    ],
  },
];
