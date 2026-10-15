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
import dayjs from 'dayjs';
import { hexToRgba } from 'monitor-common/utils/colorHelpers';

import { SPAN_TYPE_META } from '../../constants';
import { matchRating } from '../composables/use-detail-sections';
import {
  RATING_FALLBACK_META,
  RATING_META,
  SectionKeyEnum,
  TIMELINE_CONTEXT_SIZE,
  TIMELINE_HEAD_SIZE,
  TIMELINE_REQUEST_RESOURCE_TYPES,
  TIMELINE_STATUS_CODE_COLOR,
  TIMELINE_STATUS_CODE_FALLBACK_COLOR,
  TIMELINE_TAG_BG_ALPHA,
  VITAL_METRIC_META,
} from '../constants';
import { getTimelineSpanTypeConfig } from '../registry/timeline-span-registry';
import { formatDuration } from '@/components/trace-view/utils/date';

import type {
  IRumTimelineClsVM,
  IRumTimelineItemVM,
  IRumTimelineNode,
  IRumTimelineRecord,
  IRumTimelineSpanVM,
  IRumTimelineViewVM,
} from '../typings';

/** 未登记类型的标签主色 */
const FALLBACK_TAG_COLOR = '#8F9FBD';

/** 构造链路上下文列表项所需的上下文 */
export interface IRumTimelineBuildCtx {
  /** 当前详情 Span 的祖先链（含自身），用于定位每一层的折叠锚点 */
  currentPath: Set<string>;
  currentSpanId: string;
  /** 已展开的折叠段 */
  expandedFolds: Set<string>;
  /** 已展开子节点的 Span */
  expandedNodes: Set<string>;
  recordMap: Map<string, IRumTimelineRecord>;
}

const isValidNumber = (value: unknown) => value !== null && value !== undefined && Number.isFinite(Number(value));

const getAttributes = (record?: IRumTimelineRecord): Record<string, any> => record?.origin_data?.attributes ?? {};

const getSectionData = (record: IRumTimelineRecord | undefined, key: string) =>
  record?.sections?.find(section => section.key === key)?.data as Record<string, any> | undefined;

/** @description 按 span_id 索引节点详情 */
export function buildRecordMap(records: IRumTimelineRecord[] = []) {
  return new Map(records.map(record => [record.span_id, record]));
}

/**
 * @description 把一层子节点翻译成 Span 行与折叠行混排的列表，已展开的节点递归拼接其子节点
 *
 * 折叠规则：该层有当前 Span（或其祖先）时以它为锚点，前后各保留 TIMELINE_CONTEXT_SIZE 条；
 * 没有锚点时从头保留 TIMELINE_HEAD_SIZE 条。锚点前、后的剩余节点各折叠成一段，展开后整段可见。
 * @param parentKey 父节点标识，用于生成该层折叠段的唯一 key
 */
export function buildTimelineItems(
  nodes: IRumTimelineNode[] | undefined,
  ctx: IRumTimelineBuildCtx,
  level = 0,
  parentKey = 'root'
): IRumTimelineItemVM[] {
  if (!nodes?.length) return [];
  const anchorIndex = nodes.findIndex(node => ctx.currentPath.has(node.span_id));
  const [start, end] =
    anchorIndex >= 0
      ? [
          Math.max(anchorIndex - TIMELINE_CONTEXT_SIZE, 0),
          Math.min(anchorIndex + TIMELINE_CONTEXT_SIZE + 1, nodes.length),
        ]
      : [0, Math.min(TIMELINE_HEAD_SIZE, nodes.length)];
  const items: IRumTimelineItemVM[] = [];

  const pushNodes = (list: IRumTimelineNode[]) => {
    for (const node of list) {
      const span = buildSpanVM(node, ctx, level);
      items.push({ kind: 'span', data: span });
      if (span.expanded) items.push(...buildTimelineItems(node.children, ctx, level + 1, node.span_id));
    }
  };

  const pushSegment = (list: IRumTimelineNode[], key: string) => {
    if (!list.length) return;
    if (ctx.expandedFolds.has(key)) {
      pushNodes(list);
      return;
    }
    items.push({ kind: 'fold', data: { key, count: list.length, level } });
  };

  pushSegment(nodes.slice(0, start), `${parentKey}:before`);
  pushNodes(nodes.slice(start, end));
  pushSegment(nodes.slice(end), `${parentKey}:after`);
  return items;
}

/**
 * @description View 头部视图模型，取值口径见 timeline 接口协议 2.12.3
 * @param formatField 字段格式化函数，路由类型取 view_config 里的枚举别名
 */
export function buildViewVM(
  viewNode: IRumTimelineNode,
  recordMap: Map<string, IRumTimelineRecord>,
  currentSpanId: string,
  formatField: (fieldName: string, value: unknown) => string
): IRumTimelineViewVM {
  const record = recordMap.get(viewNode.span_id);
  const attributes = getAttributes(record);
  const children = viewNode.children ?? [];
  const duration = getSectionData(record, SectionKeyEnum.KEY_INFO)?.duration?.['display.view.duration'];
  return {
    spanId: viewNode.span_id,
    title: record?.origin_data?.span_name || viewNode.span_id,
    isCurrent: viewNode.span_id === currentSpanId,
    loadingType: formatField('attributes.view.loading_type', attributes['view.loading_type']),
    cls: buildClsVM(getSectionData(record, SectionKeyEnum.WEB_VITALS)?.cls),
    requestCount: countSubtree(children, recordMap, item =>
      TIMELINE_REQUEST_RESOURCE_TYPES.has(getAttributes(item)['resource.type'])
    ),
    actionCount: children.filter(child => getAttributes(recordMap.get(child.span_id)).span_type === 'action').length,
    durationText: isValidNumber(duration) ? formatDuration(Number(duration), '', 2, 'ms') : '',
  };
}

/** @description 查找从顶层节点到目标 Span 的路径（含目标本身），找不到时返回空数组 */
export function findSpanPath(nodes: IRumTimelineNode[] = [], spanId: string): string[] {
  for (const node of nodes) {
    if (node.span_id === spanId) return [node.span_id];
    const subPath = findSpanPath(node.children, spanId);
    if (subPath.length) return [node.span_id, ...subPath];
  }
  return [];
}

function buildClsVM(data?: Record<string, any>): IRumTimelineClsVM | undefined {
  const rawValue = data?.['attributes.vital.value'];
  if (!data || !isValidNumber(rawValue)) return undefined;
  const value = Number(rawValue);
  const meta = RATING_META[matchRating(value, data['display.rating_config'] || [])] || RATING_FALLBACK_META;
  const label = VITAL_METRIC_META.cls.label;
  return {
    text: `CLS ${value}`,
    color: meta.color,
    tip: meta.alias ? `${label}：${meta.alias}` : label,
  };
}

function buildSpanVM(node: IRumTimelineNode, ctx: IRumTimelineBuildCtx, level: number): IRumTimelineSpanVM {
  const origin = ctx.recordMap.get(node.span_id)?.origin_data ?? {};
  const attributes: Record<string, unknown> = origin.attributes ?? {};
  const spanType = String(attributes.span_type ?? '');
  const meta = SPAN_TYPE_META[spanType];
  const config = getTimelineSpanTypeConfig(spanType);
  const statusCode = attributes['http.response.status_code'];
  const expandable = !!node.children?.length;
  return {
    spanId: node.span_id,
    spanType,
    level,
    title: origin.span_name || node.span_id,
    /** 开始时间以微秒存储，按毫秒交给 dayjs */
    timeText: isValidNumber(origin.start_time) ? dayjs.tz(Number(origin.start_time) / 1000).format('HH:mm:ss') : '--',
    durationText: isValidNumber(origin.elapsed_time) ? formatDuration(Number(origin.elapsed_time), '', 2, 'us') : '--',
    tag: {
      label: config.tagLabel?.(attributes) || meta?.label || spanType,
      icon: meta?.icon || '',
      bgColor: hexToRgba(meta?.color || FALLBACK_TAG_COLOR, TIMELINE_TAG_BG_ALPHA),
    },
    statusCode:
      config.showStatusCode && isValidNumber(statusCode)
        ? {
            text: String(statusCode),
            ...(TIMELINE_STATUS_CODE_COLOR[Math.floor(Number(statusCode) / 100)] ||
              TIMELINE_STATUS_CODE_FALLBACK_COLOR),
          }
        : undefined,
    traceId: origin.links?.[0]?.trace_id || '',
    isCurrent: node.span_id === ctx.currentSpanId,
    expandable,
    expanded: expandable && ctx.expandedNodes.has(node.span_id),
  };
}

/** 统计子树中满足条件的节点数 */
function countSubtree(
  nodes: IRumTimelineNode[],
  recordMap: Map<string, IRumTimelineRecord>,
  predicate: (record?: IRumTimelineRecord) => boolean
): number {
  return nodes.reduce(
    (sum, node) =>
      sum + (predicate(recordMap.get(node.span_id)) ? 1 : 0) + countSubtree(node.children ?? [], recordMap, predicate),
    0
  );
}
