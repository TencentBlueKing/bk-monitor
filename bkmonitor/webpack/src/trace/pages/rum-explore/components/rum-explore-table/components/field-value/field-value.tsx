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
import { type PropType, defineComponent, h } from 'vue';

import { useI18n } from 'vue-i18n';

import { isEllipsisActiveSingleLine } from '../../../../../../utils/dom-helper';
import {
  type RumEllipsisModeType,
  RUM_HTTP_STATUS_CODE_MAP,
  RUM_OUTCOME_TYPE_MAP,
  RUM_STATUS_CODE_MAP,
  RumEllipsisModeEnum,
  RumHttpStatusCodeGroupEnum,
  SPAN_KIND_MAPS,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../../../constants';
import { formatFieldValue } from '../../../../utils/array-field-formatter';
import RumEllipsisText from '../../../ellipsis-text';
import { hasFieldValue } from '../../column-builder/column-layout';
import { STANDALONE_TAG_FIELDS } from '../../constants';
import CellIcon from '../cell-icon/cell-icon';
import CountValue, { resolveCountField } from './count-value';
import { canOpenRecordDetail, isSpanName, spanNameHover } from './detail-value';
import FieldTarget from './field-target';

import type {
  BadgePresentation,
  FieldActions,
  FieldAppearance,
  IRumField,
  RumModeType,
  SpanKindPrefixIcon,
  ValueContext,
} from '../../../../typings';
import type { CellIconConfig } from '../cell-icon/cell-icon';

import './field-value.scss';

/** 用统一组件渲染已选择的字段或标签图标。 */
const renderFieldIcon = (config: CellIconConfig | undefined, className?: string) =>
  config ? (
    <CellIcon
      class={[className, config.className]}
      icon={config.icon}
    />
  ) : null;

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
    /** 仅在复合标签位置生效的样式类和图标规则。 */
    badgePresentation: { type: Object as PropType<BadgePresentation>, default: undefined },
  },
  setup(props) {
    const { t } = useI18n();

    /** 打开这一行的详情，避免点击同时触发表格高亮。 */
    const handleOpenDetail = (event: MouseEvent) => {
      event.stopPropagation();
      props.actions.onOpenDetail(props.context.row);
    };

    /** 仅在当前复合成员被截断时展示完整内容。 */
    const handleTextEnter = (event: MouseEvent) => {
      const element = event.currentTarget as HTMLElement;
      const { content, isEllipsisActive } = isEllipsisActiveSingleLine(element);
      if (!isEllipsisActive) return;
      props.actions.hoverPopoverTools.showPopover(event, content, {
        theme: 'dark max-width-40vw text-wrap',
        placement: 'bottom',
        interactive: false,
      });
    };

    return { t, handleOpenDetail, handleTextEnter };
  },
  render() {
    const { field, fieldName, placement, row, rowId, value } = this.context;
    if (!hasFieldValue(value)) return null;

    const badge = placement === 'badge';
    const badgePresentation = badge ? this.badgePresentation : undefined;
    const resolveBadgeIcon = badgePresentation?.resolveIcon;
    const tag = badge || (placement === 'column' && STANDALONE_TAG_FIELDS.has(fieldName));
    const tagClasses = tag ? ['rum-cell-badge', badgePresentation?.className] : undefined;
    const spanName = !badge && isSpanName(this.mode, fieldName);
    const fullUrl = placement === 'item' && this.context.itemType === 'link';
    const target = { fieldName, rowId, searchable: !!field?.is_searched };
    const overflowEvents =
      !spanName && placement !== 'column'
        ? {
            onClick: this.actions.hoverPopoverTools.hidePopover,
            onMouseenter: this.handleTextEnter,
            onMouseleave: this.actions.hoverPopoverTools.clearPopoverTimer,
          }
        : {};

    /** 保留完整文本供条件菜单和悬浮提示使用，省略方向由省略方式决定；徽标是短标签，不参与省略 */
    const renderText = (text: string) =>
      badge ? (
        <span
          {...overflowEvents}
          class={['rum-field-text', 'rum-field-text--no-ellipsis', { 'rum-composite-url': fullUrl }]}
        >
          {text}
        </span>
      ) : (
        <RumEllipsisText
          {...overflowEvents}
          class={['rum-field-text', { 'rum-composite-url': fullUrl }]}
          mode={this.ellipsisMode}
          text={text}
        />
      );

    if (badge && Array.isArray(value)) {
      return value.map((item, index) =>
        hasFieldValue(item) ? (
          <span
            key={index}
            class='rum-field-badge-item'
          >
            <FieldTarget
              class={tagClasses}
              target={{ ...target, index }}
            >
              {renderFieldIcon(resolveBadgeIcon?.(item), 'rum-composite-badge-icon')}
              {renderText(formatFieldValue(item, field))}
            </FieldTarget>
          </span>
        ) : null
      );
    }

    const { icon: fieldIcon, text: fallbackText, style } = resolveFieldAppearance(fieldName, value, badge);
    const icon = resolveBadgeIcon
      ? renderFieldIcon(resolveBadgeIcon(value), 'rum-composite-badge-icon')
      : renderFieldIcon(fieldIcon);
    const vitalMetric = row['attributes.vital.metric'];
    const text =
      Array.isArray(value) && placement === 'item'
        ? value
            .filter(hasFieldValue)
            .map(item => formatFieldValue(item, field, vitalMetric))
            .join(', ')
        : formatFieldValue(value, field, vitalMetric, fallbackText);
    const drillDown = resolveCountField(this.mode, fieldName);
    if (drillDown) {
      return (
        <CountValue
          class={badgePresentation?.className}
          badge={badge}
          drillDown={drillDown}
          row={row}
          target={target}
          value={value}
          onDrillDown={this.actions.onCountClick}
        >
          {badge && icon}
          {placement === 'column' ? text : renderText(text)}
        </CountValue>
      );
    }

    const canOpenDetail = !badge && canOpenRecordDetail(this.mode, fieldName, row, rowId);
    const rating = getRatingClass(field, value);
    const hover = spanName
      ? spanNameHover(row, field?.alias ?? this.t('Span 名称'), text, this.actions.hoverPopoverTools)
      : {};
    return (
      <FieldTarget
        {...hover}
        style={tag ? style : undefined}
        class={[tagClasses, icon && 'rum-icon-text', rating, canOpenDetail && 'rum-link-text']}
        action={canOpenDetail ? this.handleOpenDetail : undefined}
        target={target}
      >
        {icon}
        {renderText(text)}
      </FieldTarget>
    );
  },
});

/** 从接口阈值计算数值的评级样式。 */
const getRatingClass = (field: IRumField | undefined, value: unknown) => {
  const thresholds = field?.rating_config;
  const number = Number(value);
  if (!thresholds?.length || Array.isArray(value) || !Number.isFinite(number)) return '';
  const rating = (thresholds.find(item => item.value === undefined || number <= item.value) ?? thresholds.at(-1))
    ?.rating;
  if (!['good', 'needs_improvement', 'poor'].includes(rating)) return '';
  return `rum-rating-value is-${rating.replace('_', '-')}`;
};

/** 将旧字库类串中的字形和样式类交给 CellIcon。 */
const toFontIconConfig = (fontClasses: string, className: string): CellIconConfig | undefined => {
  const [icon, ...styleClasses] = fontClasses
    .trim()
    .split(/\s+/)
    .filter(name => name !== 'icon-monitor');
  return icon ? { icon, className: [className, ...styleClasses].join(' ') } : undefined;
};

/** 只有无需表格上下文的 kind 图标回调才能直接用于 RUM 字段。 */
const isContextFreeKindIcon = (
  icon: SpanKindPrefixIcon | undefined
): icon is () => ReturnType<Exclude<SpanKindPrefixIcon, string>> => typeof icon === 'function' && icon.length === 0;

/** 为需要特殊呈现的字段补充图标、配色和备用文案。 */
const resolveFieldAppearance = (fieldName: string, value: unknown, badge: boolean): FieldAppearance => {
  switch (fieldName) {
    case SPAN_TYPE_FIELD: {
      const { icon: source, fontIcon, label } = SPAN_TYPE_META[String(value)] ?? {};
      if (source) {
        return {
          text: label,
          icon: {
            icon: () => h('img', { class: 'span-type-icon', alt: '', src: source }),
          },
        };
      }
      return {
        text: label,
        icon: fontIcon ? toFontIconConfig(fontIcon, 'span-type-font-icon') : undefined,
      };
    }
    case 'kind': {
      const meta = SPAN_KIND_MAPS[Number(value)];
      const prefixIcon = meta?.prefixIcon;
      if (typeof prefixIcon === 'string') {
        return { text: meta.alias, icon: toFontIconConfig(prefixIcon, 'prefix-icon') };
      }
      return { text: meta?.alias, icon: isContextFreeKindIcon(prefixIcon) ? { icon: prefixIcon } : undefined };
    }
    case 'attributes.outcome.type': {
      const meta = RUM_OUTCOME_TYPE_MAP[String(value)];
      return {
        text: meta?.label,
        icon: meta?.icon ? { icon: meta.icon, className: `prefix-icon ${meta.className}` } : undefined,
      };
    }
    case 'attributes.resource.cache.hit':
      return value === true || value === 'true'
        ? {
            text: 'HIT',
            icon: { icon: 'icon-mc-check-small' },
          }
        : {};
    case 'status.code': {
      const config = RUM_STATUS_CODE_MAP[Number(value)];
      if (!config) return {};
      return {
        text: config.alias,
        style: badge
          ? { '--rum-badge-tint': config.tagColor }
          : { color: config.tagColor, backgroundColor: config.tagBgColor },
      };
    }
    case 'attributes.http.response.status_code': {
      const group = Math.floor(Number(value) / 100);
      const config = RUM_HTTP_STATUS_CODE_MAP[group];
      if (!config) return {};
      const tint = group === RumHttpStatusCodeGroupEnum.SUCCESS ? '#23ad89' : config.tagBgColor;
      return {
        style: badge ? { '--rum-badge-tint': tint } : { color: config.tagColor, backgroundColor: config.tagBgColor },
      };
    }
    default:
      return {};
  }
};
