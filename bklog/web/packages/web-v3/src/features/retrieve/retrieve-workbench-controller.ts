/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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

import type { RetrieveRouteState } from './retrieve-data-adapter';
import type { RetrieveTab } from './workspace-controller';

export type QueryMode = 'ui' | 'sql' | 'ai';
export type DialogKey = 'share' | 'saveFavorite' | 'fieldConfig' | 'globalSettings' | 'download' | 'more' | 'context' | 'realtime' | null;

export interface QueryCondition {
  field: string;
  operator: 'contains' | 'eq' | 'not';
  value: string;
  logic: 'AND' | 'OR';
}

export interface WorkbenchSnapshot {
  routeState: RetrieveRouteState;
  queryState: {
    keyword: string;
    mode: QueryMode;
    conditions: QueryCondition[];
    page: number;
    timeRange: { startTime: number; endTime: number };
    autoRefresh: boolean;
  };
  uiState: {
    favoriteShown: boolean;
    fieldShown: boolean;
    resultView: 'raw' | 'table';
    showLineNo: boolean;
    wrapLog: boolean;
    sortDesc: boolean;
    activeDialog: DialogKey;
  };
  dataState: {
    bootstrapReady: boolean;
    activeTab: RetrieveTab;
    favoriteId: string;
  };
  errorState: Record<'bootstrap' | 'fields' | 'favorites' | 'search' | 'histogram' | 'dialog', string>;
}

export type WorkbenchIntent =
  | { type: 'route/replace'; route: RetrieveRouteState }
  | { type: 'query/change'; keyword?: string; mode?: QueryMode; conditions?: QueryCondition[] }
  | { type: 'query/submit'; resetPage?: boolean }
  | { type: 'time/change'; timeRange: { startTime: number; endTime: number } }
  | { type: 'tab/change'; tab: RetrieveTab }
  | { type: 'favorite/apply'; favoriteId: string; keyword: string }
  | { type: 'ui/toggleFavorite' }
  | { type: 'ui/toggleField' }
  | { type: 'ui/resultView'; view: 'raw' | 'table' }
  | { type: 'dialog/open'; dialog: Exclude<DialogKey, null> }
  | { type: 'dialog/close' }
  | { type: 'error/set'; scope: keyof WorkbenchSnapshot['errorState']; message: string }
  | { type: 'error/clear'; scope: keyof WorkbenchSnapshot['errorState'] };

const createDefaultTimeRange = (now = Date.now()) => ({
  startTime: now - 15 * 60 * 1000,
  endTime: now,
});

const emptyErrors: WorkbenchSnapshot['errorState'] = {
  bootstrap: '',
  fields: '',
  favorites: '',
  search: '',
  histogram: '',
  dialog: '',
};

export class RetrieveWorkbenchController {
  private snapshot: WorkbenchSnapshot;

  constructor(routeState: RetrieveRouteState, now = Date.now()) {
    this.snapshot = {
      routeState: { ...routeState },
      queryState: {
        keyword: '',
        mode: 'ui',
        conditions: [],
        page: 1,
        timeRange: createDefaultTimeRange(now),
        autoRefresh: false,
      },
      uiState: {
        favoriteShown: false,
        fieldShown: true,
        resultView: 'raw',
        showLineNo: false,
        wrapLog: false,
        sortDesc: false,
        activeDialog: null,
      },
      dataState: {
        bootstrapReady: false,
        activeTab: routeState.tab,
        favoriteId: '',
      },
      errorState: { ...emptyErrors },
    };
  }

  getState(): WorkbenchSnapshot {
    return {
      routeState: { ...this.snapshot.routeState },
      queryState: {
        ...this.snapshot.queryState,
        conditions: this.snapshot.queryState.conditions.map(item => ({ ...item })),
        timeRange: { ...this.snapshot.queryState.timeRange },
      },
      uiState: { ...this.snapshot.uiState },
      dataState: { ...this.snapshot.dataState },
      errorState: { ...this.snapshot.errorState },
    };
  }

  dispatch(intent: WorkbenchIntent): WorkbenchSnapshot {
    if (intent.type === 'route/replace') {
      this.snapshot = {
        ...this.snapshot,
        routeState: { ...intent.route },
        queryState: { ...this.snapshot.queryState, page: 1 },
        dataState: { ...this.snapshot.dataState, activeTab: intent.route.tab },
      };
    }
    if (intent.type === 'query/change') {
      this.snapshot = {
        ...this.snapshot,
        queryState: {
          ...this.snapshot.queryState,
          keyword: intent.keyword ?? this.snapshot.queryState.keyword,
          mode: intent.mode ?? this.snapshot.queryState.mode,
          conditions: intent.conditions?.map(item => ({ ...item })) ?? this.snapshot.queryState.conditions,
        },
      };
    }
    if (intent.type === 'query/submit') {
      this.snapshot = {
        ...this.snapshot,
        queryState: {
          ...this.snapshot.queryState,
          page: intent.resetPage ? 1 : this.snapshot.queryState.page,
        },
        errorState: { ...this.snapshot.errorState, search: '' },
      };
    }
    if (intent.type === 'time/change') {
      this.snapshot = {
        ...this.snapshot,
        queryState: { ...this.snapshot.queryState, timeRange: { ...intent.timeRange }, page: 1 },
        errorState: { ...this.snapshot.errorState, search: '', histogram: '' },
      };
    }
    if (intent.type === 'tab/change') {
      this.snapshot = {
        ...this.snapshot,
        routeState: { ...this.snapshot.routeState, tab: intent.tab },
        dataState: { ...this.snapshot.dataState, activeTab: intent.tab },
      };
    }
    if (intent.type === 'favorite/apply') {
      this.snapshot = {
        ...this.snapshot,
        queryState: { ...this.snapshot.queryState, keyword: intent.keyword, page: 1 },
        dataState: { ...this.snapshot.dataState, favoriteId: intent.favoriteId },
      };
    }
    if (intent.type === 'ui/toggleFavorite') {
      this.snapshot = {
        ...this.snapshot,
        uiState: { ...this.snapshot.uiState, favoriteShown: !this.snapshot.uiState.favoriteShown },
      };
    }
    if (intent.type === 'ui/toggleField') {
      this.snapshot = {
        ...this.snapshot,
        uiState: { ...this.snapshot.uiState, fieldShown: !this.snapshot.uiState.fieldShown },
      };
    }
    if (intent.type === 'ui/resultView') {
      this.snapshot = {
        ...this.snapshot,
        uiState: { ...this.snapshot.uiState, resultView: intent.view },
      };
    }
    if (intent.type === 'dialog/open') {
      this.snapshot = {
        ...this.snapshot,
        uiState: { ...this.snapshot.uiState, activeDialog: intent.dialog },
        errorState: { ...this.snapshot.errorState, dialog: '' },
      };
    }
    if (intent.type === 'dialog/close') {
      this.snapshot = {
        ...this.snapshot,
        uiState: { ...this.snapshot.uiState, activeDialog: null },
      };
    }
    if (intent.type === 'error/set') {
      this.snapshot = {
        ...this.snapshot,
        errorState: { ...this.snapshot.errorState, [intent.scope]: intent.message },
      };
    }
    if (intent.type === 'error/clear') {
      this.snapshot = {
        ...this.snapshot,
        errorState: { ...this.snapshot.errorState, [intent.scope]: '' },
      };
    }
    return this.getState();
  }
}
