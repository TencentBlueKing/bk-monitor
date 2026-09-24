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
import { SectionKeyEnum } from '../constants';
import { getActionRelated, getErrorRelated, getLongTaskRelated, getViewRelated } from '../services';
import { RumCardToneEnum, RumSectionTypeEnum } from '../typings';
import { EMPTY_TEXT, formatCount } from './card-registry';

import type { IRumFilter, IRumTimeRange, RumModeType } from '../../typings';
import type {
  IRumCardResolveCtx,
  IRumDetailContext,
  IRumRecordDetail,
  IRumRelatedData,
  IRumSparklinePoint,
  IRumSummaryCardVM,
  RumSectionType,
} from '../typings';

const t = (text: string) => window.i18n.t(text) as string;

/** 额外卡片的构造器，返回 null 表示不渲染该卡片 */
export type IRumExtraCardBuilder = (ctx: IRumCardResolveCtx) => null | Omit<IRumSummaryCardVM, 'key'>;

/**
 * span 类型的详情扩展配置。
 * 新增类型时在 SPAN_TYPE_DETAIL_CONFIG 里补一条即可，composables 与渲染组件均无需改动。
 */
export interface IRumSpanTypeDetailConfig {
  /** 追加到指定区块尾部的卡片，key 为区块标识 */
  extraCards?: Record<string, IRumExtraCardBuilder[]>;
  /** 追加在接口区块之后的前端扩展区块 */
  extraSections?: IRumExtraSection[];
  /** 关联数据加载器，结果注入卡片推导上下文的 related */
  loadRelated?: (
    context: IRumDetailContext,
    mode: RumModeType,
    detail: IRumRecordDetail,
    timeRange: IRumTimeRange
  ) => Promise<IRumRelatedData | null>;
}

/** 接口未覆盖、由前端按 span 类型补充的区块 */
interface IRumExtraSection {
  /** summary_cards 区块的卡片构造器 */
  cards?: IRumExtraCardBuilder[];
  key: string;
  type: RumSectionType;
  /** key_value_list 区块的行构造器 */
  keyValues?: (ctx: IRumCardResolveCtx) => Array<{ label: string; value: string }>;
}

/** 计数类卡片：有值时以蓝色可点击样式呈现，0 或缺失时为普通文本 */
const countCard =
  (config: Omit<IRumSummaryCardVM, 'key' | 'value'>, relatedKey: keyof IRumRelatedData): IRumExtraCardBuilder =>
  ctx => {
    const count = Number(ctx.related[relatedKey] ?? Number.NaN);
    if (!Number.isFinite(count)) return { ...config, value: EMPTY_TEXT };
    return {
      value: formatCount(count),
      tone: count > 0 ? RumCardToneEnum.LINK : RumCardToneEnum.DEFAULT,
      ...config,
    };
  };

/** 从 Error 详情的关键信息里还原「同一个错误」的过滤条件 */
function buildErrorFilters(detail: IRumRecordDetail): IRumFilter[] {
  const keyInfo = detail.sections?.find(section => section.key === SectionKeyEnum.KEY_INFO);
  const data = (keyInfo?.data ?? {}) as Record<string, Record<string, unknown>>;
  const source = data.source ?? {};
  const errorType = data.error_type ?? {};
  const fields = [
    'attributes.code.filepath',
    'attributes.code.lineno',
    'attributes.code.column',
    'events.attributes.exception.type',
  ];
  const merged = { ...source, ...errorType };
  return fields
    .filter(field => merged[field] !== undefined && merged[field] !== null && merged[field] !== '')
    .map(field => ({ key: field, operator: 'equal', value: [String(merged[field])] }));
}

export const SPAN_TYPE_DETAIL_CONFIG: Record<string, IRumSpanTypeDetailConfig> = {
  action: {
    extraCards: {
      [SectionKeyEnum.KEY_INFO]: [
        // TODO(2026-09-21): 有值时本应可点击跳转「链路上下文」tab，该 tab 本期未实现，暂按普通样式渲染
        countCard({ label: t('触发请求数'), tone: RumCardToneEnum.DEFAULT }, 'resourceCount'),
        countCard({ label: t('错误数'), tone: RumCardToneEnum.DEFAULT }, 'errorCount'),
        countCard({ label: t('Long Tasks 数'), tone: RumCardToneEnum.DEFAULT }, 'longTaskCount'),
      ],
    },
    loadRelated: (context, mode) => getActionRelated(context, mode),
  },

  long_task: {
    loadRelated: (context, mode, detail) => {
      const keyInfo = detail.sections?.find(section => section.key === SectionKeyEnum.KEY_INFO);
      const data = (keyInfo?.data ?? {}) as Record<string, Record<string, unknown>>;
      const actionId = String(data.action?.['attributes.action.id'] ?? '');
      return getLongTaskRelated(context, mode, actionId);
    },
  },

  error: {
    extraCards: {
      [SectionKeyEnum.KEY_INFO]: [
        countCard(
          { label: t('影响用户'), tone: RumCardToneEnum.DEFAULT, footer: [{ text: t('当前查询范围 · 相同错误信息') }] },
          'userCount'
        ),
        countCard(
          { label: t('发生次数'), tone: RumCardToneEnum.DEFAULT, footer: [{ text: t('当前查询范围') }] },
          'occurrenceCount'
        ),
      ],
    },
    extraSections: [
      {
        key: SectionKeyEnum.IMPACT,
        type: RumSectionTypeEnum.SUMMARY_CARDS,
        cards: [
          ctx => {
            const count = Number(ctx.related.userCount ?? Number.NaN);
            const growth = Number(ctx.related.userGrowthRate ?? 0);
            return {
              label: t('影响用户数'),
              value: Number.isFinite(count) ? formatCount(count) : EMPTY_TEXT,
              /** 环比为 0 时不展示涨跌标签 */
              growthRate: growth
                ? {
                    text: `${growth > 0 ? '+' : ''}${growth}%`,
                    tone: growth > 0 ? RumCardToneEnum.DANGER : RumCardToneEnum.SUCCESS,
                  }
                : undefined,
              footer: [{ text: t('当前查询范围 · 独立用户数') }],
            };
          },
          countCard(
            { label: t('影响会话数'), footer: [{ text: t('当前查询范围 · 独立 session_id 数') }] },
            'sessionCount'
          ),
          ctx => {
            /** 关联数据已是 { time, value } 结构，直接透传给 sparkline；无趋势数据时整张卡片不渲染 */
            const trend = (ctx.related.trend ?? []) as IRumSparklinePoint[];
            if (!trend.length) return null;
            return {
              label: t('24 小时趋势'),
              value: '',
              sparkline: trend,
              footer: [{ text: t('每 1h 一桶') }],
            };
          },
        ],
      },
      {
        key: SectionKeyEnum.VERSION,
        type: RumSectionTypeEnum.KEY_VALUE_LIST,
        keyValues: ctx => {
          const version = ctx.related.version as undefined | { current: string; first: string; note: string };
          if (!version) return [];
          return [
            { label: t('当前版本'), value: version.current },
            { label: t('首次出现版本'), value: version.first },
            { label: t('说明'), value: version.note },
          ];
        },
      },
    ],
    loadRelated: (context, mode, detail, timeRange) =>
      getErrorRelated(context, mode, buildErrorFilters(detail), timeRange),
  },

  view: {
    extraCards: {
      [SectionKeyEnum.KEY_INFO]: [
        countCard({ label: t('请求'), tone: 'link', cardCls: 'view-extra-card' }, 'resourceCount'),
        countCard({ label: t('错误'), tone: 'danger', cardCls: 'view-extra-card' }, 'errorCount'),
        countCard({ label: 'Span', tone: 'link', cardCls: 'view-extra-card' }, 'spanCount'),
      ],
    },
    loadRelated: (context, mode, detail) => {
      return getViewRelated(context, mode, detail);
    },
  },
};

/** @description 取 span 类型的详情扩展配置，未登记的类型只渲染接口返回的区块 */
export function getSpanTypeDetailConfig(spanType: string): IRumSpanTypeDetailConfig {
  return SPAN_TYPE_DETAIL_CONFIG[spanType] ?? {};
}
