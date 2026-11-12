import { computed, shallowRef, unref, watch } from 'vue';
import type { MaybeRef } from 'vue';

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
import { useI18n } from 'vue-i18n';

import { RumTimelineFilterCategoryEnum, RumTimelineSortEnum, TIMELINE_REQUEST_RESOURCE_TYPES } from '../constants';
import { getSessionTimeline, getViewTimeline } from '../services';
import { buildRecordMap, buildTimelineItems, buildViewVM, findSpanPath } from '../utils/timeline-transform';
import { formatDuration } from '@/components/trace-view/utils/date';

import type {
  IRumTimelineCardItemVM,
  IRumTimelineCardVM,
  IRumTimelineNode,
  IRumTimelineRecord,
  IRumTimelineResponse,
  RumTimelineFilterCategoryType,
  RumTimelineSortType,
} from '../typings';

/** 慢节点阈值：耗时超过 500ms（elapsed_time 以微秒存储） */
const SLOW_NODE_THRESHOLD_US = 500 * 1000;

/** 折叠中间 View 时首尾各自保留的卡片数 */
const COLLAPSE_EDGE_VIEW_COUNT = 2;

/** 星期文案，时间轴开始横幅使用，按 dayjs 的 day() 索引取值 */
const WEEKDAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

/** 类别筛选谓词，口径同 timeline 接口协议 2.12.3 */
const CATEGORY_PREDICATES: Record<
  Exclude<RumTimelineFilterCategoryType, typeof RumTimelineFilterCategoryEnum.ALL>,
  (record: IRumTimelineRecord | undefined) => boolean
> = {
  [RumTimelineFilterCategoryEnum.ACTION]: record =>
    String(record?.origin_data?.attributes?.span_type ?? '') === RumTimelineFilterCategoryEnum.ACTION,
  [RumTimelineFilterCategoryEnum.ERROR]: record => {
    const attributes: Record<string, unknown> = record?.origin_data?.attributes ?? {};
    return (
      String(attributes.span_type ?? '') === 'error' ||
      attributes.error === true ||
      attributes['outcome.type'] === 'error'
    );
  },
  [RumTimelineFilterCategoryEnum.SLOW_NODE]: record => {
    const elapsed = record?.origin_data?.elapsed_time;
    return elapsed !== null && elapsed !== undefined && Number(elapsed) > SLOW_NODE_THRESHOLD_US;
  },
  [RumTimelineFilterCategoryEnum.REQUEST]: record =>
    TIMELINE_REQUEST_RESOURCE_TYPES.has(record?.origin_data?.attributes?.['resource.type']),
  [RumTimelineFilterCategoryEnum.THIRD_PARTY]: record => {
    const attributes: Record<string, unknown> = record?.origin_data?.attributes ?? {};
    return (
      String(attributes.span_type ?? '') === 'resource' &&
      !TIMELINE_REQUEST_RESOURCE_TYPES.has(String(attributes['resource.type'] ?? ''))
    );
  },
};

interface IUseTraceContextOptions {
  /** tab 是否激活，未激活时不发请求 */
  active: MaybeRef<boolean>;
  appName: MaybeRef<string>;
  /** 当前详情的 span_id，决定高亮与折叠锚点；会话时间轴不传 */
  currentSpanId?: MaybeRef<string>;
  /** 数据维度：会话 ID 或 View ID，为空时不请求 */
  dimension: MaybeRef<string>;
  /** 取数维度类型：会话时间轴按 session_id 查询，链路上下文按 view_id 查询 */
  scope: 'session' | 'view';
  /** 字段格式化函数，来自 useDetailFormatter */
  formatField: (fieldName: string, value: unknown) => string;
}

/**
 * @description RUM 时间线：按会话或 View 拉取时间线并维护筛选、展开状态，产出可直接渲染的卡片列表
 *
 * 会话时间轴与链路上下文共用同一套产出：按 session_id 查询返回多个顶层 View（每个 View 一张卡片），
 * 按 view_id 查询只返回当前 View，差异只在传入的维度与 scope。
 * 同一维度下切换 Span 不重复请求，只重新定位高亮与折叠锚点；筛选生效时丢弃未命中的 View 卡片，
 * 并平铺展示命中项、自动展开其祖先。
 */
export function useTraceContext({
  active,
  appName,
  currentSpanId,
  dimension,
  scope,
  formatField,
}: IUseTraceContextOptions) {
  const { t } = useI18n();

  const timeline = shallowRef<IRumTimelineResponse | null>(null);
  const loading = shallowRef(false);
  /** 接口失败，与「无数据」区分展示 */
  const error = shallowRef(false);
  const expandedFolds = shallowRef(new Set<string>());
  const expandedNodes = shallowRef(new Set<string>());
  /** 快捷筛选：Span 名称关键字与类别，均为前端过滤 */
  const filterKeyword = shallowRef('');
  const filterCategory = shallowRef<RumTimelineFilterCategoryType>(RumTimelineFilterCategoryEnum.ALL);
  /** View 卡片的排序方向：按 View 开始时间排序，只影响顶层 View 的顺序 */
  const sortOrder = shallowRef<RumTimelineSortType>(RumTimelineSortEnum.ASC);
  /** 是否折叠中间的 View：只展示首尾各 2 张卡片，中间收成一张隐藏卡片 */
  const collapseMiddleView = shallowRef(false);
  /** 请求序号，用于丢弃过期响应 */
  let requestId = 0;
  /** 已请求过的 `${appName}|${dimension}`，相同时不重复请求 */
  let fetchedKey = '';

  /** 当前详情的 Span，会话时间轴没有当前 Span 时为空串 */
  const currentSpan = computed(() => unref(currentSpanId) ?? '');

  async function fetchTimeline(app: string, dim: string) {
    const seq = ++requestId;
    loading.value = true;
    timeline.value = null;
    error.value = false;
    const res =
      scope === 'session'
        ? await getSessionTimeline({ app_name: app, session_id: dim })
        : await getViewTimeline({ app_name: app, view_id: dim });
    if (seq !== requestId) return;
    timeline.value = res;
    error.value = !res;
    loading.value = false;
  }

  watch(
    () => [unref(active), unref(appName), unref(dimension)] as const,
    ([isActive, app, dim]) => {
      if (!isActive) return;
      const key = `${app}|${dim}`;
      if (key === fetchedKey) return;
      fetchedKey = key;
      expandedFolds.value = new Set();
      expandedNodes.value = new Set();
      if (!dim) {
        requestId++;
        timeline.value = null;
        error.value = false;
        loading.value = false;
        return;
      }
      fetchTimeline(app, dim);
    },
    { immediate: true }
  );

  const recordMap = computed(() => buildRecordMap(timeline.value?.records));
  /** 当前 Span 的祖先链；会话时间轴没有当前 Span，直接返回空数组避免整树遍历 */
  const currentPath = computed(() => (currentSpan.value ? findSpanPath(timeline.value?.tree, currentSpan.value) : []));

  /** 节点是否命中当前筛选条件 */
  function matchRecord(record: IRumTimelineRecord | undefined) {
    const keyword = filterKeyword.value.trim().toLowerCase();
    if (
      keyword &&
      !String(record?.origin_data?.span_name ?? '')
        .toLowerCase()
        .includes(keyword)
    )
      return false;
    if (
      filterCategory.value !== RumTimelineFilterCategoryEnum.ALL &&
      !CATEGORY_PREDICATES[filterCategory.value](record)
    )
      return false;
    return true;
  }

  /** 保留命中的节点与其祖先链，未命中子树整枝裁掉 */
  function filterNodes(nodes: IRumTimelineNode[] = []): IRumTimelineNode[] {
    const result: IRumTimelineNode[] = [];
    for (const node of nodes) {
      const children = filterNodes(node.children);
      if (matchRecord(recordMap.value.get(node.span_id)) || children.length) {
        result.push({ ...node, children });
      }
    }
    return result;
  }

  const hasFilter = computed(
    () => filterKeyword.value.trim() !== '' || filterCategory.value !== RumTimelineFilterCategoryEnum.ALL
  );

  /** 筛选生效后可见的 View：未命中的 View 整张卡片丢弃，View 头部仍按全量统计 */
  const visibleViews = computed(() => {
    const nodes = timeline.value?.tree ?? [];
    if (!hasFilter.value) return nodes.map(node => ({ node, children: node.children ?? [] }));
    return nodes.reduce<{ children: IRumTimelineNode[]; node: IRumTimelineNode }[]>((result, node) => {
      const children = filterNodes(node.children);
      if (matchRecord(recordMap.value.get(node.span_id)) || children.length) {
        result.push({ node, children });
      }
      return result;
    }, []);
  });

  /** View 的开始时间（微秒），作为排序依据；缺失时按 0 处理 */
  function getViewStartedAt(spanId: string) {
    const startedAt = Number(recordMap.value.get(spanId)?.origin_data?.attributes?.['view.started_at']);
    return Number.isFinite(startedAt) ? startedAt : 0;
  }

  /** View 开始时间的展示值，HH:mm，用于卡片左侧时间轴；缺失时为空串 */
  function getViewTimeText(spanId: string) {
    const startTime = recordMap.value.get(spanId)?.origin_data?.start_time;
    if (startTime === null || startTime === undefined || !Number.isFinite(Number(startTime))) return '';
    return dayjs.tz(Number(startTime) / 1000).format('HH:mm');
  }

  /** 时间轴开始日期（如 8月3日 周一），用于首尾横幅的开始标记；接口未返回开始时间时为空 */
  const beginDateText = computed(() => {
    const startTime = timeline.value?.start_time;
    if (startTime === null || startTime === undefined) return '';
    const startDate = dayjs.tz(Number(startTime) / 1000);
    return t('{0}月{1}日 {2}', [startDate.month() + 1, startDate.date(), t(WEEKDAY_LABELS[startDate.day()])]);
  });

  /** 时间轴总耗时（微秒）：优先取接口 duration，接口未返回时用起止时间差兜底 */
  const duration = computed(() => {
    const rawDuration = timeline.value?.duration;
    if (rawDuration !== null && rawDuration !== undefined) {
      const value = Number(rawDuration);
      if (Number.isFinite(value) && value > 0) return value;
    }
    const startTime = timeline.value?.start_time;
    const endTime = timeline.value?.end_time;
    if (startTime === null || startTime === undefined || endTime === null || endTime === undefined) return 0;
    const diff = Number(endTime) - Number(startTime);
    return Number.isFinite(diff) && diff > 0 ? diff : 0;
  });

  const durationText = computed(() => (duration.value ? formatDuration(duration.value, '', 2, 'us') : ''));

  /** 时间轴总时长：仅已结束（有 end_time）时展示结束横幅 */
  const endDurationText = computed(() => {
    const endTime = timeline.value?.end_time;
    if (endTime === null || endTime === undefined) return '';
    return durationText.value;
  });

  /** 按 View 开始时间排列顶层 View 卡片，View 内部的 Span 行顺序不受影响 */
  const views = computed(() => {
    const direction = sortOrder.value === RumTimelineSortEnum.ASC ? 1 : -1;
    return [...visibleViews.value].sort(
      (a, b) => (getViewStartedAt(a.node.span_id) - getViewStartedAt(b.node.span_id)) * direction
    );
  });

  /** 每个可见 View 一张卡片，卡片内为该 View 的 Span 列表 */
  const cards = computed<IRumTimelineCardVM[]>(() =>
    views.value.map(({ node, children }) => ({
      key: node.span_id,
      timeText: getViewTimeText(node.span_id),
      view: buildViewVM(node, recordMap.value, currentSpan.value, formatField),
      items: buildTimelineItems(children, {
        recordMap: recordMap.value,
        currentSpanId: currentSpan.value,
        currentPath: new Set(currentPath.value),
        expandedFolds: expandedFolds.value,
        expandedNodes: expandedNodes.value,
        showAll: hasFilter.value,
      }),
    }))
  );

  /** 折叠中间 View 时的展示列表：首尾各保留 2 张卡片，中间收成一张隐藏卡片，不超过 4 张时全部展示 */
  const cardItems = computed<IRumTimelineCardItemVM[]>(() => {
    const list = cards.value;
    if (!collapseMiddleView.value || list.length <= COLLAPSE_EDGE_VIEW_COUNT * 2) {
      return list.map(card => ({ kind: 'card', card }));
    }
    const head = list.slice(0, COLLAPSE_EDGE_VIEW_COUNT).map(card => ({ kind: 'card' as const, card }));
    const tail = list.slice(-COLLAPSE_EDGE_VIEW_COUNT).map(card => ({ kind: 'card' as const, card }));
    const hidden: IRumTimelineCardItemVM = {
      kind: 'hidden',
      count: list.length - COLLAPSE_EDGE_VIEW_COUNT * 2,
    };
    return [...head, hidden, ...tail];
  });

  /** 点击隐藏卡片：展示全部 View，并同步取消「折叠中间 View」勾选 */
  const handleExpandHiddenViews = () => {
    collapseMiddleView.value = false;
  };

  /** 数据或当前 Span 变化时重置展开状态：折叠段全部收起，只展开当前 Span 的祖先节点 */
  watch(
    currentPath,
    path => {
      expandedFolds.value = new Set();
      expandedNodes.value = new Set(path.slice(0, -1));
    },
    { immediate: true }
  );

  /** 筛选生效时默认展开命中项的祖先，保证命中可见，之后仍可手动收起；筛选取消时恢复默认展开状态 */
  watch([hasFilter, visibleViews], ([filterActive, currentViews]) => {
    if (!filterActive) {
      expandedFolds.value = new Set();
      expandedNodes.value = new Set(currentPath.value.slice(0, -1));
      return;
    }
    const next = new Set<string>();
    const collectExpandable = (list?: IRumTimelineNode[]) => {
      for (const node of list ?? []) {
        if (node.children?.length) {
          next.add(node.span_id);
          collectExpandable(node.children);
        }
      }
    };
    for (const view of currentViews) collectExpandable(view.children);
    expandedNodes.value = next;
  });

  /** 展开一段折叠的 Span */
  const handleExpandFold = (key: string) => {
    expandedFolds.value = new Set(expandedFolds.value).add(key);
  };

  /** 切换节点子级的展开 / 收起 */
  const handleToggleNode = (spanId: string) => {
    const next = new Set(expandedNodes.value);
    if (next.has(spanId)) {
      next.delete(spanId);
    } else {
      next.add(spanId);
    }
    expandedNodes.value = next;
  };

  return {
    loading,
    error,
    cards,
    cardItems,
    hasFilter,
    filterKeyword,
    filterCategory,
    sortOrder,
    collapseMiddleView,
    durationText,
    beginDateText,
    endDurationText,
    handleExpandFold,
    handleExpandHiddenViews,
    handleToggleNode,
  };
}
