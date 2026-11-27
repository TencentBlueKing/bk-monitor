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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import { type RumEllipsisModeType, RumEllipsisModeEnum } from '../../../../constants';
import { hasFieldValue } from '../../column-builder/column-layout';
import { getRatingClass } from '../../field-appearance';
import { getFieldRule } from '../../field-rules';
import CountValue from './count-value';
import { formatCellText, renderBadgeList, renderCellText, renderFieldIcon } from './field-content';
import FieldTarget from './field-target';

import type { FieldActions, RumModeType, ValueContext } from '../../../../typings';

import './field-value.scss';

export default defineComponent({
  name: 'RumFieldValue',
  props: {
    /** 当前字段所在位置、行和原始值。 */
    context: { type: Object as PropType<ValueContext>, required: true },
    /** 用于决定计数和详情交互的检索视角。 */
    mode: { type: String as PropType<RumModeType>, required: true },
    /** 字段需要的表格级交互。 */
    actions: { type: Object as PropType<FieldActions>, required: true },
    /** 单元格文本省略方式，默认 ...yz（开头省略） */
    ellipsisMode: { type: String as PropType<RumEllipsisModeType>, default: RumEllipsisModeEnum.START },
  },
  /**
   * @description 准备字段提示的国际化函数及详情点击处理。
   * @param props 当前字段上下文与表格交互回调
   * @returns 渲染使用的国际化函数及详情点击处理函数
   */
  setup(props) {
    const { t } = useI18n();
    /**
     * @description 打开当前行详情并阻止点击触发行高亮。
     * @param event 字段值的点击事件
     */
    const handleOpenDetail = (event: MouseEvent) => {
      event.stopPropagation();
      props.actions.onOpenDetail(props.context.row);
    };
    return { t, handleOpenDetail };
  },
  /**
   * @description 根据字段位置与当前视角，组装数组标签、计数或普通字段节点。
   * @returns 单元格内容，空值返回 null
   */
  render() {
    const { field, fieldName, placement, row, rowId, value } = this.context;
    if (!hasFieldValue(value)) return null;

    const rule = getFieldRule(fieldName);
    const badge = placement === 'badge';
    const target = { fieldName, rowId, searchable: !!field?.is_searched };
    const tools = this.actions.hoverPopoverTools;
    if (badge && Array.isArray(value)) return renderBadgeList(value, field, target, rule.badge, tools);

    const modeRule = rule.byMode?.[this.mode];
    const getTooltip = badge ? undefined : modeRule?.getTooltip;
    const appearance = rule.appearance?.(value, badge);
    const text = formatCellText(this.context, appearance?.text);
    const badgeStyle = badge ? rule.badge : undefined;
    const icon = badgeStyle?.resolveIcon
      ? renderFieldIcon(badgeStyle.resolveIcon(value), 'rum-field-badge-icon')
      : renderFieldIcon(appearance?.icon);
    /**
     * @description 渲染当前字段文本，专用悬浮提示接管时跳过通用溢出提示。
     * @returns 当前展示位置的文本节点
     */
    const renderText = () =>
      renderCellText(text, placement, this.ellipsisMode, rule.itemTextClass, getTooltip ? undefined : tools);

    if (modeRule?.drillDown) {
      return (
        <CountValue
          class={badge ? ['rum-field-badge', badgeStyle?.className] : undefined}
          badge={badge}
          drillDown={modeRule.drillDown}
          row={row}
          target={target}
          value={value}
          onDrillDown={this.actions.onCountClick}
        >
          {badge && icon}
          {placement === 'column' ? text : renderText()}
        </CountValue>
      );
    }

    const columnTag = placement === 'column' && rule.columnAsTag;
    const canOpenDetail = !badge && modeRule?.canOpenDetail?.(this.context);
    const hover = getTooltip && {
      /**
       * @description 悬浮时生成并展示当前字段的专用提示。
       * @param event 当前字段节点的鼠标移入事件
       */
      onMouseenter: (event: MouseEvent) => {
        const { content, theme } = getTooltip(this.context, text, this.t);
        tools.showPopover(event, content, { theme });
      },
      onMouseleave: tools.clearPopoverTimer,
    };
    return (
      <FieldTarget
        {...hover}
        style={badge || columnTag ? appearance?.style : undefined}
        class={[
          badge && 'rum-field-badge',
          columnTag && 'rum-field-tag',
          badgeStyle?.className,
          icon && 'rum-icon-text',
          getRatingClass(field, value),
          canOpenDetail && 'rum-field-detail-trigger',
        ]}
        action={canOpenDetail ? this.handleOpenDetail : undefined}
        target={target}
      >
        {icon}
        {renderText()}
      </FieldTarget>
    );
  },
});
