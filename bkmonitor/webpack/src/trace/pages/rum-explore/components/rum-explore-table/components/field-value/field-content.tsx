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
import { isEllipsisActiveSingleLine } from '../../../../../../utils/dom-helper';
import { formatFieldValue } from '../../../../utils/array-field-formatter';
import RumEllipsisText from '../../../ellipsis-text';
import { hasFieldValue } from '../../column-builder/column-layout';
import CellIcon from '../cell-icon/cell-icon';
import FieldTarget from './field-target';

import type { RumEllipsisModeType } from '../../../../constants';
import type { BadgePresentation, FieldActions, FieldPlacement, IRumField, ValueContext } from '../../../../typings';
import type { CellIconConfig } from '../cell-icon/cell-icon';
import type { FieldTargetInfo } from './field-target';

type HoverTools = FieldActions['hoverPopoverTools'];

/**
 * @description 按接口字段元数据格式化展示文本，复合正文中的数组逐项格式化后拼接。
 * @param context 包含字段、原始值、展示位置和指标所属记录的上下文
 * @param fallbackText 特殊字段提供的备用文案
 * @returns 用于单元格展示和悬浮提示的完整文本
 */
export function formatCellText({ field, placement, row, value }: ValueContext, fallbackText?: string) {
  const vitalMetric = row['attributes.vital.metric'];
  if (placement === 'item' && Array.isArray(value)) {
    return value
      .filter(hasFieldValue)
      .map(item => formatFieldValue(item, field, vitalMetric))
      .join(', ');
  }
  return formatFieldValue(value, field, vitalMetric, fallbackText);
}

/**
 * @description 逐项渲染数组标签，跳过空项并保留条件菜单回溯原值所需的下标。
 * @param values 字段的原始数组
 * @param field 用于文本格式化的字段元信息
 * @param target 条件菜单定位字段及行所需的信息
 * @param badge 标签专用的样式和选图规则
 * @param tools 表格共用的悬浮层控制器
 * @returns 与原始数组下标对应的标签节点，空项保留为 null
 */
export function renderBadgeList(
  values: unknown[],
  field: IRumField | undefined,
  target: FieldTargetInfo,
  badge: BadgePresentation | undefined,
  tools: HoverTools
) {
  return values.map((value, index) =>
    hasFieldValue(value) ? (
      <span
        key={index}
        class='rum-field-badge-item'
      >
        <FieldTarget
          class={['rum-field-badge', badge?.className]}
          target={{ ...target, index }}
        >
          {renderFieldIcon(badge?.resolveIcon?.(value), 'rum-field-badge-icon')}
          {renderBadgeText(formatFieldValue(value, field), tools)}
        </FieldTarget>
      </span>
    ) : null
  );
}

/**
 * @description 根据字段的展示位置选择标签文本或可省略的文本。
 * @param text 格式化后的完整文本
 * @param placement 字段在普通列或复合列中的位置
 * @param ellipsisMode 文本的省略位置
 * @param itemTextClass 仅应用于复合正文的附加样式类
 * @param tools 表格共用的悬浮层控制器，专用提示接管时省略
 * @returns 对应位置的文本节点
 */
export function renderCellText(
  text: string,
  placement: FieldPlacement,
  ellipsisMode: RumEllipsisModeType,
  itemTextClass: string | undefined,
  tools: HoverTools | undefined
) {
  if (placement === 'badge') return renderBadgeText(text, tools);
  return (
    <RumEllipsisText
      {...(placement === 'item' ? overflowEvents(tools) : {})}
      class={['rum-field-text', placement === 'item' && itemTextClass]}
      mode={ellipsisMode}
      text={text}
    />
  );
}

/**
 * @description 用 CellIcon 渲染字段图标并合并当前位置的样式类。
 * @param config 字段或标签选出的图标配置
 * @param className 图标在当前位置使用的附加样式类
 * @returns 图标节点，无配置时返回 null
 */
export function renderFieldIcon(config: CellIconConfig | undefined, className?: string) {
  return config ? (
    <CellIcon
      class={[className, config.className]}
      icon={config.icon}
    />
  ) : null;
}

/**
 * @description 为文本绑定溢出提示以及提示的收起事件。
 * @param tools 表格共用的悬浮层控制器，省略时由调用方负责悬浮交互
 * @returns 传给文本节点的事件集合
 */
function overflowEvents(tools?: HoverTools) {
  if (!tools) return {};
  return {
    onClick: tools.hidePopover,
    /**
     * @description 在当前文本确实被截断时展示完整内容。
     * @param event 当前文本节点的鼠标移入事件
     */
    onMouseenter(event: MouseEvent) {
      const { content, isEllipsisActive } = isEllipsisActiveSingleLine(event.currentTarget as HTMLElement);
      if (isEllipsisActive) {
        tools.showPopover(event, content, {
          theme: 'dark max-width-40vw text-wrap',
          placement: 'bottom',
          interactive: false,
        });
      }
    },
    onMouseleave: tools.clearPopoverTimer,
  };
}

/**
 * @description 渲染完整的标签文本并绑定悬浮层的收起交互。
 * @param text 格式化后的标签文本
 * @param tools 表格共用的悬浮层控制器
 * @returns 无省略样式的标签文本节点
 */
function renderBadgeText(text: string, tools?: HoverTools) {
  return (
    <span
      class='rum-field-text rum-field-text--no-ellipsis'
      {...overflowEvents(tools)}
    >
      {text}
    </span>
  );
}
