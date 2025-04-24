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

/** 全量 */
export const ALL_OPTION = 'allOption';
/** 勾选项 */
export const CHECKED_OPTION = 'checkedOption';
/** 编辑范围 */
export const RADIO_OPTIONS = [
  { id: ALL_OPTION, label: window.i18n.tc('全量') },
  { id: CHECKED_OPTION, label: window.i18n.tc('勾选项') },
];
/** 全选框状态 */
export enum CheckboxStatus {
  ALL_CHECKED = 2, // 全选
  INDETERMINATE = 1, // 半选
  UNCHECKED = 0, // 未选
}
/** 全部 */
export const ALL_LABEL = '__all_label__';
/** 未分组 */
export const NULL_LABEL = '__null_label__';

/** 分组列表 */
export interface IGroupListItem {
  name: string; // 分组名称
  matchRules: string[]; // 匹配规则
  manualList: string[]; // 手动添加的指标
  matchRulesOfMetrics?: string[]; // 匹配规则匹配的指标列表
}

/** 表格列配置 */
export interface IColumnConfig {
  label: string;
  width: number;
  type?: string;
  renderFn: (props: any, key?: any) => any;
  renderHeaderFn?: (config: any) => any;
}

export interface PopoverInstance extends Vue {
  $el: HTMLDivElement;
  hideHandler: () => void;
}

export type PopoverChildRef = Vue & {
  $refs: {
    refDropdownContent?: PopoverInstance;
    selectDropdown?: any;
  };
};

export type MetricHeaderKeys = keyof Pick<
  IMetricItem,
  'aggregate_method' | 'dimensions' | 'function' | 'interval' | 'unit'
>;

export interface IMetricItem {
  name: string;
  description?: string;
  unit?: string;
  aggregate_method?: string;
  interval?: number;
  function?: string[];
  hidden?: boolean;
  disabled?: boolean;
  isNew?: boolean;
  dimensions?: string[];
  error?: string;
  selection?: boolean;
}

export interface IDimensionItem {
  name: string;
  description?: string;
  disabled?: boolean;
  isNew?: boolean;
  error?: string;
  common?: boolean;
  type?: string;
  selection?: boolean;
  hidden?: boolean;
}

export type DimensionHeaderKeys = keyof Pick<IDimensionItem, 'common' | 'hidden'>;
