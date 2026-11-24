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
import type { VNodeChild } from 'vue';

import { useI18n } from 'vue-i18n';

import {
  RUM_HTTP_STATUS_CODE_MAP,
  RUM_OUTCOME_TYPE_MAP,
  RUM_STATUS_CODE_MAP,
  SPAN_KIND_MAPS,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../../../constants';
import { formatFieldValue } from '../../../../utils/array-field-formatter';
import { hasFieldValue } from '../../column-layout';
import CountValue, { resolveCountField } from './count-value';
import { canOpenRecordDetail, isSpanName, spanNameHover } from './detail-value';
import FieldTarget from './field-target';

import type { IRumCountDrillDown, IRumField, IRumSpanRecord, RumModeType } from '../../../../typings';
import type { TippyContent } from 'vue-tippy';

import './field-value.scss';

/** 表格传给字段值的详情、下钻和悬浮回调。 */
export interface FieldActions {
  /** 从计数字段切换视角和筛选条件。 */
  onCountClick: (payload: IRumCountDrillDown) => void;
  /** 打开当前行的记录详情。 */
  onOpenDetail: (row: IRumSpanRecord) => void;
  /** 表格共用的悬浮层控制器。 */
  hoverPopoverTools: {
    /** 清除尚未显示的悬浮提示。 */
    clearPopoverTimer: () => void;
    /** 在触发元素附近展示字段提示。 */
    showPopover: (event: MouseEvent, content: TippyContent, options: unknown) => void;
  };
}

/** 字段在表格中的展示位置，影响标签样式和可用的点击动作。 */
export type FieldPlacement = 'badge' | 'column' | 'item';

/** 独立列和复合成员共用的字段渲染参数。 */
interface ValueContext {
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

const TAG_STYLES: Record<string, string> = {
  'attributes.action.frustration.type': 'rum-badge-long-task',
  'attributes.action.type': 'rum-badge-action',
  'attributes.long_task.entry_type': 'rum-badge-long-task',
  'attributes.resource.type': 'rum-badge-resource',
  'attributes.view.loading_type': 'rum-badge-view',
  'events.attributes.exception.type': 'rum-badge-error',
};

export default defineComponent({
  name: 'RumFieldValue',
  props: {
    /** 当前字段所在位置、行和原始值。 */
    context: { type: Object as PropType<ValueContext>, required: true },
    /** 用于决定计数和详情交互的检索视角。 */
    mode: { type: String as PropType<RumModeType>, required: true },
    /** 字段需要的表格级交互。 */
    actions: { type: Object as PropType<FieldActions>, required: true },
  },
  setup(props) {
    const { t } = useI18n();

    /** 打开这一行的详情，避免点击同时触发表格高亮。 */
    const handleOpenDetail = (event: MouseEvent) => {
      event.stopPropagation();
      props.actions.onOpenDetail(props.context.row);
    };

    return { t, handleOpenDetail };
  },
  render() {
    const { field, fieldName, placement, row, rowId, value } = this.context;
    if (!hasFieldValue(value)) return null;

    const badge = placement === 'badge';
    const target = { fieldName, rowId, searchable: !!field?.is_searched };
    if (badge && Array.isArray(value)) {
      return value.map((item, index) =>
        hasFieldValue(item) ? (
          <span
            key={index}
            class='rum-field-badge-item'
          >
            <FieldTarget
              class={['rum-cell-badge', TAG_STYLES[fieldName]]}
              target={{ ...target, index }}
            >
              {formatFieldValue(item, field)}
            </FieldTarget>
          </span>
        ) : null
      );
    }

    const { icon, text: fallbackText, style } = resolveFieldAppearance(fieldName, value);
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
          badge={badge}
          drillDown={drillDown}
          row={row}
          target={target}
          text={text}
          value={value}
          onDrillDown={this.actions.onCountClick}
        />
      );
    }

    const spanName = !badge && isSpanName(this.mode, fieldName);
    const canOpenDetail = !badge && canOpenRecordDetail(this.mode, fieldName, row, rowId);
    const rating = getRatingClass(field, value);
    const tag =
      badge ||
      ['status.code', 'attributes.http.request.method', 'attributes.http.response.status_code'].includes(fieldName);
    const hover = spanName
      ? spanNameHover(row, field?.alias ?? this.t('Span 名称'), text, this.actions.hoverPopoverTools)
      : {};
    return (
      <FieldTarget
        {...hover}
        style={style}
        class={[
          tag && 'rum-cell-badge',
          tag && TAG_STYLES[fieldName],
          icon && 'rum-icon-text',
          rating,
          canOpenDetail && 'rum-link-text',
        ]}
        action={canOpenDetail ? this.handleOpenDetail : undefined}
        target={target}
      >
        {icon}
        <span
          class='rum-field-text'
          title={!spanName && placement !== 'column' ? text : undefined}
        >
          {text}
        </span>
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

/** 为需要特殊呈现的字段补充图标、配色和备用文案。 */
const resolveFieldAppearance = (fieldName: string, value: unknown) => {
  switch (fieldName) {
    case SPAN_TYPE_FIELD: {
      const meta = SPAN_TYPE_META[String(value)];
      return {
        text: meta?.label,
        icon: meta?.icon ? (
          <img
            class='span-type-icon'
            alt=''
            src={meta.icon}
          />
        ) : meta?.fontIcon ? (
          <i
            class={`${meta.fontIcon} span-type-font-icon`}
            aria-hidden='true'
          />
        ) : null,
      };
    }
    case 'kind': {
      const meta = SPAN_KIND_MAPS[Number(value)];
      const icon = meta?.prefixIcon;
      return {
        text: meta?.alias,
        icon:
          typeof icon === 'function' ? (icon as () => VNodeChild)() : icon ? <i class={`prefix-icon ${icon}`} /> : null,
      };
    }
    case 'attributes.outcome.type': {
      const meta = RUM_OUTCOME_TYPE_MAP[String(value)];
      return {
        text: meta?.label,
        icon: meta ? (
          <i
            class={`prefix-icon ${meta.icon}`}
            aria-hidden='true'
          />
        ) : null,
      };
    }
    case 'attributes.resource.cache.hit':
      return value === true || value === 'true'
        ? {
            text: 'HIT',
            icon: (
              <i
                class='icon-monitor icon-mc-check-small'
                aria-hidden='true'
              />
            ),
          }
        : {};
    case 'status.code': {
      const config = RUM_STATUS_CODE_MAP[Number(value)];
      return config
        ? { text: config.alias, style: { color: config.tagColor, backgroundColor: config.tagBgColor } }
        : {};
    }
    case 'attributes.http.response.status_code': {
      const config = RUM_HTTP_STATUS_CODE_MAP[Math.floor(Number(value) / 100)];
      return config ? { style: { color: config.tagColor, backgroundColor: config.tagBgColor } } : {};
    }
    default:
      return {};
  }
};
