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

import { deepClone, getBizRouteHref } from 'monitor-common/utils';

import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { ITableItem } from '../typing';

/**
 * AI 诊断里的跳转一律新开页，不与左侧告警详情联动。
 * 面板内的明细改为 hover「添加至聊天」，见 use-hover-to-chat.ts。
 */

/** 维度展示名 → 后端字段 */
const DIMENSION_NAME_TO_KEY: Record<string, string> = {
  主机名: 'bk_host_name',
  主机: 'bk_host_name',
  '目标 IP': 'bk_target_ip',
  IP: 'bk_target_ip',
  管控区域: 'bk_cloud_id',
};

/** 展示名形如「RPC 应用（app）」时取括号里的字段名，其余按原名 */
const resolveDimensionKey = (name: string) => {
  if (DIMENSION_NAME_TO_KEY[name]) return DIMENSION_NAME_TO_KEY[name];
  return name.match(/[（(]([\w.]+)[)）]\s*$/)?.[1] || name;
};

/** 【临时联调 mock】维度 mock 里的占位项，拼检索条件时跳过，否则查不出数据 */
const isPlaceholderDimension = (item: ITableItem) =>
  String(item.name).includes('占位') || String(item.value).includes('占位');

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

/**
 * 点事件分析的事件总数：新开页打开事件检索，带上该告警的时间范围。
 * 链接拼法与左侧事件面板的「更多事件」一致。
 */
export function openEventExplore() {
  const store = useAlarmCenterDetailStore();
  const detail = store.alarmDetail;
  const bizId = detail?.bk_biz_id || store.bizId || window.cc_biz_id;
  const params = new URLSearchParams();
  if (detail?.begin_time) {
    params.set('from', String(detail.begin_time * 1000));
    params.set('to', String(Date.now()));
  }
  const query = params.toString();
  const url = `${location.origin}${location.pathname}?bizId=${bizId}#/event-explore${query ? `?${query}` : ''}`;
  window.open(url, '_blank');
}

/**
 * 点异常维度（组合）：新开页打开指标检索，查该告警的指标 + 这组维度条件。
 * targets 沿用告警自身的 graph_panel，条件按指标检索的 where 结构追加。
 */
export function openMetricRetrievalByDimensions(tableData: ITableItem[]) {
  const store = useAlarmCenterDetailStore();
  const detail = store.alarmDetail;
  const bizId = detail?.bk_biz_id || store.bizId || window.cc_biz_id;
  const targets = deepClone(detail?.graph_panel?.targets || []);
  if (!targets.length) return;

  const conditions = tableData
    .filter(item => !isPlaceholderDimension(item))
    .map(item => ({ key: resolveDimensionKey(item.name), value: [String(item.value)] }))
    .filter(item => item.key && item.value[0]);

  for (const target of targets) {
    for (const queryConfig of target?.data?.query_configs || []) {
      queryConfig.where = [
        ...(queryConfig.where || []),
        ...conditions.map(item => ({ key: item.key, method: 'eq', value: item.value, condition: 'and' })),
      ];
    }
  }

  const url = `${location.origin}${location.pathname.replace('fta/', '')}?bizId=${bizId}#/data-retrieval/?targets=${encodeURIComponent(
    JSON.stringify(targets)
  )}`;
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
