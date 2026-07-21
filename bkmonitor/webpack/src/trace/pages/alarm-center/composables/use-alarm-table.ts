/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { ref as deepRef, onMounted, onScopeDispose, shallowRef, watch, watchEffect } from 'vue';

import { commonPageSizeGet } from 'monitor-common/utils';

import { TrendRangeEnum } from '../alarm-issues/constant';
import { type ActionTableItem, type AlertTableItem, type IncidentTableItem, AlarmType } from '../typings';
import { getOperatorDisabled } from '../utils';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { IssueItem, TrendRangeType } from '../alarm-issues/typing';
import type { IssuesService } from '../services/issues-services';

export function useAlarmTable() {
  const alarmStore = useAlarmCenterStore();
  /** 分页参数 */
  const pageSize = shallowRef(commonPageSizeGet() ?? 50);
  /** 当前页 */
  const page = shallowRef(1);
  /** 总条数 */
  const total = shallowRef(0);
  /** 查询结果完整性 */
  const isPartial = shallowRef(false);
  const totalRelation = shallowRef<'eq' | 'gte'>('eq');
  /** 表格数据（深响应式，支持直接修改行对象属性后触发重新渲染） */
  const data = deepRef<(ActionTableItem | AlertTableItem | IncidentTableItem | IssueItem)[]>([]);
  /** 排序字段 */
  const ordering = shallowRef('');
  /** 是否加载中 */
  const loading = shallowRef(false);
  /** Issues 趋势时间范围（默认 24h） */
  const trendRange = shallowRef<TrendRangeType>(TrendRangeEnum.HOURS_24);
  /** Issues 趋势数据是否加载中 */
  const trendLoading = shallowRef(false);
  /** 已开启故障分析功能的空间 bizId 列表（incident 场景专用） */
  const enabledSpaces = deepRef<number[]>([]);
  /** BK助手链接 */
  const wxCsLink = shallowRef('');
  /** 请求中止控制器 */
  let abortController: AbortController | null = null;
  /** 趋势请求中止控制器 */
  let trendAbortController: AbortController | null = null;

  const effectFunc = async () => {
    // 中止上一次未完成的请求
    if (abortController) {
      abortController.abort();
    }
    // 创建新的中止控制器
    abortController = new AbortController();
    const { signal } = abortController;

    loading.value = true;
    data.value = [];
    isPartial.value = false;
    totalRelation.value = 'eq';
    const params = {
      ...alarmStore.commonFilterParams,
      page_size: pageSize.value,
      page: page.value,
      ordering: ordering.value ? [ordering.value] : [],
    };
    const res = await alarmStore.alarmService.getFilterTableList(params, { signal });
    // 获取告警关联事件数 和 关联告警信息
    await alarmStore.alarmService
      .getAlterRelevance(res.data as (ActionTableItem | AlertTableItem | IncidentTableItem)[], { signal })
      .then(result => {
        if (!result) return;
        // eslint-disable-next-line @typescript-eslint/naming-convention
        const { event_count, extend_info } = result;
        for (const item of res.data as AlertTableItem[]) {
          item.event_count = event_count?.[item.id];
          item.extend_info = extend_info?.[item.id];
          item.followerDisabled = getOperatorDisabled(item.follower, item.assignee);
        }
      });
    // 检查请求是否已被中止，确保不会更新过期数据
    if (signal.aborted) return;
    total.value = res.total;
    isPartial.value = res.isPartial ?? false;
    totalRelation.value = res.totalRelation ?? 'eq';
    data.value = res.data;
    enabledSpaces.value = (res.enabled_spaces ?? []).map(Number);
    wxCsLink.value = res.wx_cs_link ?? '';
    loading.value = false;
    fetchTrendData();
  };
  /**
   * @description 单独请求 Issues 趋势数据并回填到当前列表行
   */
  const fetchTrendData = async () => {
    if (alarmStore.alarmType !== AlarmType.ISSUES) return;
    const issues = data.value as IssueItem[];
    if (!issues.length) return;
    const endTime = alarmStore.commonFilterParams.end_time;
    if (!endTime) return;

    if (trendAbortController) trendAbortController.abort();
    const controller = new AbortController();
    trendAbortController = controller;
    const { signal } = controller;

    trendLoading.value = true;
    const trendMap = await (alarmStore.alarmService as IssuesService).getIssueTrend(issues, endTime, trendRange.value, {
      signal,
    });
    if (signal.aborted) return;
    for (const issue of issues) {
      issue.trend = trendMap[issue.id] || [];
    }
    if (trendAbortController === controller) {
      trendLoading.value = false;
    }
  };

  // 由于在 setup(create) | BeforeMount 时机可能需要获取路由参数对变量进行初始化
  // 如果不在 onMounted 时机进行 watchEffect 可能会导致 effect 首次执行是错误的且是非必要的
  onMounted(() => {
    watchEffect(effectFunc);
    watch(trendRange, fetchTrendData);
  });

  onScopeDispose(() => {
    // 中止未完成的请求
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    if (trendAbortController) {
      trendAbortController.abort();
      trendAbortController = null;
    }
    pageSize.value = commonPageSizeGet() ?? 50;
    page.value = 1;
    total.value = 0;
    isPartial.value = false;
    totalRelation.value = 'eq';
    data.value = [];
    loading.value = false;
    ordering.value = '';
    enabledSpaces.value = [];
    wxCsLink.value = '';
    trendRange.value = TrendRangeEnum.HOURS_24;
    trendLoading.value = false;
  });
  return {
    pageSize,
    page,
    total,
    isPartial,
    totalRelation,
    data,
    loading,
    ordering,
    enabledSpaces,
    wxCsLink,
    trendRange,
    trendLoading,
  };
}
