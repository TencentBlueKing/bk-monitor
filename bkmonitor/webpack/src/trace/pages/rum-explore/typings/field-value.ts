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
import type { RumModeType } from './enum';
import type { IRumSpanRecord } from './record';
import type { IRumField } from './view-config';
import type { IUsePopoverTools } from '@/pages/alarm-center/components/alarm-table/hooks/use-popover';
import type { TippyContent } from 'vue-tippy';

/** 字段在复合标签位置使用的样式与图标。 */
export interface BadgePresentation {
  /** 应用于标签的色系、字体等样式类。 */
  className?: string;
  /** 按标量或单个数组项的原始值选择标签图标。 */
  resolveIcon?: (rawValue: unknown) => CellIconConfig | undefined;
}

/** 当前视角下计数字段的下钻目标。 */
export interface CountDrillDown extends Pick<IRumCountDrillDown, 'spanType' | 'targetMode'> {
  /** 从当前行读取筛选值并用于下钻条件的 ID 字段。 */
  idField: string;
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

/** 按字段名登记的 RUM 表格展示和交互规则。 */
export interface FieldRule {
  /** 复合列标签专用的附加样式和选图规则。 */
  badge?: BadgePresentation;
  /** 随当前检索视角变化的交互配置。 */
  byMode?: Partial<Record<RumModeType, FieldModeRule>>;
  /** 字段独立成列时是否使用标签样式。 */
  columnAsTag?: boolean;
  /** 字段出现在复合列正文时附加的文本样式类。 */
  itemTextClass?: string;
  /** 根据字段原值和标签位置生成图标、配色及备用文案。 */
  appearance?: (value: unknown, badge: boolean) => FieldAppearance;
}

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

/** 字段在单个检索视角下的交互规则。 */
interface FieldModeRule {
  /** 计数下钻的目标视角和筛选字段。 */
  drillDown?: CountDrillDown;
  /** 根据当前记录判断该字段能否打开详情。 */
  canOpenDetail?: (context: ValueContext) => boolean;
  /** 在悬浮时根据当前记录和完整展示文本生成专用提示。 */
  getTooltip?: (
    context: ValueContext,
    text: string,
    t: (key: string) => string
  ) => {
    /** 传给表格悬浮层的提示内容。 */
    content: TippyContent;
    /** 专用提示使用的悬浮层主题。 */
    theme: string;
  };
}
