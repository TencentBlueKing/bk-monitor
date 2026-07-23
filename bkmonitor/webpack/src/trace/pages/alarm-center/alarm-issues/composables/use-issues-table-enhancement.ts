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

import { type MaybeRef, type Ref, onScopeDispose, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

import { AlarmType } from '../../typings';
import { TrendRangeEnum } from '../constant';

import type { IssuesService } from '../../services/issues-services';
import type { IssueItem, TrendRangeType } from '../typing';

export interface UseIssuesTableEnhancementOptions {
  /** 当前告警类型 */
  alarmType?: MaybeRef<AlarmType>;
  /** 基础表格数据（由 useAlarmTable 提供） */
  data: Ref<IssueItem[]>;
  /** 查询结束时间戳（用于趋势数据） */
  endTime: MaybeRef<number | undefined>;
  /** IssuesService 实例，用于获取趋势数据 */
  serviceInstance: MaybeRef<IssuesService>;
}

export interface UseIssuesTableEnhancementReturn {
  /** 趋势数据加载中 */
  trendLoading: Ref<boolean>;
  /** 趋势时间范围 */
  trendRange: Ref<TrendRangeType>;
  /** 切换趋势时间范围 */
  onTrendRangeChange: (range: TrendRangeType) => void;
}

/**
 * @description Issues 表格异步数据增强层 hook，负责趋势数据和日志内容的获取与回填
 * @param {UseIssuesTableEnhancementOptions} options - 基础数据、service 实例、结束时间、告警类型
 * @returns {UseIssuesTableEnhancementReturn} 趋势相关状态和操作函数
 */
export function useIssuesTableEnhancement(options: UseIssuesTableEnhancementOptions): UseIssuesTableEnhancementReturn {
  const { data, serviceInstance, endTime, alarmType } = options;

  /** 趋势时间范围(24h | 7d) */
  const trendRange = shallowRef<TrendRangeType>(TrendRangeEnum.HOURS_24);
  /** 趋势数据加载中 */
  const trendLoading = shallowRef(false);
  /** 趋势请求中止控制器 */
  let trendAbortController: AbortController | null = null;
  /** Log 请求中止控制器 */
  let logAbortController: AbortController | null = null;

  /**
   * @description 判断是否满足触发 Issues 请求的前置条件
   */
  const shouldFetchIssues = (issues: IssueItem[]) => {
    // -- alarmType 有值时，非 ISSUES 告警类型时不触发
    // -- alarmType 无值时， 默认可以触发
    if (get(alarmType) !== undefined && get(alarmType) !== AlarmType.ISSUES) {
      return false;
    }
    // 空列表不触发
    if (!issues.length) {
      return false;
    }
    return true;
  };

  /**
   * @description 获取 Issues 趋势数据并回填到当前列表行
   */
  const fetchTrendData = async (issues: IssueItem[]) => {
    if (trendAbortController) trendAbortController.abort();

    const trendEndTime = get(endTime);
    if (!shouldFetchIssues(issues) || !trendEndTime) return;

    const controller = new AbortController();
    trendAbortController = controller;
    const { signal: trendSignal } = controller;

    trendLoading.value = true;
    const trendMap = await get(serviceInstance).getIssueTrend(issues, trendEndTime, trendRange.value, {
      signal: trendSignal,
    });
    if (trendSignal.aborted) return;
    for (const issue of issues) {
      issue.trend = trendMap[issue.id] || [];
    }
    if (trendAbortController === controller) {
      trendLoading.value = false;
    }
  };

  /**
   * @description 按批串行获取 Issue 关联日志内容并回填
   * - 每批最多 10 条
   * - 串行执行，避免并发超限
   * - 单批失败静默处理，不影响其他批次
   * - 无 loading 状态
   */
  const fetchLogContent = async (issues: IssueItem[]) => {
    if (logAbortController) logAbortController.abort();
    if (!shouldFetchIssues(issues)) return;
    const controller = new AbortController();
    logAbortController = controller;
    const { signal: logSignal } = controller;

    const batchSize = 10;
    const batches: IssueItem[][] = [];
    for (let i = 0; i < issues.length; i += batchSize) {
      batches.push(issues.slice(i, i + batchSize));
    }

    for (const batch of batches) {
      if (logSignal.aborted) return;

      const dataMap = await get(serviceInstance).getIssueLogContent(batch, {
        signal: logSignal,
      });

      if (logSignal.aborted) return;

      for (const issue of batch) {
        issue.log_content = dataMap[issue.id]?.log_content || '';
      }
    }
  };

  const onTrendRangeChange = (range: TrendRangeType) => {
    trendRange.value = range;
  };

  /**
   * @description 监听 data 变化，自动触发趋势和 log 的异步获取
   * - 翻页/筛选时 data 变化，自动取消前一轮未完成请求
   * - 仅当 alarmType 为 ISSUES 时生效
   */
  watch(data, newData => {
    // 并发触发趋势和 log（两者互相独立）
    fetchTrendData(newData);
    fetchLogContent(newData);
  });

  /**
   * @description 监听趋势时间范围变化，重新获取趋势数据
   */
  watch(trendRange, () => {
    fetchTrendData(data.value);
  });

  onScopeDispose(() => {
    trendAbortController?.abort();
    logAbortController?.abort();
    trendAbortController = null;
    logAbortController = null;
    trendRange.value = TrendRangeEnum.HOURS_24;
    trendLoading.value = false;
  });

  return {
    trendRange,
    trendLoading,
    onTrendRangeChange,
  };
}
