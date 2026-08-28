/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export interface ClusterPatternRow {
  count: number;
  group: string[];
  id: number;
  is_new_class: boolean;
  origin_log: string;
  origin_pattern: string;
  owners: string[];
  pattern: string;
  percentage: number;
  remark: any[];
  signature: string;
  strategy_enabled: boolean;
  strategy_id: number;
  year_on_year_count: number;
  year_on_year_percentage: number;
  [key: string]: any;
}

export interface ITableItem {
  childCount?: number;
  data?: ClusterPatternRow;
  group?: string[];
  groupKey: string;
  hashKey: string;
  hidden?: boolean;
  index: number;
  isGroupRow: boolean;
}

export type ClusterDisplayType = 'group' | 'flatten';

export interface ClusterFilterSort {
  filter: {
    owners: string[];
    remark: string[];
  };
  sort: Record<string, string>;
}

export interface ClusterPipelineInput {
  displayType: ClusterDisplayType | string;
  filterSort: ClusterFilterSort;
  groupBy: string[];
  raw?: ClusterPatternRow[];
}

export interface ClusterPipelineResult {
  childCount: number;
  groupCount: number;
  list: ITableItem[];
  visibleCount: number;
}

export interface WalkVisibleWindowOptions {
  displayType: ClusterDisplayType | string;
  groupByLength: number;
  limit: number;
  openMap: Record<string, { isOpen?: boolean } | undefined>;
}

export interface ClusterGroupMeta {
  childCount?: number;
  groupKey: string;
  hashKey: string;
  hidden?: boolean;
}

export interface ClusterViewResult {
  childCount: number;
  groupCount: number;
  groups: ClusterGroupMeta[];
  openMap: Record<string, { isOpen?: boolean }>;
  visibleCount: number;
  window: ITableItem[];
}

export const getOwnerList = (owners: unknown): string[] => {
  if (Array.isArray(owners)) return owners as string[];
  if (owners && typeof owners === 'object' && Array.isArray((owners as { value?: unknown }).value)) {
    return (owners as { value: string[] }).value;
  }
  return [];
};

export function fastHash(text: string, length = 16) {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;

  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ char, 2654435761);
    h2 = Math.imul(h2 ^ char, 1597334677);
    h1 = (h1 << 13) | (h1 >>> 19);
    h2 = (h2 << 17) | (h2 >>> 15);
  }

  const combined = (h1 & 0x1fffff) * 0x1000000000 + (h2 & 0xfffffff);
  return combined.toString(36).padStart(length, '0').slice(-length);
}

const getByPath = (obj: any, path: string) => {
  const keys = path.split('.');
  let current = obj;
  for (const key of keys) {
    if (current == null) return undefined;
    current = current[key];
  }
  return current;
};

const sortByPath = <T>(list: T[], path: string, order: 'asc' | 'desc'): T[] => {
  const dir = order === 'desc' ? -1 : 1;
  return list.slice().sort((left, right) => {
    const va = getByPath(left, path);
    const vb = getByPath(right, path);
    if (va === vb) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (va > vb) return dir;
    if (va < vb) return -dir;
    return 0;
  });
};

const normalizePatternRow = (item: ClusterPatternRow, id: number): ClusterPatternRow => ({
  ...item,
  id,
  owners: getOwnerList(item.owners),
});

export function buildGroupedList(raw: ClusterPatternRow[], groupBy: string[]) {
  const listMap = new Map<string, ClusterPatternRow[]>();
  const groupKeys: string[] = [];

  raw.forEach(item => {
    const groupList = item.group?.map((g, i) => `${groupBy[i] ?? '#'}=${g}`) ?? ['#'];
    const groupKey = groupList.length ? groupList.join(' | ') : '#';
    if (!listMap.has(groupKey)) {
      listMap.set(groupKey, []);
      groupKeys.push(groupKey);
    }
    listMap.get(groupKey)!.push(item);
  });

  const list: ITableItem[] = [];
  let index = 0;

  groupKeys.forEach(key => {
    const children = listMap.get(key) ?? [];
    const hashKey = fastHash(key);
    index += 1;
    list.push({
      childCount: children.length,
      group: children[0]?.group,
      groupKey: key,
      hashKey,
      index,
      isGroupRow: true,
    });

    children.forEach(item => {
      index += 1;
      list.push({
        data: normalizePatternRow(item, index),
        groupKey: key,
        hashKey,
        index,
        isGroupRow: false,
      });
    });
  });

  return {
    childCount: raw.length,
    groupCount: groupKeys.length,
    list,
  };
}

const createFilterFn = (filterSort: ClusterFilterSort) => {
  const owners = filterSort.filter.owners ?? [];
  const remark = filterSort.filter.remark ?? [];
  const isRemarked = remark[0] === 'remarked';
  const ownersMap = owners.reduce<Record<string, boolean>>((map, item) => Object.assign(map, { [item]: true }), {});
  const filterOwners = owners.length > 0;
  const filterRemark = remark.length > 0;
  const noOwner = owners.length === 1 && owners[0] === 'no_owner';

  return (item: ITableItem) => {
    let result = true;
    if (filterOwners) {
      const ownerList = getOwnerList(item.data?.owners);
      result = noOwner ? ownerList.length > 0 : ownerList.some(owner => !!ownersMap[owner]);
    }
    if (filterRemark && result) {
      result = isRemarked ? (item.data?.remark ?? []).length > 0 : !item.data?.remark?.length;
    }
    return result;
  };
};

const sortGroupedRows = (
  targetList: ITableItem[],
  filterFn: (_item: ITableItem) => boolean,
  sortMap: Record<string, string>,
) => {
  const groupList: ITableItem[] = [];
  const groupMap = new Map<string, ITableItem[]>();
  let visibleCount = 0;
  const sortObj = Object.entries(sortMap).find(item => !!item[1]);

  for (const item of targetList) {
    if (!groupMap.has(item.hashKey)) {
      groupMap.set(item.hashKey, []);
    }
    if (item.isGroupRow) {
      groupList.push(item);
    } else {
      groupMap.get(item.hashKey)!.push(item);
    }
  }

  const resultList: ITableItem[] = [];
  for (const group of groupList) {
    resultList.push(group);
    let childList = groupMap.get(group.hashKey) ?? [];

    if (sortObj) {
      const [field, order] = sortObj;
      const sortField = order === 'none' ? 'index' : `data.${field}`;
      const orders = (order === 'none' ? 'asc' : order) as 'asc' | 'desc';
      childList = sortByPath(childList, sortField, orders);
    }

    let isHiddenGroup = true;
    for (const child of childList) {
      child.hidden = !filterFn(child);
      resultList.push(child);
      if (!child.hidden) {
        isHiddenGroup = false;
        visibleCount += 1;
      }
    }
    group.hidden = isHiddenGroup;
  }

  groupMap.clear();
  return { list: resultList, visibleCount };
};

const sortFlattenRows = (
  targetList: ITableItem[],
  filterFn: (_item: ITableItem) => boolean,
  sortMap: Record<string, string>,
) => {
  const groupRows: ITableItem[] = [];
  let childList: ITableItem[] = [];
  let visibleCount = 0;
  const sortObj = Object.entries(sortMap).find(item => !!item[1]);

  for (const item of targetList) {
    if (item.isGroupRow) {
      groupRows.push(item);
    } else {
      childList.push(item);
    }
  }

  if (sortObj) {
    const [field, order] = sortObj;
    const sortField = order === 'none' ? 'data.count' : `data.${field}`;
    const orders = (order === 'none' ? 'desc' : order) as 'asc' | 'desc';
    childList = sortByPath(childList, sortField, orders);
  } else {
    childList = sortByPath(childList, 'data.count', 'desc');
  }

  for (const child of childList) {
    child.hidden = !filterFn(child);
    groupRows.push(child);
    if (!child.hidden) {
      visibleCount += 1;
    }
  }

  return { list: groupRows, visibleCount };
};

export function applySortAndFilter(
  targetList: ITableItem[],
  input: Pick<ClusterPipelineInput, 'displayType' | 'filterSort' | 'groupBy'>,
) {
  const filterFn = createFilterFn(input.filterSort);
  if (input.displayType === 'group' && (input.groupBy?.length ?? 0) > 0) {
    return sortGroupedRows(targetList, filterFn, input.filterSort.sort);
  }
  return sortFlattenRows(targetList, filterFn, input.filterSort.sort);
}

export function runClusterTablePipeline(input: ClusterPipelineInput): ClusterPipelineResult {
  const grouped = buildGroupedList(input.raw ?? [], input.groupBy ?? []);
  const sorted = applySortAndFilter(grouped.list, input);
  return {
    childCount: grouped.childCount,
    groupCount: grouped.groupCount,
    list: sorted.list,
    visibleCount: sorted.visibleCount,
  };
}

export function walkVisibleWindow(list: ITableItem[], options: WalkVisibleWindowOptions): ITableItem[] {
  const showGroup = options.displayType === 'group' && options.groupByLength > 0;
  const result: ITableItem[] = [];
  let visible = 0;

  for (const item of list) {
    if (item.hidden) continue;

    if (showGroup) {
      if (item.isGroupRow) {
        result.push(item);
        visible += 1;
      } else if (options.openMap[item.hashKey]?.isOpen) {
        result.push(item);
        visible += 1;
      }
    } else if (!item.isGroupRow) {
      result.push(item);
      visible += 1;
    }

    if (visible >= options.limit) break;
  }

  return result;
}

export function collectGroupMeta(list: ITableItem[]): ClusterGroupMeta[] {
  return list
    .filter(item => item.isGroupRow)
    .map(item => ({
      childCount: item.childCount,
      groupKey: item.groupKey,
      hashKey: item.hashKey,
      hidden: item.hidden,
    }));
}

export function resolveOpenMap(
  list: ITableItem[],
  options: WalkVisibleWindowOptions,
): Record<string, { isOpen?: boolean }> {
  const openMap: Record<string, { isOpen?: boolean }> = {};
  Object.keys(options.openMap || {}).forEach(key => {
    openMap[key] = { isOpen: !!options.openMap[key]?.isOpen };
  });
  const showGroup = options.displayType === 'group' && options.groupByLength > 0;
  if (!showGroup) return openMap;
  if (Object.values(openMap).some(item => item?.isOpen)) return openMap;
  const first = list.find(item => item.isGroupRow && !item.hidden);
  if (first) openMap[first.hashKey] = { isOpen: true };
  return openMap;
}

export function buildClusterView(
  list: ITableItem[],
  counts: Pick<ClusterPipelineResult, 'childCount' | 'groupCount' | 'visibleCount'>,
  options: WalkVisibleWindowOptions,
): ClusterViewResult {
  const openMap = resolveOpenMap(list, options);
  const window = walkVisibleWindow(list, { ...options, openMap });
  return {
    childCount: counts.childCount,
    groupCount: counts.groupCount,
    groups: collectGroupMeta(window),
    openMap,
    visibleCount: counts.visibleCount,
    window,
  };
}

export function toPlainOpenMap(
  openMap: Record<string, { isOpen?: boolean } | undefined> = {},
): Record<string, { isOpen?: boolean }> {
  const plain: Record<string, { isOpen?: boolean }> = {};
  Object.keys(openMap).forEach(key => {
    plain[key] = { isOpen: !!openMap[key]?.isOpen };
  });
  return plain;
}

export function toPlainPipelineInput(input: ClusterPipelineInput, sendRaw = true): ClusterPipelineInput {
  return {
    displayType: String(input.displayType || 'group'),
    filterSort: {
      filter: {
        owners: [...(input.filterSort?.filter?.owners ?? [])],
        remark: [...(input.filterSort?.filter?.remark ?? [])],
      },
      sort: { ...(input.filterSort?.sort ?? {}) },
    },
    groupBy: [...(input.groupBy ?? [])].map(item => String(item)),
    raw: sendRaw ? (input.raw ?? []) : undefined,
  };
}

export function toPlainWindowOptions(options: WalkVisibleWindowOptions): WalkVisibleWindowOptions {
  return {
    displayType: String(options.displayType || 'group'),
    groupByLength: Number(options.groupByLength || 0),
    limit: Math.max(1, Number(options.limit || 50)),
    openMap: toPlainOpenMap(options.openMap),
  };
}
