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

import { shallowRef, watch } from 'vue';

import { issueDetail } from 'monitor-api/modules/issue';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import { defineStore } from 'pinia';

import type { IssueDetail } from '../../pages/alarm-center/alarm-issues/typing';

/**
 * @description Issue 详情全局 Store
 *
 * 设计目标：让 Issue Detail SideSlider 与 TAPD 创建弹窗共享同一份数据，
 * 避免首次 TAPD 授权后表单默认值无法回填（通过延迟弹窗渲染，等待 detail 异步就绪）。
 *
 * 字段语义：
 *   - issueId / bizId：仅由 IssuesDetailSideSlider 同步 props 写入，其他消费者只读。
 *   - detail：当前展示态（含未保存的本地编辑 name/assignee/priority/status）。
 *     IssuesDetailSideSlider 编辑时直接写本字段；IssuesTapd/TapdSideslider 读取后回填表单。
 *
 * 请求生命周期（store 自管 AbortController，不依赖 useRequestAbort 的组件级 onUnmounted）：
 *   - 切换 issue：fetchDetail 开头 abort 上一次，避免竞态。
 *   - 关闭侧滑 / 组件卸载：由 IssuesDetailSideSlider 调 reset() 显式 abort 并清空。
 */
export const useIssuesDetailStore = defineStore('issuesDetail', () => {
  /** Issue ID（仅 IssuesDetailSideSlider 写入） */
  const issueId = shallowRef('');
  /** 业务 ID（仅 IssuesDetailSideSlider 写入） */
  const bizId = shallowRef<null | number>(null);
  /** Issue 详情：展示态（含未保存编辑） */
  const detail = shallowRef<IssueDetail | undefined>(undefined);
  /** 加载状态 */
  const loading = shallowRef(false);
  /** 时间范围 */
  const timeRange = shallowRef<(number | string)[]>(['now-1h', 'now']);
  /** 时区 */
  const timezone = shallowRef(getDefaultTimezone());
  /** 刷新间隔 */
  const refreshInterval = shallowRef(-1);

  /** 当前请求的 AbortController，用于中止过期请求 */
  let abortController: AbortController | null = null;

  /**
   * @description 初始化默认查询时间范围
   */
  const initTimeRange = () => {
    const timeValue = detail.value?.first_alert_time ?? 'now-1h';
    const time = Number(timeValue);
    timeRange.value = [Number.isNaN(time) ? timeValue : time * 1000, 'now'];
  };

  /**
   * @description 获取 Issue 详情数据
   *
   * 注意：TAPD 首次授权回调场景中，本方法在 IssuesDetailSideSlider 中异步调用。
   * 数据到达后通过全局 store 中的 detail 字段驱动 IssuesTapd 的弹窗显示（show = createTapdSliderShow && !!detail），
   * 从而避免表单字段在数据未就绪前被初始化导致无法回填。
   */
  const fetchDetail = async () => {
    if (!issueId.value || !bizId.value) {
      detail.value = undefined;
      loading.value = false;
      return;
    }

    // 中止上一次未完成请求，避免切换 issue 时的竞态
    abortController?.abort();
    abortController = new AbortController();
    const { signal } = abortController;

    loading.value = true;
    try {
      const res = await issueDetail(
        { bk_biz_id: bizId.value, id: issueId.value },
        { signal } // 透传 signal，请求可被真正中止
      ).catch(() => undefined);
      // 请求期间若已被新请求或 reset 中止，丢弃过期结果
      if (signal.aborted) return;
      detail.value = res;
      initTimeRange();
    } finally {
      loading.value = false;
    }
  };

  /**
   * @description 刷新详情
   */
  const refresh = () => fetchDetail();

  /**
   * @description 重置状态：中止请求并清空全部字段
   */
  const reset = () => {
    abortController?.abort();
    abortController = null;
    issueId.value = '';
    bizId.value = null;
    detail.value = undefined;
    loading.value = false;
    timeRange.value = ['now-1h', 'now'];
    timezone.value = getDefaultTimezone();
    refreshInterval.value = -1;
  };

  // 监听 id 变化自动请求（显式依赖，避免 watchEffect 自动追踪）
  watch([issueId, bizId], fetchDetail, { immediate: true });

  return {
    issueId,
    bizId,
    detail,
    loading,
    timeRange,
    timezone,
    refreshInterval,
    fetchDetail,
    refresh,
    reset,
  };
});
