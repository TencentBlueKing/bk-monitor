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

export interface IBoundaryDraft extends IRangeCost {
  boundary: number;
  boundaryIndex: number;
  range: { from: number; to: number };
  routes: IRouteSegment[];
  sourceNodeId: number;
  targetNodeId: number;
}

export interface ICostPrefix {
  lowerBytes: number;
  measuredCount: number;
  peakMembers: number;
  strategyId: number;
  unmeasuredCount: number;
  upperBytes: number;
}

export interface IRangeCost {
  lowerBytes: number;
  measuredCount: number;
  peakMembers: number;
  unmeasuredCount: number;
  upperBytes: number;
}

export interface IRouteSegment {
  from: number;
  nodeId: number;
  to: number;
}

const prefixAt = (prefix: ICostPrefix[], strategyId: number): IRangeCost => {
  let left = 0;
  let right = prefix.length - 1;
  let matched = -1;
  while (left <= right) {
    const middle = Math.floor((left + right) / 2);
    if (prefix[middle].strategyId <= strategyId) {
      matched = middle;
      left = middle + 1;
    } else {
      right = middle - 1;
    }
  }
  if (matched < 0) {
    return { lowerBytes: 0, upperBytes: 0, peakMembers: 0, measuredCount: 0, unmeasuredCount: 0 };
  }
  const item = prefix[matched];
  return {
    lowerBytes: item.lowerBytes,
    upperBytes: item.upperBytes,
    peakMembers: item.peakMembers,
    measuredCount: item.measuredCount,
    unmeasuredCount: item.unmeasuredCount,
  };
};

export const costBetween = (prefix: ICostPrefix[], from: number, to: number): IRangeCost => {
  if (from > to) {
    return { lowerBytes: 0, upperBytes: 0, peakMembers: 0, measuredCount: 0, unmeasuredCount: 0 };
  }
  const end = prefixAt(prefix, to);
  const before = prefixAt(prefix, from - 1);
  return {
    lowerBytes: Math.max(0, end.lowerBytes - before.lowerBytes),
    upperBytes: Math.max(0, end.upperBytes - before.upperBytes),
    peakMembers: Math.max(0, end.peakMembers - before.peakMembers),
    measuredCount: Math.max(0, end.measuredCount - before.measuredCount),
    unmeasuredCount: Math.max(0, end.unmeasuredCount - before.unmeasuredCount),
  };
};

export const coverageBetween = (prefix: ICostPrefix[], from: number, to: number) => {
  const cost = costBetween(prefix, from, to);
  return { measuredCount: cost.measuredCount, unmeasuredCount: cost.unmeasuredCount };
};

export const buildBoundaryDraft = (
  routes: IRouteSegment[],
  boundaryIndex: number,
  boundary: number,
  prefix: ICostPrefix[]
): IBoundaryDraft => {
  const nextRoutes = routes.map(route => ({ ...route }));
  const left = nextRoutes[boundaryIndex];
  const right = nextRoutes[boundaryIndex + 1];
  if (!left || !right) throw new Error('invalid route boundary');
  const originalBoundary = left.to;
  const bounded = Math.max(left.from, Math.min(boundary, right.to - 1));
  left.to = bounded;
  right.from = bounded + 1;

  const movingRight = bounded > originalBoundary;
  const range = movingRight ? { from: originalBoundary + 1, to: bounded } : { from: bounded + 1, to: originalBoundary };
  const sourceNodeId = movingRight ? right.nodeId : left.nodeId;
  const targetNodeId = movingRight ? left.nodeId : right.nodeId;
  const cost = costBetween(prefix, range.from, range.to);

  return {
    boundary: bounded,
    boundaryIndex,
    range,
    routes: nextRoutes,
    sourceNodeId,
    targetNodeId,
    ...cost,
  };
};

export const calculateMemoryScale = (values: number[]): number => {
  const valid = values.filter(value => Number.isFinite(value) && value > 0).sort((a, b) => a - b);
  if (!valid.length) return 1024 * 1024;
  const mib = 1024 * 1024;
  const maximum = valid[valid.length - 1];
  return 2 ** Math.ceil(Math.log2(Math.max(maximum, mib) / mib)) * mib;
};

export const calculateMarkerHeight = (value: number, scale: number) => (value / scale) * 110;

export const estimateMax3hMemoryRange = (
  before: null | number,
  costLower: number,
  costUpper: number,
  isSource: boolean
): { lower: null | number; upper: null | number } => {
  if (before === null) return { lower: null, upper: null };
  if (isSource) {
    return {
      lower: Math.max(0, before - costUpper),
      upper: Math.max(0, before - costLower),
    };
  }
  return { lower: before + costLower, upper: before + costUpper };
};

export const canEditBoundary = (
  routes: IRouteSegment[],
  boundaryIndex: number,
  enabledNodeIds: number[],
  topologyValid: boolean
) => {
  if (!topologyValid) return false;
  const enabled = new Set(enabledNodeIds);
  const left = routes[boundaryIndex];
  const right = routes[boundaryIndex + 1];
  return !!left && !!right && enabled.has(left.nodeId) && enabled.has(right.nodeId);
};

export const buildSparklineSegments = (trend: Array<[null | number, number]>) => {
  if (trend.length < 2) return [];
  const ordered = [...trend].sort((left, right) => left[1] - right[1]);
  const validValues = ordered.filter(item => item[0] !== null) as Array<[number, number]>;
  if (validValues.length < 2) return [];
  const minimumValue = Math.min(...validValues.map(item => item[0]));
  const maximumValue = Math.max(...validValues.map(item => item[0]));
  const valueSpan = Math.max(maximumValue - minimumValue, 1);
  const minimumTime = ordered[0][1];
  const timeSpan = Math.max(ordered[ordered.length - 1][1] - minimumTime, 1);
  const segments: string[][] = [];
  let current: string[] = [];

  for (const [value, timestamp] of ordered) {
    if (value === null) {
      if (current.length > 1) segments.push(current);
      current = [];
      continue;
    }
    const x = ((timestamp - minimumTime) / timeSpan) * 180;
    const y = 38 - ((value - minimumValue) / valueSpan) * 34;
    current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  if (current.length > 1) segments.push(current);
  return segments.map(segment => segment.join(' '));
};

export const canAccessRedisManagement = (isSuperuser: boolean, actionResults: Array<{ isAllowed?: boolean }>) =>
  isSuperuser && actionResults.some(item => item.isAllowed === true);

export const resolveRedisManagementAccess = async (
  isSuperuser: boolean,
  loadActionResults: () => Promise<Array<{ isAllowed?: boolean }>>
) => {
  if (!isSuperuser) return false;
  const actionResults = await loadActionResults().catch(() => []);
  return canAccessRedisManagement(isSuperuser, actionResults);
};

export const buildRedisManagementForbiddenQuery = (isSuperuser: boolean, actionId: string, fullPath: string) =>
  isSuperuser
    ? {
        actionId,
        fromUrl: fullPath.replace(/^\//, ''),
      }
    : undefined;
