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

import { getBizRouteHref } from 'monitor-common/utils';

import { EMode } from '@/components/retrieval-filter/typing';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';
import { ALARM_CENTER_PANEL_TAB_MAP, type AlarmCenterPanelTabType } from '../../../utils/constant';

import type { ITableItem } from '../typing';
import type { IDiagnosticPanelFilter } from './navigate-typing';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

/** 维度展示名 → 主机/指标侧字段 */
const DIMENSION_NAME_TO_KEY: Record<string, string> = {
  主机名: 'bk_host_name',
  主机: 'bk_host_name',
  '目标 IP': 'bk_target_ip',
  IP: 'bk_target_ip',
  管控区域: 'bk_cloud_id',
};

/** 仅这些维度点击后切到左侧主机 tab 检索 */
const HOST_NAVIGABLE_DIMENSION_KEYS = new Set(['bk_host_name', 'bk_target_ip']);

export function isHostNavigableDimension(name: string) {
  return HOST_NAVIGABLE_DIMENSION_KEYS.has(DIMENSION_NAME_TO_KEY[name] || '');
}

/** Trace 明细展示名 → 调用链筛选字段 */
const TRACE_NAME_TO_KEY: Record<string, string> = {
  'Span ID': 'span_id',
  SpanID: 'span_id',
  '所属 Trace': 'trace_id',
  TraceID: 'trace_id',
  所属应用: 'app_name',
  所属服务: 'root_service',
  调用类型: 'kind',
};

function equalWhere(key: string, value: string): IWhereItem {
  return { key, operator: 'equal', value: [value] };
}

function containsWhere(key: string, value: string): IWhereItem {
  return { key, operator: 'like', value: [value] };
}

/** 切到指定 tab，并可选灌入筛选条件 */
export function navigateDiagnosticToTab(tab: AlarmCenterPanelTabType, filter?: IDiagnosticPanelFilter) {
  const store = useAlarmCenterDetailStore();
  store.navigateFromDiagnostic({
    tab,
    filter,
    nonce: Date.now(),
  });
}

export function navigateToHostTab(tableItem: ITableItem) {
  const key = DIMENSION_NAME_TO_KEY[tableItem.name] || '';
  if (!HOST_NAVIGABLE_DIMENSION_KEYS.has(key)) return;
  const filter: IDiagnosticPanelFilter = {};
  if (key === 'bk_target_ip') {
    filter.hostIp = tableItem.value;
  } else {
    filter.hostName = tableItem.value;
  }
  navigateDiagnosticToTab(ALARM_CENTER_PANEL_TAB_MAP.HOST, filter);
}

/**
 * 跳转策略配置详情页（查看态）。
 * 路由 `/strategy-config/detail/:id`，与告警表策略名跳转一致。
 */
export function openStrategyDetail(strategyId: number | string) {
  if (strategyId === undefined || strategyId === null || strategyId === '') return;
  const store = useAlarmCenterDetailStore();
  const bizId = store.alarmDetail?.bk_biz_id || store.bizId || window.cc_biz_id;
  window.open(getBizRouteHref(`/strategy-config/detail/${strategyId}`, bizId), '_blank');
}

export function navigateToTraceTab(tableItem: ITableItem, tableData?: ITableItem[]) {
  const fieldKey = TRACE_NAME_TO_KEY[tableItem.name];
  const filter: IDiagnosticPanelFilter = { filterMode: EMode.ui, where: [] };
  if (fieldKey === 'app_name') {
    filter.appName = tableItem.value;
  } else if (fieldKey) {
    filter.where = [equalWhere(fieldKey, tableItem.value)];
  } else {
    filter.where = [containsWhere('*', tableItem.value)];
  }
  const appItem = tableData?.find(item => TRACE_NAME_TO_KEY[item.name] === 'app_name');
  if (appItem?.value && !filter.appName) {
    filter.appName = appItem.value;
  }
  navigateDiagnosticToTab(ALARM_CENTER_PANEL_TAB_MAP.TRACE, filter);
}

/** 点击「示例 span」：用 Span ID（优先）或 Trace ID 在调用链 tab 检索 */
export function navigateToTraceBySpan(tableData: ITableItem[]) {
  const span = tableData.find(item => TRACE_NAME_TO_KEY[item.name] === 'span_id');
  const trace = tableData.find(item => TRACE_NAME_TO_KEY[item.name] === 'trace_id');
  const target = span || trace;
  if (!target) return;
  navigateToTraceTab(target, tableData);
}

export function navigateToLogTab(keyword: string) {
  navigateDiagnosticToTab(ALARM_CENTER_PANEL_TAB_MAP.LOG, {
    filterMode: EMode.ui,
    where: [containsWhere('*', keyword)],
  });
}

export function navigateToEventTab(eventNames: string[]) {
  const names = eventNames.filter(Boolean);
  if (!names.length) return;
  navigateDiagnosticToTab(ALARM_CENTER_PANEL_TAB_MAP.EVENT, {
    filterMode: EMode.ui,
    where: [{ key: 'event_name', operator: 'equal', value: names }],
  });
}

/**
 * 跳转指标检索，带上告警 graph_panel.targets，并把维度组合写入 filter_dict。
 * 无 targets 时仍打开带 filter_dict 占位的指标检索页，便于联调。
 */
export function openDataRetrievalByDimensions(tableData: ITableItem[]) {
  const store = useAlarmCenterDetailStore();
  const detail = store.alarmDetail;
  const bizId = detail?.bk_biz_id || store.bizId || window.cc_biz_id;
  let targets = detail?.graph_panel?.targets ? structuredClone(detail.graph_panel.targets) : [];
  const filterDict = tableData.reduce<Record<string, string>>((prev, item) => {
    const key = DIMENSION_NAME_TO_KEY[item.name] || item.name;
    if (item.value !== undefined && item.value !== '') {
      prev[key] = item.value;
    }
    return prev;
  }, {});

  if (targets?.length) {
    targets = targets.map((target: Record<string, any>) => {
      const data = target?.data || {};
      const queryConfigs = (data.query_configs || []).map((config: Record<string, any>) => ({
        ...config,
        filter_dict: { ...(config.filter_dict || {}), ...filterDict },
      }));
      return {
        ...target,
        data: {
          ...data,
          query_configs: queryConfigs,
        },
      };
    });
  } else {
    targets = [
      {
        data: {
          query_configs: [
            {
              filter_dict: filterDict,
            },
          ],
        },
      },
    ];
  }

  const url = `${location.origin}${location.pathname.replace('fta/', '')}?bizId=${bizId}#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`;
  window.open(url, '_blank');
}

/**
 * 【占位】日志聚类页跳转。联调就绪后替换为真实路由与参数。
 */
export function openLogClusteringPlaceholder(pattern?: string) {
  const store = useAlarmCenterDetailStore();
  const bizId = store.bizId || window.cc_biz_id;
  const params = new URLSearchParams({
    placeholder: '1',
    pattern: pattern || '',
  });
  window.open(`${location.origin}${location.pathname}?bizId=${bizId}#/log-clustering?${params.toString()}`, '_blank');
}
