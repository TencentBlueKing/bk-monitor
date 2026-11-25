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
import type { CSSProperties } from 'vue';

import type { CellIconConfig } from '../components/rum-explore-table/components/cell-icon/cell-icon';
import type { SPAN_KIND_MAPS } from '../constants';
import type { IRumCountDrillDown } from './common';
import type { IRumSpanRecord } from './record';
import type { IRumField } from './view-config';
import type { IUsePopoverTools } from '@/pages/alarm-center/components/alarm-table/hooks/use-popover';

/** 列构建层为复合标签提供的展示配置。 */
export interface BadgePresentation {
  /** 应用于标签的色系、字体等样式类。 */
  className?: string;
  /** 按标量或单个数组项的原始值选择标签图标。 */
  resolveIcon?: (rawValue: unknown) => CellIconConfig | undefined;
}

/** 表格传给字段值的详情、下钻和悬浮回调。 */
export interface FieldActions {
  /** 表格共用的悬浮层控制器。 */
  hoverPopoverTools: Pick<IUsePopoverTools, 'clearPopoverTimer' | 'hidePopover' | 'showPopover'>;
  /** 从计数字段切换视角和筛选条件。 */
  onCountClick: (payload: IRumCountDrillDown) => void;
  /** 打开当前行的记录详情。 */
  onOpenDetail: (row: IRumSpanRecord) => void;
}

/** 字段格式化与渲染使用的展示配置。 */
export interface FieldAppearance {
  /** 字段默认图标。 */
  icon?: CellIconConfig;
  /** 状态等字段的字色和背景。 */
  style?: CSSProperties;
  /** 枚举和格式化规则未提供文案时使用的文本。 */
  text?: string;
}

/** 字段在表格中的展示位置，影响标签样式和可用的点击动作。 */
export type FieldPlacement = 'badge' | 'column' | 'item';

/** Trace 的 kind 图标定义兼容通用的表格渲染回调。 */
export type SpanKindPrefixIcon = (typeof SPAN_KIND_MAPS)[number]['prefixIcon'];

/** 独立列和复合成员共用的字段渲染参数。 */
export interface ValueContext {
  /** 用于枚举、单位和权限推导的字段元信息。 */
  field?: IRumField;
  /** 当前值所对应的真实字段名。 */
  fieldName: string;
  /** 当前字段在单元格中的展示位置。 */
  placement: FieldPlacement;
  /** 提供详情、下钻和按行确定单位的原始记录。 */
  row: IRumSpanRecord;
  /** 单元格菜单回溯原始记录所用的行标识。 */
  rowId: string;
  /** 未经展示格式化的原始字段值。 */
  value: unknown;
}
