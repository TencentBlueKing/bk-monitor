/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type { Ref } from 'vue';

import type { TNil } from './trace';

export enum ETraceViewType {
  TraceGraph = 'TraceGraph',
  TraceSpansView = 'TraceSpansView',
  TraceStatistics = 'TraceStatistics',
  TraceTimelineViewer = 'TraceTimelineViewer',
}

export interface IChildrenHiddenStore {
  childrenHiddenIds: Ref<any>;
  onChange: (spanId: string) => void;
}

export interface IFocusMatchesStore {
  findMatchesIDs: Ref<any>;
  focusMatchesId: Ref<string>;
  focusMatchesIdIndex: Ref<number>;
}

export interface ISpanBarStore {
  current: Ref<[number, number]>;
  onCurrentChange: (current: [number, number]) => void;
}

export interface IViewRange {
  time: IViewRangeTime;
}

export interface IViewRangeStore {
  viewRange: Ref<IViewRange>;
  onViewRangeChange: (viewRange: IViewRange) => void;
}

export interface IViewRangeTime {
  current: [number, number];
  cursor?: number | TNil;
  shiftEnd?: number;
  shiftStart?: number;
  reframe?: {
    anchor: number;
    shift: number;
  };
}

export type TUpdateViewRangeTimeFunction = (start: number, end: number, trackSrc?: string) => void;

export type ViewRangeTimeUpdate = ITimeCursorUpdate | ITimeReframeUpdate | ITimeShiftEndUpdate | ITimeShiftStartUpdate;

interface ITimeCursorUpdate {
  cursor: number | TNil;
}

interface ITimeReframeUpdate {
  reframe: {
    anchor: number;
    shift: number;
  };
}

interface ITimeShiftEndUpdate {
  shiftEnd: number;
}

interface ITimeShiftStartUpdate {
  shiftStart: number;
}
