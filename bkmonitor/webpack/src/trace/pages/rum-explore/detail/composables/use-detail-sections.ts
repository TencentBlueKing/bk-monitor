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
import { computed, unref } from 'vue';
import type { MaybeRef } from 'vue';

import {
  CARDS_PER_ROW,
  RATING_FALLBACK_META,
  RATING_META,
  SECTION_TITLE_MAP,
  VITAL_METRIC_META,
  WATERFALL_FALLBACK_COLORS,
  WATERFALL_MERGED_PHASES,
  WATERFALL_PHASE_COLOR,
  WATERFALL_TTFB_MARKER_KEY,
} from '../constants';
import { getCardDescriptor, itemToCard } from '../registry/card-registry';
import { getSpanTypeDetailConfig } from '../registry/span-type-registry';
import { RumSectionTypeEnum } from '../typings';
import { formatDuration } from '@/components/trace-view/utils/date';

import type { IRumExtraCardBuilder } from '../registry/span-type-registry';
import type {
  IRumCardResolveCtx,
  IRumDetailSection,
  IRumDetailSectionVM,
  IRumRatingBarData,
  IRumRatingBarVM,
  IRumRatingSegmentVM,
  IRumRecordDetail,
  IRumRelatedData,
  IRumSummaryCardVM,
  IRumTtfbBreakdownVM,
  IRumWaterfallData,
  IRumWaterfallVM,
} from '../typings';

const t = (text: string) => window.i18n.t(text) as string;

/** 请求时序区块的 TTFB 口径说明 */
const TTFB_TIP =
  'TTFB 表示从请求发出到收到响应首字节的时间，包含请求传输、服务端处理和排队时间；仅凭浏览器时序不能直接判定服务端处理，需结合 Trace 或 Server-Timing。';

/**
 * @description 区块视图模型：接口区块归一化 + 按 span 类型注册的扩展卡片 / 扩展区块
 *
 * 渲染层只消费返回的 IRumDetailSectionVM[]，新增 span 类型或展示形态都不需要改这里。
 */
export function useDetailSections(
  detail: MaybeRef<IRumRecordDetail | null>,
  spanType: MaybeRef<string>,
  related: MaybeRef<IRumRelatedData>,
  baseCtx: MaybeRef<IRumCardResolveCtx>,
  relatedLoading: MaybeRef<boolean>
) {
  const sectionVMs = computed<IRumDetailSectionVM[]>(() => {
    const data = unref(detail);
    if (!data) return [];
    const type = unref(spanType);
    const ctx: IRumCardResolveCtx = { ...unref(baseCtx), originData: data.origin_data || {}, related: unref(related) };
    const { extraCards = {}, extraSections = [] } = getSpanTypeDetailConfig(type);
    const isRelatedLoading = unref(relatedLoading);
    const buildExtraCards = (builders: IRumExtraCardBuilder[], keyPrefix: string) =>
      builders
        .map((build, index) => {
          const card = build(ctx);
          return card ? { ...card, key: `${keyPrefix}_${index}` } : null;
        })
        .filter(Boolean) as IRumSummaryCardVM[];

    const vms: IRumDetailSectionVM[] = (data?.sections || []).map(section => {
      const base: IRumDetailSectionVM = {
        key: section.key,
        type: section.type,
        title: SECTION_TITLE_MAP[section.key] || '',
      };
      switch (section.type) {
        case RumSectionTypeEnum.SUMMARY_CARDS: {
          const cards = buildSummaryCards(section, type, ctx);
          /** 追加卡片依赖关联数据，未就绪时先展示占位值，不把整个区块挡在 loading 后面 */
          const extras = extraCards[section.key]
            ? buildExtraCards(extraCards[section.key], `${section.key}_extra`)
            : [];
          return { ...base, cardRows: chunkCards([...cards, ...extras]) };
        }
        case RumSectionTypeEnum.WATERFALL: {
          const waterfallData = (section.data || { phases: [], unit: 'ms' }) as IRumWaterfallData;
          const waterfall = buildWaterfall(waterfallData);
          /** 含等待首字节阶段时补一条口径说明，避免把 TTFB 直接当作服务端处理耗时 */
          const hasFirstByte = waterfallData.phases?.some(phase => phase.key === 'first_byte');
          return {
            ...base,
            waterfall,
            subTitle: waterfallData.total_duration
              ? `${t('总耗时')}：${formatDuration(Number(waterfallData.total_duration) || 0, '', 3, waterfallData.unit || 'us').replace(/ /g, '')}`
              : '',
            tip: hasFirstByte ? t(TTFB_TIP) : '',
            spanType: type,
          };
        }
        case RumSectionTypeEnum.RATING_BAR:
          return { ...base, ratingBar: buildRatingBar(section.data as IRumRatingBarData) };
        default:
          return base;
      }
    });

    for (const extra of extraSections) {
      const base: IRumDetailSectionVM = {
        key: extra.key,
        type: extra.type,
        title: SECTION_TITLE_MAP[extra.key] || '',
        loading: isRelatedLoading,
      };
      if (extra.type === RumSectionTypeEnum.KEY_VALUE_LIST) {
        const keyValues = extra.keyValues?.(ctx) ?? [];
        if (!keyValues.length && !isRelatedLoading) continue;
        vms.push({ ...base, keyValues });
        continue;
      }
      const cards = extra.cards ? buildExtraCards(extra.cards, extra.key) : [];
      if (!cards.length && !isRelatedLoading) continue;
      vms.push({ ...base, cardRows: chunkCards(cards) });
    }

    return vms;
  });

  return { sectionVMs };
}

/**
 * @description 评级条区块：按 rating_config 的阈值切分等宽分段，并算出指标值在整条上的落点
 */
function buildRatingBar(data: IRumRatingBarData): IRumRatingBarVM {
  const metric = String(data['attributes.vital.metric'] || '').toLowerCase();
  const value = Number(data['attributes.vital.value'] ?? 0);
  const configs = data['display.rating_config'] || [];
  const meta = VITAL_METRIC_META[metric];
  const unit = meta?.unit ?? 'ms';
  const segments: IRumRatingSegmentVM[] = [];
  let thumbPercent = 0;
  /** 指标值可能恰好落在 0%，不能用 thumbPercent 自身判断是否已定位 */
  let thumbResolved = false;
  let hitRating = configs[configs.length - 1]?.rating ?? '';

  let lower = 0;
  for (const [index, config] of configs.entries()) {
    const ratingMeta = RATING_META[config.rating] || RATING_FALLBACK_META;
    const upper = config.value;
    const isLast = index === configs.length - 1;
    segments.push({
      rating: config.rating,
      color: ratingMeta.barColor,
      label: isLast
        ? `${config.alias || ratingMeta.alias} > ${lower}${unit}`
        : `${config.alias || ratingMeta.alias} ≦ ${upper}${unit}`,
      threshold: isLast ? '' : `${upper}${unit}`,
    });
    /** 落在本段内时按段内比例定位指针；最后一段无上界，按前一段阈值作为虚拟段宽 */
    if (!thumbResolved && (isLast || value <= upper)) {
      const span = isLast ? Math.max(lower, 1) : Math.max(upper - lower, 1);
      const ratio = Math.min(Math.max((value - lower) / span, 0), 1);
      thumbPercent = ((index + ratio) / configs.length) * 100;
      hitRating = config.rating;
      thumbResolved = true;
    }
    lower = upper ?? lower;
  }

  const hitMeta = RATING_META[hitRating] || RATING_FALLBACK_META;
  return {
    metricLabel: meta?.label || metric.toUpperCase(),
    valueText: unit ? `${value.toLocaleString('en-US')} ${unit}` : String(value),
    rating: hitRating,
    ratingAlias: hitMeta.alias,
    segments,
    thumbPercent,
  };
}

/**
 * @description 统计卡片区块：data（字段分组）走描述符注册表，items（平铺字段）走通用映射
 */
function buildSummaryCards(section: IRumDetailSection, spanType: string, ctx: IRumCardResolveCtx) {
  if (section.items?.length) {
    return section.items.map(item => itemToCard(item, ctx));
  }
  const data = (section.data ?? {}) as Record<string, Record<string, unknown>>;
  const cards: IRumSummaryCardVM[] = [];
  for (const [groupKey, groupData] of Object.entries(data)) {
    const descriptor = getCardDescriptor(spanType, section.key, groupKey);
    for (const [index, card] of descriptor(groupData, ctx).entries()) {
      cards.push({ ...card, key: `${groupKey}_${index}` });
    }
  }
  return cards;
}

/**
 * @description TTFB 分解：把结束时间不晚于 TTFB 时间点的阶段（浏览器准备 / DNS / TCP / TLS / 等待首字节）作为分摊
 * TTFB 的子项，给出子项合计与 TTFB 主值的差值
 *
 * 后端没返回 TTFB 时间点标记、或没有落在 TTFB 之前的阶段时不返回，UI 不展示该说明。
 */
function buildTtfbBreakdown(data: IRumWaterfallData): IRumTtfbBreakdownVM | undefined {
  const unit = data.unit || 'us';
  const ttfb = (data.markers || []).find(marker => marker.key === WATERFALL_TTFB_MARKER_KEY);
  const ttfbValue = Number(ttfb?.value);
  if (!Number.isFinite(ttfbValue)) return undefined;
  const items = (data.phases || []).filter(phase => phase.start + phase.duration <= ttfbValue);
  if (!items.length) return undefined;
  const itemsTotal = items.reduce((sum, phase) => sum + (Number(phase.duration) || 0), 0);
  return {
    itemsTotalText: formatDuration(itemsTotal, '', 3, unit).replace(/ /g, ''),
    diffText: formatDuration(Math.abs(ttfbValue - itemsTotal), '', 3, unit).replace(/ /g, ''),
  };
}

/**
 * @description 瀑布图区块：把绝对时序换算成百分比布局
 *
 * DNS / TCP / TLS 耗时为 0 时说明连接被复用，这三段合并成一条说明线而不单独占行。
 */
function buildWaterfall(data: IRumWaterfallData): IRumWaterfallVM {
  const phases = data.phases || [];
  const total =
    data.total_duration || phases.reduce((max, phase) => Math.max(max, phase.start + phase.duration), 0) || 1;
  const mergedNames: string[] = [];
  const rows = phases
    .filter(phase => {
      const mergedName = WATERFALL_MERGED_PHASES[phase.key];
      if (mergedName && phase.duration <= 0) {
        mergedNames.push(mergedName);
        return false;
      }
      return true;
    })
    .map((phase, index) => ({
      key: phase.key,
      label: phase.alias || phase.key,
      durationText: formatDuration(Number(phase.duration) || 0, '', 3, data.unit || 'us').replace(/ /g, ''),
      startPercent: Math.min((phase.start / total) * 100, 100),
      durationPercent: Math.max(Math.min((phase.duration / total) * 100, 100), phase.duration > 0 ? 1 : 0),
      color: WATERFALL_PHASE_COLOR[phase.key] || WATERFALL_FALLBACK_COLORS[index % WATERFALL_FALLBACK_COLORS.length],
    }));
  return {
    rows,
    mergedNames,
    ttfbBreakdown: buildTtfbBreakdown(data),
    markers: (data.markers || []).map(marker => ({
      key: marker.key,
      label: marker.field_name || marker.key,
      percent: Math.min((marker.value / total) * 100, 100),
      durationText: formatDuration(Number(marker.value) || 0, '', 3, data.unit || 'us').replace(/ /g, ''),
    })),
  };
}

/** 把卡片列表按每行固定张数切行 */
function chunkCards(cards: IRumSummaryCardVM[]): IRumSummaryCardVM[][] {
  const rows: IRumSummaryCardVM[][] = [];
  for (let i = 0; i < cards.length; i += CARDS_PER_ROW) {
    rows.push(cards.slice(i, i + CARDS_PER_ROW));
  }
  return rows;
}
