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

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import {
  RUM_HTTP_STATUS_CODE_MAP,
  RUM_OUTCOME_TYPE_MAP,
  RUM_STATUS_CODE_MAP,
  RumFieldDisplayEnum,
  SPAN_KIND_MAPS,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../../constants';
import { formatUnitValue } from '../../../utils';
import { BaseScenario } from './base-scenario';

import type { IUsePopoverTools } from '../../../../alarm-center/components/alarm-table/hooks/use-popover';
import type { IRumSpanRecord } from '../../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';
import type { TippyContent } from 'vue-tippy';

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
    /**
     * span_name 列：蓝色链接样式，点击把值加为检索条件，hover 展示 span / trace 信息 tooltip。
     * 渲染由 cellRenderer 全权接管，不再声明 renderType（两者互斥，见 BaseScenario.resolveColumnConfig）。
     */
    span_name: {
      cellRenderer: (row, column, renderCtx) => this.renderSpanNameCell(row, column, renderCtx),
    },
    /** kind 列：Span 调用类型（图标 + 类型名，展示语义与 trace 检索 kind 列一致） */
    kind: {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: row => this.getSpanKindRenderValue(row.kind),
    },
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
    /** events.attributes.exception.type 列：异常类型（图标 + 异常类型） */
    'events.attributes.exception.type': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getExceptionTypeRenderValue(row['events.attributes.exception.type']),
    },
    /** attributes.outcome.type 列：结果状态（图标 + 状态文案） */
    'attributes.outcome.type': {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: row => this.getOutcomeTypeRenderValue(row['attributes.outcome.type']),
    },
  };

  constructor(
    protected readonly context: {
      /** span_name 列 hover 展示详情信息的 popover 工具 */
      hoverPopoverTools: IUsePopoverTools;
      /** 点击链接类单元格，把值加为检索条件 */
      onCellFilter: (colKey: string, value: string) => void;
    } & BaseScenario['context']
  ) {
    super(context);
  }

  /**
   * @description 场景元数据推导：根据 field_display_type / field_unit 派发对应渲染类型
   * - datetime → 时间列
   * - duration → 耗时列（透传原始单位供 formatDuration 量纲换算）
   * - 其余带 field_unit 的字段 → 按单位自适应换算展示（复用图表的 getValueFormat 量纲表）
   */
  protected buildBaseline(colKey: string): Partial<BaseTableColumn> {
    const field = get(this.context.fieldMap).get(colKey);
    /**
     * 指标值列（attributes.vital.value）特殊处理。
     * 该列元数据是伪单位 vital（display_type=duration），含义为「单位由每行是哪一个 Web Vitals 指标决定」：
     * Span 视角下一行即一条 vital span，只带一个指标，指标名在 attributes.vital.metric，数值统一存在本列：
     *   - lcp / fcp / inp / ttfb → 毫秒耗时，按 ms 换算展示（如 2.5s、180ms）
     *   - cls → 0~1 的无量纲分数，原样展示（不能拼时间单位）
     * 故不能交给下面按整列固定 durationUnit 的 DURATION 渲染器，改为按行取值；
     * 不指定 renderType，格式化后的字符串走默认 TEXT 渲染。
     */
    if (field?.field_unit === 'vital') {
      return {
        getRenderValue: row => {
          const value = row[colKey];
          if (value === null || value === undefined || value === '') return '';
          /** CLS 分数与不可转数值的脏数据都原样输出，避免拼出无意义的时间单位 */
          if (String(row['attributes.vital.metric']).toLowerCase() === 'cls' || !Number.isFinite(Number(value))) {
            return String(value);
          }
          return formatDuration(Number(value), '', 2, 'ms');
        },
      };
    }
    switch (field?.field_display_type) {
      case RumFieldDisplayEnum.DATETIME:
        return { renderType: ExploreTableColumnTypeEnum.TIME };
      case RumFieldDisplayEnum.DURATION:
        return {
          renderType: ExploreTableColumnTypeEnum.DURATION,
          cellSpecificProps: { durationUnit: field?.field_unit as 'ms' | 'us' },
        };
      default: {
        const unit = field?.field_unit;
        if (!unit) return {};
        return { getRenderValue: row => formatUnitValue(row[colKey], unit) };
      }
    }
  }

  // ----------------- Span 场景私有逻辑方法 -----------------

  /**
   * @description span_name 列单元格渲染：保留 CLICK 列「点击加为检索条件」的结构与交互（含右键条件菜单），
   *              并在 hover 时展示 span 名称 / Span ID / 所属 Trace ID 信息
   * @param {IRumSpanRecord} row 当前行数据
   * @param {BaseTableColumn} column 当前列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderSpanNameCell(row: IRumSpanRecord, column: BaseTableColumn, renderCtx: TableCellRenderContext) {
    const alias = renderCtx.getTableCellRenderValue(row, column);
    if (alias === null || alias === undefined || alias === '') {
      return renderCtx.cellRenderHandleMap[ExploreTableColumnTypeEnum.TEXT]?.(row, column, renderCtx);
    }
    /**
     * 省略号不使用 renderCtx.isEnabledCellEllipsis：该类是表格溢出 tip 的事件委托类，
     * 挂上后长文本 hover 会同时弹出「完整文本 tip」与本列的 span / trace 信息 tooltip（后者已含完整名称）。
     * 这里仅做纯 CSS 省略（与告警中心 alert_name 列 ellipsis-text 的处理一致）。
     */
    return (
      <div class='explore-col explore-click-col'>
        <div class='span-name-ellipsis'>
          <span
            class='explore-click-text'
            data-col-id={column.colKey}
            data-row-id={renderCtx.getRowId(row)}
            onClick={() => this.context.onCellFilter(column.colKey, String(row?.span_name ?? ''))}
            onMouseenter={e => this.handleSpanNameHover(e, row)}
            onMouseleave={this.context.hoverPopoverTools.clearPopoverTimer}
          >
            {alias}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description span_name 列 hover 事件：展示 span 名称 / Span ID 信息
   *              （所属 Trace ID 待 Trace 关联能力上线后补充）
   * @param {MouseEvent} e 鼠标事件
   * @param {IRumSpanRecord} row 当前行数据
   */
  private handleSpanNameHover(e: MouseEvent, row: IRumSpanRecord) {
    /** 标签文案与表头同源（fieldMap.alias），避免「表头 Span 名称 / tooltip Span Name」两套叫法；字段不在 fieldMap（未开放为列）时回落前端文案 */
    const label = (colKey: string, fallback: string) => get(this.context.fieldMap).get(colKey)?.alias ?? fallback;
    const content = (
      <div class='span-name-popover-container'>
        <div class='span-name-popover-item'>
          <span class='span-name-popover-item-label'>{label('span_name', window.i18n.t('Span 名称'))}：</span>
          <span class='span-name-popover-item-value'>{row?.span_name || '--'}</span>
        </div>
        <div class='span-name-popover-item'>
          <span class='span-name-popover-item-label'>{label('span_id', 'Span ID')}：</span>
          <span class='span-name-popover-item-value'>{row?.span_id || '--'}</span>
        </div>
        {/* 所属 Trace ID 行：Trace 关联能力本期未做，暂不展示，下期开放后放开
        <div class='span-name-popover-item'>
          <span class='span-name-popover-item-label'>{window.i18n.t('所属 Trace ID')}：</span>
          {row?.trace_id ? (
            <a
              class='span-name-popover-item-value is-link'
              href={this.getTraceQueryUrl(row)}
              rel='noopener noreferrer'
              target='_blank'
            >
              <span>{row.trace_id}</span>
              <i class='icon-monitor icon-mc-goto' />
            </a>
          ) : (
            <span class='span-name-popover-item-value'>--</span>
          )}
        </div>
        */}
      </div>
    ) as unknown as TippyContent;
    this.context.hoverPopoverTools.showPopover(e, content, {
      theme: 'rum-span-name-popover max-width-40vw text-wrap padding-0',
    });
  }

  /**
   * @description 所属 Trace 检索页链接：按 trace_id 精确查询并展开 trace 详情侧栏
   *              （链接规则与 trace 检索 span 详情的「所属 Trace」一致，应用 / 业务取行数据自带的 app_name / bk_biz_id）
   *              Trace 关联能力本期未做，暂不展示，下期开放后连同 tooltip 中的所属 Trace ID 行一起放开
   * @param {IRumSpanRecord} row 当前行数据
   * @returns {string} Trace 检索页链接
   */
  // private getTraceQueryUrl(row: IRumSpanRecord) {
  //   const hash = `#/trace/home?app_name=${row?.app_name}&sceneMode=trace&trace_id=${row?.trace_id}`;
  //   const url = new URL(location.href.replace(location.hash, hash));
  //   /** 监控 URL 约定：bizId 位于 hash 之前的 search 上（?bizId=xx#/trace/home） */
  //   if (row?.bk_biz_id != null) {
  //     url.searchParams.set('bizId', String(row.bk_biz_id));
  //   }
  //   return url.toString();
  // }

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
   * @description Span 调用类型列渲染值：类型图标 + 类型别名（复用 trace 检索 kind 列配置）
   * @param {unknown} value 当前行 kind 值
   */
  private getSpanKindRenderValue(value: unknown) {
    if (value === null || value === undefined || value === '') return { alias: '', prefixIcon: '' };
    const meta = SPAN_KIND_MAPS[Number(value)];
    /** 未命中枚举时回退展示后台枚举别名或原始值，不渲染图标 */
    if (!meta) return { alias: this.getFieldOptionAlias('kind', value) ?? String(value), prefixIcon: '' };
    return { ...meta };
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
   * @description 结果状态列渲染值：状态图标 + 状态文案（复用内置前置图标渲染，图标配色见 span-table-theme.scss）
   * @param {unknown} value 当前行结果状态值
   */
  private getOutcomeTypeRenderValue(value: unknown) {
    const meta = RUM_OUTCOME_TYPE_MAP[value as string];
    /** 未命中枚举时回退展示原始值，不渲染图标 */
    if (!meta) return { alias: value ? String(value) : '', prefixIcon: '' };
    /** 后台字段元数据声明了枚举别名时优先取后台映射值，兜底用本地枚举文案 */
    const alias = this.getFieldOptionAlias('attributes.outcome.type', value);
    return { alias: alias || meta.label, prefixIcon: meta.icon };
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
