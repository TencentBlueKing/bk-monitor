/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import dayjs from 'dayjs';

import type { BaseTableColumn } from '../trace-explore/components/trace-explore-table/typing';
import type { RumAppRow } from './rum-mock-data';

export type RumMetricTone = 'bad' | 'empty' | 'good' | 'warning';

export type RumTableColKey =
  | 'accessStatus'
  | 'actions'
  | 'apiFailRate'
  | 'appStatus'
  | 'createdAt'
  | 'creator'
  | 'dataStatus'
  | 'domain'
  | 'jsErrorRate'
  | 'lcpP75'
  | 'updatedAt';

export function formatLcpCell(sec: null | number) {
  if (sec == null || Number.isNaN(sec)) return '--';
  return `${sec.toFixed(1)}s`;
}

export function formatRateCell(pct: null | number) {
  if (pct == null || Number.isNaN(pct)) return '--';
  return `${pct.toFixed(1)}%`;
}

/** API 失败率：略严于 JS 错误率，便于出现「警示色」区间 */
export function getApiFailTone(pct: null | number): RumMetricTone {
  if (pct == null || Number.isNaN(pct)) return 'empty';
  if (pct <= 1) return 'good';
  if (pct <= 3) return 'warning';
  return 'bad';
}

/** 比率类：0-100，越低越好 */
export function getJsErrorTone(pct: null | number): RumMetricTone {
  if (pct == null || Number.isNaN(pct)) return 'empty';
  if (pct <= 0.5) return 'good';
  if (pct <= 2) return 'warning';
  return 'bad';
}

/** LCP：秒，越低越好（对齐 Web Vitals 量级） */
export function getLcpTone(sec: null | number): RumMetricTone {
  if (sec == null || Number.isNaN(sec)) return 'empty';
  if (sec <= 2.5) return 'good';
  if (sec <= 4) return 'warning';
  return 'bad';
}

function metricClass(tone: RumMetricTone) {
  if (tone === 'empty') return 'rum-metric rum-metric--empty';
  return `rum-metric rum-metric--${tone}`;
}

export const RUM_TABLE_FIELD_META: { field: RumTableColKey; label: string; locked?: boolean }[] = [
  { field: 'domain', label: '应用名称', locked: true },
  { field: 'lcpP75', label: 'LCP P75' },
  { field: 'jsErrorRate', label: 'JS 错误率' },
  { field: 'apiFailRate', label: 'API 失败率' },
  { field: 'dataStatus', label: '数据状态' },
  { field: 'accessStatus', label: '接入状态' },
  { field: 'appStatus', label: '应用状态' },
  { field: 'creator', label: '创建人' },
  { field: 'updatedAt', label: '最近更新时间' },
  { field: 'createdAt', label: '创建时间' },
  { field: 'actions', label: '操作', locked: true },
];

export const RUM_DEFAULT_VISIBLE_FIELDS: RumTableColKey[] = [
  'domain',
  'lcpP75',
  'jsErrorRate',
  'apiFailRate',
  'dataStatus',
  'actions',
];

export function buildRumTableColumnMap(onConfigure: (row: RumAppRow) => void): Record<RumTableColKey, BaseTableColumn> {
  return {
    domain: {
      colKey: 'domain',
      title: '应用名称',
      minWidth: 220,
      fixed: 'left',
      cellRenderer: (row: RumAppRow) => (
        <div class='rum-cell-app'>
          <div class='rum-cell-app__icon'>
            <i class='icon-monitor icon-wangye' />
          </div>
          <div class='rum-cell-app__text'>
            <div class='rum-cell-app__domain'>{row.domain}</div>
            <div class='rum-cell-app__alias'>{row.alias}</div>
          </div>
        </div>
      ),
    },
    lcpP75: {
      colKey: 'lcpP75',
      title: 'LCP P75',
      minWidth: 100,
      align: 'right',
      sorter: true,
      cellRenderer: (row: RumAppRow) => (
        <span class={metricClass(getLcpTone(row.lcpP75Sec))}>{formatLcpCell(row.lcpP75Sec)}</span>
      ),
    },
    jsErrorRate: {
      colKey: 'jsErrorRate',
      title: 'JS 错误率',
      minWidth: 112,
      align: 'right',
      sorter: true,
      cellRenderer: (row: RumAppRow) => (
        <span class={metricClass(getJsErrorTone(row.jsErrorRate))}>{formatRateCell(row.jsErrorRate)}</span>
      ),
    },
    apiFailRate: {
      colKey: 'apiFailRate',
      title: 'API 失败率',
      minWidth: 112,
      align: 'right',
      sorter: true,
      cellRenderer: (row: RumAppRow) => (
        <span class={metricClass(getApiFailTone(row.apiFailRate))}>{formatRateCell(row.apiFailRate)}</span>
      ),
    },
    dataStatus: {
      colKey: 'dataStatus',
      title: '数据状态',
      minWidth: 100,
      align: 'center',
      cellRenderer: (row: RumAppRow) =>
        row.dataStatus === 'healthy' ? (
          <i
            class='icon-monitor icon-mc-check-fill rum-status rum-status--ok'
            v-bk-tooltips={{ content: '正常' }}
          />
        ) : (
          <i
            class='icon-monitor icon-mc-alert rum-status rum-status--err'
            v-bk-tooltips={{ content: '异常' }}
          />
        ),
    },
    accessStatus: {
      colKey: 'accessStatus',
      title: '接入状态',
      minWidth: 100,
      filter: {
        type: 'multiple',
        resetValue: [],
        list: [
          { label: '已接入', value: '已接入' },
          { label: '接入中', value: '接入中' },
          { label: '未接入', value: '未接入' },
        ],
      },
    },
    appStatus: {
      colKey: 'appStatus',
      title: '应用状态',
      minWidth: 100,
      filter: {
        type: 'multiple',
        resetValue: [],
        list: [
          { label: '启用', value: '启用' },
          { label: '停用', value: '停用' },
        ],
      },
    },
    creator: {
      colKey: 'creator',
      title: '创建人',
      minWidth: 100,
    },
    updatedAt: {
      colKey: 'updatedAt',
      title: '最近更新时间',
      minWidth: 168,
      sorter: true,
      cellRenderer: (row: RumAppRow) => dayjs(row.updatedAt).format('YYYY-MM-DD HH:mm:ss'),
    },
    createdAt: {
      colKey: 'createdAt',
      title: '创建时间',
      minWidth: 168,
      sorter: true,
      cellRenderer: (row: RumAppRow) => dayjs(row.createdAt).format('YYYY-MM-DD HH:mm:ss'),
    },
    actions: {
      colKey: 'actions',
      title: '操作',
      minWidth: 88,
      fixed: 'right',
      align: 'center',
      cellRenderer: (row: RumAppRow) => (
        <button
          class='rum-action-link'
          type='button'
          onClick={() => onConfigure(row)}
        >
          配置
        </button>
      ),
    },
  };
}

export function pickRumColumns(visibleFields: string[], map: Record<string, BaseTableColumn>): BaseTableColumn[] {
  return visibleFields.map(f => map[f]).filter(Boolean) as BaseTableColumn[];
}
