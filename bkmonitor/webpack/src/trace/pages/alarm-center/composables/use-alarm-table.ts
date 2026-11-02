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
import { computed, ref as deepRef, onMounted, onScopeDispose, shallowRef, watch, watchEffect } from 'vue';

import { commonPageSizeGet } from 'monitor-common/utils';

import { getAlertRelevanceNeeds } from '../services/base';
import { AlarmType } from '../typings';
import { getOperatorDisabled } from '../utils';
import { useAlarmTableColumns } from './use-table-columns';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { IssueItem } from '../alarm-issues/typing';
import type { ActionTableItem, AlertTableItem, IncidentTableItem } from '../typings';

export function useAlarmTable() {
  const alarmStore = useAlarmCenterStore();
  const { storageColumns } = useAlarmTableColumns();
  const relevanceNeeds = computed(() => getAlertRelevanceNeeds(storageColumns.value));
  /** 分页参数 */
  const pageSize = shallowRef(commonPageSizeGet() ?? 50);
  /** 当前页 */
  const page = shallowRef(1);
  /** 总条数 */
  const total = shallowRef(0);
  /** 表格数据（深响应式，支持直接修改行对象属性后触发重新渲染） */
  const data = deepRef<(ActionTableItem | AlertTableItem | IncidentTableItem | IssueItem)[]>([]);
  /** 排序字段 */
  const ordering = shallowRef('');
  /** 是否加载中 */
  const loading = shallowRef(true);
  const hasLoaded = shallowRef(false);
  /** 已开启故障分析功能的空间 bizId 列表（incident 场景专用） */
  const enabledSpaces = deepRef<number[]>([]);
  /** BK助手链接 */
  const wxCsLink = shallowRef('');
  /** 请求中止控制器 */
  let abortController: AbortController | null = null;
  let dataContext = '';

  const effectFunc = async () => {
    // 中止上一次未完成的请求
    if (abortController) {
      abortController.abort();
    }
    // 创建新的中止控制器
    abortController = new AbortController();
    const { signal } = abortController;

    loading.value = true;
    const context = JSON.stringify([alarmStore.alarmType, alarmStore.bizIds]);
    if (context !== dataContext) {
      dataContext = context;
      data.value = [];
      total.value = 0;
      enabledSpaces.value = [];
      hasLoaded.value = false;
    }
    const service = alarmStore.alarmService;
    const params = {
      ...alarmStore.commonFilterParams,
      page_size: pageSize.value,
      page: page.value,
      ordering: ordering.value ? [ordering.value] : [],
    };
    try {
      const res = await service.getFilterTableList(params, { signal });
      // 检查请求是否已被中止，确保不会更新过期数据
      if (signal.aborted) return;
      for (const item of res.data as AlertTableItem[]) {
        item.followerDisabled = getOperatorDisabled(item.follower, item.assignee);
      }
      total.value = res.total;
      data.value = res.data;
      enabledSpaces.value = (res.enabled_spaces ?? []).map(Number);
      wxCsLink.value = res.wx_cs_link ?? '';
      hasLoaded.value = true;
      const currentData = data.value as (ActionTableItem | AlertTableItem | IncidentTableItem)[];
      // 按当前显示列按需回填关联事件数 / 关联信息，不阻塞列表展示
      fillAlterRelevance(currentData as AlertTableItem[], relevanceNeeds.value, signal);
    } finally {
      if (!signal.aborted) loading.value = false;
    }
  };

  const fillAlterRelevance = (
    currentData: AlertTableItem[],
    needs: ReturnType<typeof getAlertRelevanceNeeds>,
    signal?: AbortSignal
  ) => {
    if (alarmStore.alarmType !== AlarmType.ALERT) return;
    if (!needs.needEventCount && !needs.needRelatedInfo) return;
    if (!currentData.length) return;
    alarmStore.alarmService.getAlterRelevance(currentData, { signal, ...needs }).then(result => {
      if (!result || signal?.aborted) return;
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { event_count, extend_info } = result;
      for (const item of currentData) {
        if (needs.needEventCount && event_count) {
          item.event_count = event_count[item.id];
        }
        if (needs.needRelatedInfo && extend_info) {
          item.extend_info = extend_info[item.id];
        }
      }
    });
  };

  // 由于在 setup(create) | BeforeMount 时机可能需要获取路由参数对变量进行初始化
  // 如果不在 onMounted 时机进行 watchEffect 可能会导致 effect 首次执行是错误的且是非必要的
  onMounted(() => {
    watchEffect(effectFunc);
    watch(
      () => [relevanceNeeds.value.needEventCount, relevanceNeeds.value.needRelatedInfo],
      ([needEventCount, needRelatedInfo], prev) => {
        if (loading.value || !hasLoaded.value) return;
        fillAlterRelevance(
          data.value as AlertTableItem[],
          {
            needEventCount: needEventCount && !prev?.[0],
            needRelatedInfo: needRelatedInfo && !prev?.[1],
          },
          abortController?.signal
        );
      }
    );
  });

  onScopeDispose(() => {
    // 中止未完成的请求
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    pageSize.value = commonPageSizeGet() ?? 50;
    page.value = 1;
    total.value = 0;
    data.value = [];
    loading.value = false;
    ordering.value = '';
    enabledSpaces.value = [];
    wxCsLink.value = '';
  });
  return {
    pageSize,
    page,
    total,
    data,
    loading,
    hasLoaded,
    ordering,
    enabledSpaces,
    wxCsLink,
  };
}
