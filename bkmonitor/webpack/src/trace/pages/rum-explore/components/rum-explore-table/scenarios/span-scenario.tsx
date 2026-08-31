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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { get } from '@vueuse/core';
import { hexToRgba } from 'monitor-common/utils/colorHelpers';

import {
  type BaseTableColumn,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import {
  RUM_HTTP_STATUS_CODE_MAP,
  RUM_LINK_FIELDS,
  RUM_STATUS_CODE_MAP,
  RumFieldDisplayEnum,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../../constants';
import { BaseScenario } from './base-scenario';

import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * @class SpanScenario
 * @classdesc Span 检索场景：时间列、链接列、类型列、状态码列的渲染差异在 columnOverrides 中声明；
 *           耗时（单位=微秒）等基于字段元数据的渲染推导在 buildBaseline 中完成。
 * @extends BaseScenario
 */
export class SpanScenario extends BaseScenario {
  readonly privateClassName = 'span-table';
  readonly rowKey = 'span_id';
  protected columnOverrides: Record<string, BaseTableColumn> = {
    /** 链接列：点击把值加为检索条件 */
    ...Object.fromEntries(
      [...RUM_LINK_FIELDS].map((key): [string, BaseTableColumn] => [
        key,
        {
          renderType: ExploreTableColumnTypeEnum.CLICK,
          clickCallback: (row, _column, _event) => this.context.onCellFilter(key, `${row?.[key] ?? ''}`),
        },
      ])
    ),
    /** Span 类型列：类型图标 + 类型名 */
    [SPAN_TYPE_FIELD]: {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: row => this.getSpanTypeRenderValue(row[SPAN_TYPE_FIELD]),
    },
    /** status.code 列：按状态语义着色的 Tag */
    'status.code': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getStatusCodeRenderValue(row['status.code']),
    },
    'attributes.http.response.status_code': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getHttpStatusCodeRenderValue(row['attributes.http.response.status_code']),
    },
    /** attributes.http.request.method 列：统一灰色 Tag（不指定配色即用 tags 渲染的默认灰） */
    'attributes.http.request.method': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getHttpMethodRenderValue(row['attributes.http.request.method']),
    },
    /** attributes.resource.cache.hit 列：缓存命中（图标 + HIT / --） */
    'attributes.resource.cache.hit': {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: row => this.getCacheHitRenderValue(row['attributes.resource.cache.hit']),
    },
    'events.attributes.exception.type': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getExceptionTypeRenderValue(row['events.attributes.exception.type']),
    },
    // TODO： attributes.action.frustration.type 列渲染逻辑需和 设计确认
    // 'attributes.action.frustration.type': {
    //   renderType: ExploreTableColumnTypeEnum.TAGS,
    // },
  };

  constructor(
    protected readonly context: {
      /** 点击链接类单元格，把值加为检索条件 */
      onCellFilter: (colKey: string, value: string) => void;
    } & BaseScenario['context']
  ) {
    super(context);
  }

  /**
   * @description 场景元数据推导：根据 field_display_type 派发对应渲染类型
   * - datetime → 时间列
   * - duration → 耗时列（透传原始单位供 formatDuration 量纲换算）
   */
  protected buildBaseline(colKey: string): Partial<BaseTableColumn> {
    const field = get(this.context.fieldMap).get(colKey);
    switch (field?.field_display_type) {
      case RumFieldDisplayEnum.DATETIME:
        return { renderType: ExploreTableColumnTypeEnum.TIME };
      case RumFieldDisplayEnum.DURATION:
        return {
          renderType: ExploreTableColumnTypeEnum.DURATION,
          cellSpecificProps: { durationUnit: field?.field_unit as 'ms' | 'us' },
        };
      default:
        return {};
    }
  }

  // ----------------- Span 场景私有逻辑方法 -----------------

  /**
   * @description Span 类型列渲染值：类型图标 + 类型别名（复用内置前置图标渲染）
   * @param {unknown} value 当前行 Span 类型值
   */
  private getSpanTypeRenderValue(value: unknown) {
    const meta = SPAN_TYPE_META[value as string];
    return {
      alias: meta?.label || value,
      prefixIcon: meta?.icon
        ? () =>
            (
              <img
                class='span-type-icon'
                alt=''
                src={meta.icon}
              />
            ) as unknown as SlotReturnValue
        : '',
    };
  }

  /**
   * @description 状态码列渲染值：按状态语义着色的 Tag（复用内置 tags 渲染）
   * @param {unknown} value 当前行状态码值
   */
  private getStatusCodeRenderValue(value: number) {
    const status = RUM_STATUS_CODE_MAP[value];
    return status ? [{ ...status }] : [{ alias: value }];
  }

  /**
   * @description HTTP 状态码列渲染值：按百位分组着色的 Tag（复用内置 tags 渲染）
   * @param {unknown} value 当前行 HTTP 状态码值
   */
  private getHttpStatusCodeRenderValue(value: unknown) {
    const code = Number(value);
    if (!Number.isFinite(code)) return [];
    const config = RUM_HTTP_STATUS_CODE_MAP[Math.floor(code / 100)];
    return config ? [{ alias: String(value), ...config }] : [{ alias: value }];
  }

  /**
   * @description HTTP 方法列渲染值：统一灰色 Tag（复用内置 tags 渲染的默认配色，不做方法语义区分）
   * @param {unknown} value 当前行 HTTP 方法值
   */
  private getHttpMethodRenderValue(value: unknown) {
    return value ? [String(value)] : [];
  }

  /**
   * @description 缓存命中列渲染值：命中时显示勾选图标 + HIT 文本，未命中显示 --
   * @param {unknown} value 当前行缓存命中值（布尔值）
   */
  private getCacheHitRenderValue(value: unknown) {
    if (!value) return { alias: '', prefixIcon: '' };
    return {
      alias: 'HIT',
      prefixIcon: 'icon-monitor icon-mc-check-small',
    };
  }

  /**
   * @description 错误类型列渲染值：红色主题 Tag（无映射，原始字符串直接展示）
   * @param {unknown} value 当前行错误类型值（如 'TypeError'）
   */
  private getExceptionTypeRenderValue(value: unknown) {
    return value
      ? [
          {
            alias: String(value),
            tagBgColor: '#FDE7E7',
            tagColor: '#EA3636',
            tagHoverBgColor: hexToRgba('#FDE7E7', 0.8),
            tagHoverColor: hexToRgba('#EA3636', 0.8),
          },
        ]
      : [];
  }
}
